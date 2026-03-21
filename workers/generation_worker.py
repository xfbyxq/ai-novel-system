"""生成任务 Celery Worker."""

import asyncio
import logging
from uuid import UUID

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """在同步 Celery task 中运行异步函数."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _execute_planning(novel_id: str, task_id: str):
    """异步执行企划任务."""
    from core.database import async_session_factory
    from backend.services.generation_service import GenerationService
    from core.models.generation_task import GenerationTask, TaskStatus
    from sqlalchemy import select

    async with async_session_factory() as session:
        # 检查是否已有企划任务在运行
        existing_result = await session.execute(
            select(GenerationTask)
            .where(
                GenerationTask.novel_id == novel_id,
                GenerationTask.task_type == "planning",
                GenerationTask.status.in_([TaskStatus.pending, TaskStatus.running]),
            )
            .order_by(GenerationTask.created_at.desc())
        )
        existing_task = existing_result.scalar_one_or_none()
        if existing_task:
            logger.warning(
                f"Other planning task already running for novel {novel_id} (Task ID: {existing_task.id})"
            )
            return {
                "status": "failed",
                "error": f"其他企划任务已在运行中 (Task ID: {existing_task.id})",
            }

        service = GenerationService(session)
        try:
            result = await service.run_planning(novel_id, task_id)
            return {"status": "completed", "novel_id": novel_id, "task_id": task_id}
        except Exception as e:
            logger.error(f"Planning task failed: {e}")
            return {"status": "failed", "error": str(e)}


async def _execute_writing(
    novel_id: str, task_id: str, chapter_number: int, volume_number: int
):
    """异步执行写作任务."""
    from core.database import async_session_factory
    from backend.services.generation_service import GenerationService

    async with async_session_factory() as session:
        service = GenerationService(session)
        try:
            result = await service.run_chapter_writing(
                UUID(novel_id), UUID(task_id), chapter_number, volume_number
            )
            return {
                "status": "completed",
                "novel_id": novel_id,
                "chapter_number": chapter_number,
                "word_count": result.get("chapter_plan", {}).get(
                    "target_word_count", 0
                ),
            }
        except Exception as e:
            logger.error(f"Writing task failed: {e}")
            return {"status": "failed", "error": str(e)}


@celery_app.task(name="workers.generation_worker.run_planning_task", bind=True)
def run_planning_task(self, novel_id: str, task_id: str):
    """Celery task: 执行企划阶段."""
    logger.info(f"Starting planning task for novel {novel_id}")
    return _run_async(_execute_planning(novel_id, task_id))


@celery_app.task(name="workers.generation_worker.run_writing_task", bind=True)
def run_writing_task(
    self, novel_id: str, task_id: str, chapter_number: int, volume_number: int = 1
):
    """Celery task: 执行单章写作."""
    logger.info(f"Starting writing task for novel {novel_id}, chapter {chapter_number}")
    return _run_async(
        _execute_writing(novel_id, task_id, chapter_number, volume_number)
    )
