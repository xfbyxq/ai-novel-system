"""重试工具模块（带指数退避策略）.

提供智能重试机制，用于处理 LLM API 调用等可能失败的操作。
支持：
- 指数退避（Exponential Backoff）
- 最大重试次数限制
- 可配置的延迟时间
- 重试日志记录
- 异常分类处理
"""

import asyncio
import logging
import random
from functools import wraps
from typing import Any, Callable, Optional, Set, Type, TypeVar

from backend.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryError(Exception):
    """重试失败异常."""

    def __init__(self, message: str, attempts: int, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


class RetryConfig:
    """重试配置."""

    def __init__(
        self,
        max_retries: int = None,
        base_delay: float = None,
        max_delay: float = None,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Set[Type[Exception]]] = None,
    ):
        """初始化重试配置.

        Args:
            max_retries: 最大重试次数（不含首次尝试）
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            exponential_base: 指数退避基数
            jitter: 是否添加随机抖动（防止雷群效应）
            retryable_exceptions: 可重试的异常类型集合
        """
        self.max_retries = max_retries or settings.REVIEW_LLM_MAX_RETRIES
        self.base_delay = base_delay or settings.REVIEW_RETRY_BASE_DELAY
        self.max_delay = max_delay or settings.REVIEW_RETRY_MAX_DELAY
        self.exponential_base = exponential_base
        self.jitter = jitter
        
        # 默认重试的异常类型
        self.retryable_exceptions = retryable_exceptions or {
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        }

    def get_delay(self, attempt: int) -> float:
        """计算第 N 次重试的延迟时间.

        使用指数退避公式：delay = min(base_delay * (exponential_base ^ attempt), max_delay)
        如果启用 jitter，添加 0-10% 的随机扰动。

        Args:
            attempt: 当前重试次数（从 0 开始）

        Returns:
            延迟时间（秒）
        """
        # 指数退避
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        # 添加随机抖动（0-10%）
        if self.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(0, jitter_range)
        
        return delay


async def retry_async(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs
) -> T:
    """异步函数重试包装器.

    Args:
        func: 要重试的异步函数
        *args: 函数位置参数
        config: 重试配置（使用默认配置如果未提供）
        on_retry: 每次重试前的回调函数 (attempt, exception, delay)
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果

    Raises:
        RetryError: 重试次数用尽后仍然失败
    """
    config = config or RetryConfig()
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):  # +1 是因为首次尝试不算重试
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
                
        except Exception as e:
            last_exception = e
            
            # 检查是否是可重试的异常
            if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                logger.warning(f"遇到不可重试的异常 {type(e).__name__}: {e}")
                raise
            
            # 检查是否还有重试次数
            if attempt >= config.max_retries:
                logger.error(
                    f"重试次数用尽（{config.max_retries}次）后仍然失败",
                    extra={"last_exception": str(e)}
                )
                raise RetryError(
                    f"函数 {func.__name__} 重试失败",
                    attempts=attempt + 1,
                    last_exception=e
                )
            
            # 计算延迟时间
            delay = config.get_delay(attempt)
            
            # 调用重试回调
            if on_retry:
                on_retry(attempt + 1, e, delay)
            
            # 记录重试日志
            logger.warning(
                f"第 {attempt + 1}/{config.max_retries} 次重试，"
                f"异常：{type(e).__name__}: {e}, "
                f"延迟：{delay:.2f}秒"
            )
            
            # 等待后重试
            await asyncio.sleep(delay)
    
    # 理论上不会到这里，但为了类型安全
    raise RetryError(
        f"函数 {func.__name__} 重试失败",
        attempts=config.max_retries + 1,
        last_exception=last_exception
    )


def retry_sync(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs
) -> T:
    """同步函数重试包装器.

    Args:
        func: 要重试的同步函数
        *args: 函数位置参数
        config: 重试配置
        on_retry: 每次重试前的回调函数
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果

    Raises:
        RetryError: 重试次数用尽后仍然失败
    """
    config = config or RetryConfig()
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return func(*args, **kwargs)
                
        except Exception as e:
            last_exception = e
            
            # 检查是否是可重试的异常
            if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                logger.warning(f"遇到不可重试的异常 {type(e).__name__}: {e}")
                raise
            
            # 检查是否还有重试次数
            if attempt >= config.max_retries:
                logger.error(
                    f"重试次数用尽（{config.max_retries}次）后仍然失败",
                    extra={"last_exception": str(e)}
                )
                raise RetryError(
                    f"函数 {func.__name__} 重试失败",
                    attempts=attempt + 1,
                    last_exception=e
                )
            
            # 计算延迟时间
            delay = config.get_delay(attempt)
            
            # 调用重试回调
            if on_retry:
                on_retry(attempt + 1, e, delay)
            
            # 记录重试日志
            logger.warning(
                f"第 {attempt + 1}/{config.max_retries} 次重试，"
                f"异常：{type(e).__name__}: {e}, "
                f"延迟：{delay:.2f}秒"
            )
            
            # 等待后重试
            time.sleep(delay)
    
    raise RetryError(
        f"函数 {func.__name__} 重试失败",
        attempts=config.max_retries + 1,
        last_exception=last_exception
    )


def with_retry(config: Optional[RetryConfig] = None):
    """装饰器：为函数添加自动重试功能.

    Usage:
        @with_retry()
        async def fetch_data():
            ...
        
        @with_retry(config=RetryConfig(max_retries=5, base_delay=2.0))
        def call_api():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await retry_async(func, *args, config=config, **kwargs)
            return wrapper
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return retry_sync(func, *args, config=config, **kwargs)
            return wrapper
    
    return decorator


# 导入 time 模块用于同步重试
import time
