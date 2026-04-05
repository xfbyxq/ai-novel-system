"""Celery 应用配置."""

from celery import Celery
from backend.config import settings

celery_app = Celery(
    "novel_system",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 分钟超时
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,  # 长任务不预取
    worker_concurrency=2,
)

celery_app.autodiscover_tasks(["workers"])

# 设置 Worker 日志（必须在所有任务注册之后）
from core.logging_config import setup_logging, setup_worker_logging

# 先确保日志系统初始化
setup_logging()
# 再配置 Worker 专用日志
setup_worker_logging()
