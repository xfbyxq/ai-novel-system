"""Logging configuration for the Novel Generation System.

统一日志配置模块：
- 日志统一在 logs/ 目录下生成
- 支持按大小轮转
- 支持过期自动清理（默认保留7天）
- 支持后端和 Worker 日志分离
"""

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.config import settings

# 获取根 logger 实例，供其他模块导入使用
# 使用方式: from core.logging_config import logger
logger = logging.getLogger("novel_system")


def get_project_root() -> Path:
    """
    获取项目根目录。

    基于当前文件位置向上两级定位项目根目录。
    core/ -> 项目根目录

    Returns:
        Path: 项目根目录路径
    """
    # core/ -> 项目根目录
    config_dir = Path(__file__).resolve().parent
    project_root = config_dir.parent
    return project_root


def ensure_log_directory() -> Path:
    """
    确保日志目录存在。

    如果目录不存在则创建，设置合适的权限。

    Returns:
        Path: 日志目录的绝对路径
    """
    project_root = get_project_root()
    log_dir = project_root / settings.LOG_DIR

    # 创建目录（如果不存在），设置 0o755 权限
    log_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

    return log_dir


def cleanup_old_logs():
    """
    清理过期的日志文件。

    基于文件修改时间删除超过保留天数的日志文件。
    在日志配置初始化时调用，确保写入新日志前完成清理。

    清理逻辑：
    - 跳过当前正在写入的 .log 主文件（app.log, worker.log）
    - 删除修改时间超过 LOG_RETENTION_DAYS 的所有 .log* 文件
    """
    log_dir = ensure_log_directory()

    if not log_dir.exists():
        return

    current_time = time.time()
    # 计算过期时间戳（当前时间 - 保留天数）
    cutoff_time = current_time - (settings.LOG_RETENTION_DAYS * 24 * 60 * 60)

    cleaned_count = 0

    # 遍历所有日志相关文件
    for log_file in log_dir.glob("*.log*"):
        try:
            # 获取文件修改时间
            file_mtime = log_file.stat().st_mtime

            # 如果文件已过期，删除
            if file_mtime < cutoff_time:
                # 跳过当前正在写入的主日志文件（不带数字后缀的 .log 文件）
                # 例如 app.log 保留，但 app.log.1, app.log.2 等备份可以删除
                if log_file.suffix == ".log" and not log_file.name.endswith((".1", ".2", ".3", ".4", ".5")):
                    continue

                log_file.unlink()
                cleaned_count += 1
        except OSError:
            # 忽略文件删除错误（如权限问题或文件已被其他进程处理）
            pass

    if cleaned_count > 0:
        print(f"日志清理: 已删除 {cleaned_count} 个过期日志文件")


def get_log_level() -> int:
    """
    根据配置获取日志级别。

    Returns:
        int: logging.DEBUG 或 logging.INFO
    """
    return logging.DEBUG if settings.APP_DEBUG else logging.INFO


# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging():
    """
    配置后端日志系统。

    功能：
    1. 创建日志目录
    2. 清理过期日志
    3. 配置根 logger（控制台 + 文件）
    4. 设置第三方库日志级别

    日志输出：
    - 控制台：stdout
    - 文件：logs/app.log（按大小轮转）
    """
    # 1. 确保日志目录存在
    log_dir = ensure_log_directory()

    # 2. 清理过期日志
    cleanup_old_logs()

    # 3. 获取日志级别
    log_level = get_log_level()

    # 4. 获取根 logger 并彻底清除所有 handlers（包括其他模块添加的）
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 只禁用第三方库的日志传播，避免重复输出应用日志
    # 第三方库logger列表
    third_party_loggers = [
        "sqlalchemy", "httpx", "asyncio", "urllib3", "celery",
        "uvicorn", "uvicorn.error", "uvicorn.access",
        "watchfiles", "fastapi", "starlette", "httpcore", "anyio",
    ]
    for name in third_party_loggers:
        log = logging.getLogger(name)
        log.propagate = False
        log.setLevel(logging.WARNING)

    # 确保应用模块日志正确配置
    # 这些logger不需要单独设置handler，让它们传播到root logger统一输出
    for prefix in ["novel_system", "llm", "backend", "agents", "core"]:
        log = logging.getLogger(prefix)
        # 开启传播，让日志传播到root logger输出
        log.propagate = True
        log.setLevel(log_level)
        # 清除可能存在的重复handler
        log.handlers = []

    # 5. 控制台 Handler（只保留一个）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(console_handler)

    # 6. 文件 Handler（按大小轮转）
    log_file_path = log_dir / settings.LOG_FILE_NAME
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)

    return root_logger


def setup_worker_logging():
    """
    配置 Celery Worker 日志系统。

    功能：
    1. 创建 Worker 专用 logger
    2. 输出到 logs/worker.log（按大小轮转）
    3. 继承根 logger 的配置

    注意：
    - 需要在 setup_logging() 之后调用
    - Worker 日志会同时输出到控制台（继承根 logger）
    """
    # 获取日志目录
    log_dir = ensure_log_directory()
    log_level = get_log_level()

    # 创建 Worker 专用 logger
    worker_logger = logging.getLogger("workers")
    worker_logger.setLevel(log_level)

    # 清除现有 handlers（避免重复配置）
    worker_logger.handlers = []

    # 控制台 Handler（继承根 logger 的控制台输出）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    worker_logger.addHandler(console_handler)

    # 文件 Handler（Worker 专用日志文件）





    
    worker_log_path = log_dir / settings.LOG_WORKER_FILE_NAME
    file_handler = RotatingFileHandler(
        worker_log_path,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    worker_logger.addHandler(file_handler)

    return worker_logger


# 注意：不要在这里自动初始化，让使用方手动调用 setup_logging()
# 如果需要初始化，使用: from core.logging_config import setup_logging; setup_logging()