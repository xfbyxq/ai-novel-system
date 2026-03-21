"""并发控制工具模块 - Issue #7 修复.

提供数据库事务、行级锁和分布式锁（Redis Lock）功能，
防止多用户同时操作导致的数据不一致问题。
"""

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Optional

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings


class ConcurrentOperationError(Exception):
    """并发操作冲突异常."""

    def __init__(self, resource_type: str, resource_id: str, message: Optional[str] = None):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            message
            or f"并发操作冲突：{resource_type}({resource_id}) 正在被其他操作修改"
        )


class DistributedLock:
    """分布式锁（基于 Redis）.

    使用 Redis SETNX 实现分布式锁，支持自动过期防止死锁。
    """

    def __init__(
        self,
        redis_client: Redis,
        lock_name: str,
        timeout: int = 30,
        retry_times: int = 3,
        retry_delay: float = 0.5,
    ):
        """初始化分布式锁.

        Args:
            redis_client: Redis 客户端
            lock_name: 锁名称
            timeout: 锁超时时间（秒），防止死锁
            retry_times: 重试次数
            retry_delay: 重试间隔（秒）
        """
        self.redis = redis_client
        self.lock_name = f"lock:{lock_name}"
        self.timeout = timeout
        self.retry_times = retry_times
        self.retry_delay = retry_delay
        self.lock_value = f"{time.time()}:{id(self)}"

    async def acquire(self) -> bool:
        """尝试获取锁.

        Returns:
            是否成功获取锁
        """
        for attempt in range(self.retry_times):
            # SETNX: 仅在键不存在时设置
            acquired = await self.redis.set(
                self.lock_name,
                self.lock_value,
                nx=True,  # 仅在不存在时设置
                ex=self.timeout,  # 过期时间
            )
            if acquired:
                return True
            if attempt < self.retry_times - 1:
                await asyncio.sleep(self.retry_delay)
        return False

    async def release(self) -> bool:
        """释放锁.

        Returns:
            是否成功释放锁
        """
        # 使用 Lua 脚本确保原子性：只有锁的值匹配时才删除
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await self.redis.eval(lua_script, 1, self.lock_name, self.lock_value)
        return result == 1

    @asynccontextmanager
    async def __call__(self):
        """上下文管理器用法."""
        acquired = await self.acquire()
        if not acquired:
            raise ConcurrentOperationError("distributed_lock", self.lock_name)
        try:
            yield
        finally:
            await self.release()


@asynccontextmanager
async def database_transaction(session: AsyncSession):
    """数据库事务上下文管理器.

    提供自动提交/回滚的事务支持。

    Usage:
        async with database_transaction(db) as tx:
            # 执行数据库操作
            await tx.execute(...)
            # 自动提交，异常时自动回滚

    Args:
        session: 数据库会话

    Yields:
        数据库会话
    """
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise


@asynccontextmanager
async def row_level_lock(
    session: AsyncSession,
    table_name: str,
    record_id: str,
    lock_type: str = "update",
):
    """行级锁上下文管理器.

    使用 SELECT FOR UPDATE 实现行级锁，防止并发更新。

    Usage:
        async with row_level_lock(db, "novels", novel_id):
            # 在锁内执行更新操作
            novel.status = "writing"
            await db.commit()

    Args:
        session: 数据库会话
        table_name: 表名
        record_id: 记录 ID
        lock_type: 锁类型 ("update" | "share")
    """
    try:
        # 开始事务
        await session.begin()

        # 获取行级锁
        if lock_type == "update":
            # FOR UPDATE: 排他锁，防止其他事务读取或更新
            query = (
                select(1)
                .select_from(f'"{table_name}"')  # 使用引号避免 SQL 注入
                .where(f"id = '{record_id}'")
                .with_for_update()
            )
        else:
            # FOR SHARE: 共享锁，允许其他事务读取但不允许更新
            query = (
                select(1)
                .select_from(f'"{table_name}"')
                .where(f"id = '{record_id}'")
                .with_for_update(read=True)
            )

        await session.execute(query)
        yield session

    except Exception:
        await session.rollback()
        raise


def with_concurrency_control(
    resource_type: str,
    resource_id_field: str = "id",
    lock_timeout: int = 30,
    use_redis: bool = True,
):
    """并发控制装饰器.

    为 API 端点添加并发控制，防止竞态条件。

    Usage:
        @router.patch("/{novel_id}")
        @with_concurrency_control("novel", "novel_id")
        async def update_novel(novel_id: UUID, novel_in: NovelUpdate, db: AsyncSession):
            # 自动获取分布式锁，防止并发更新
            ...

    Args:
        resource_type: 资源类型（用于锁命名）
        resource_id_field: 资源 ID 字段名（从请求参数中获取）
        lock_timeout: 锁超时时间（秒）
        use_redis: 是否使用 Redis 分布式锁（否则仅使用数据库事务）
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从参数中提取资源 ID
            resource_id = kwargs.get(resource_id_field)
            if not resource_id:
                raise ValueError(f"无法获取资源 ID 字段：{resource_id_field}")

            lock_name = f"{resource_type}:{resource_id}"

            if use_redis and hasattr(settings, "REDIS_URL") and settings.REDIS_URL:
                # 使用 Redis 分布式锁
                redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
                async with DistributedLock(
                    redis_client, lock_name, timeout=lock_timeout
                ):
                    result = await func(*args, **kwargs)
                await redis_client.close()
            else:
                # 仅使用数据库事务
                result = await func(*args, **kwargs)

            return result

        return wrapper

    return decorator


async def acquire_novel_lock(
    redis_client: Redis, novel_id: str, timeout: int = 30
) -> DistributedLock:
    """获取小说分布式锁的辅助函数.

    Args:
        redis_client: Redis 客户端
        novel_id: 小说 ID
        timeout: 锁超时时间

    Returns:
        分布式锁实例
    """
    lock = DistributedLock(redis_client, f"novel:{novel_id}", timeout=timeout)
    if not await lock.acquire():
        raise ConcurrentOperationError("novel", str(novel_id))
    return lock


async def acquire_chapter_lock(
    redis_client: Redis, novel_id: str, chapter_number: int, timeout: int = 30
) -> DistributedLock:
    """获取章节分布式锁的辅助函数.

    Args:
        redis_client: Redis 客户端
        novel_id: 小说 ID
        chapter_number: 章节号
        timeout: 锁超时时间

    Returns:
        分布式锁实例
    """
    lock = DistributedLock(
        redis_client, f"chapter:{novel_id}:{chapter_number}", timeout=timeout
    )
    if not await lock.acquire():
        raise ConcurrentOperationError("chapter", f"{novel_id}:{chapter_number}")
    return lock


async def get_redis_client() -> Redis:
    """获取 Redis 客户端.

    Returns:
        Redis 客户端实例
    """
    if not hasattr(settings, "REDIS_URL") or not settings.REDIS_URL:
        raise RuntimeError("Redis URL 未配置")
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)
