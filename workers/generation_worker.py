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
                f"Other planning task already running for novel {novel_id} "
                f"(Task ID: {existing_task.id})"
            )
            return {
                "status": "failed",
                "error": f"其他企划任务已在运行中 (Task ID: {existing_task.id})",
            }

        service = GenerationService(session)
        try:
            await service.run_planning(novel_id, task_id)
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


async def _execute_extract_all_chapters(
    novel_id: str,
    start_chapter: int,
    end_chapter: int,
    task_instance=None,  # Celery task实例，用于进度更新
):
    """异步执行全量章节图谱抽取任务.

    Args:
        novel_id: 小说ID
        start_chapter: 起始章节号
        end_chapter: 结束章节号
        task_instance: Celery task实例，用于更新进度状态

    Returns:
        抽取结果统计
    """
    from core.database import async_session_factory
    from core.models.chapter import Chapter
    from core.models.character import Character
    from sqlalchemy import select
    from backend.services.entity_extractor_service import EntityExtractorService
    from backend.services.graph_sync_service import GraphSyncService
    from core.graph.neo4j_client import get_neo4j_client
    import time

    start_time = time.time()
    novel_uuid = UUID(novel_id)  # 统一转换为UUID类型
    result = {
        "status": "completed",
        "novel_id": novel_id,
        "start_chapter": start_chapter,
        "end_chapter": end_chapter,
        "total_chapters": 0,
        "processed_chapters": 0,
        "total_entities": 0,
        "total_relations": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    async with async_session_factory() as session:
        try:
            # 1. 获取指定范围内的章节
            stmt = select(Chapter).where(
                Chapter.novel_id == novel_uuid,
                Chapter.chapter_number >= start_chapter,
                Chapter.chapter_number <= end_chapter,
                Chapter.content.isnot(None),  # 只处理有内容的章节
            ).order_by(Chapter.chapter_number)

            db_result = await session.execute(stmt)
            chapters = db_result.scalars().all()
            result["total_chapters"] = len(chapters)

            if not chapters:
                logger.warning(f"No chapters found in range {start_chapter}-{end_chapter}")
                return result

            # 2. 获取已有角色列表
            char_stmt = select(Character.name).where(Character.novel_id == novel_uuid)
            char_result = await session.execute(char_stmt)
            known_characters = [row[0] for row in char_result.fetchall()]

            # 3. 初始化服务
            extractor = EntityExtractorService()
            neo4j_client = get_neo4j_client()

            if not neo4j_client or not neo4j_client.is_connected:
                result["status"] = "failed"
                result["errors"].append("图数据库未连接")
                return result

            sync_service = GraphSyncService(neo4j_client, session)

            # 4. 逐章节抽取并同步
            for idx, chapter in enumerate(chapters):
                try:
                    logger.info(
                        f"Extracting chapter {chapter.chapter_number} for novel {novel_id}"
                    )

                    # 抽取实体（只调用一次LLM）
                    extraction = await extractor.extract_from_chapter(
                        chapter_number=chapter.chapter_number,
                        chapter_content=chapter.content or "",
                        known_characters=known_characters,
                    )

                    # 同步到图数据库（使用新方法，避免重复LLM调用）
                    sync_result = await sync_service.sync_extraction_result_only(
                        novel_uuid,
                        chapter.chapter_number,
                        extraction,
                    )

                    result["processed_chapters"] += 1
                    result["total_entities"] += sync_result.entities_created
                    result["total_relations"] += sync_result.relationships_created

                    # 更新已知角色列表（新角色加入）
                    for char in extraction.characters:
                        if char.name not in known_characters:
                            known_characters.append(char.name)

                    # 更新进度（每处理5章更新一次）
                    if task_instance and (idx + 1) % 5 == 0:
                        task_instance.update_state(
                            state="PROGRESS",
                            meta={
                                "current": idx + 1,
                                "total": len(chapters),
                                "status": f"已处理 {idx + 1}/{len(chapters)} 章节",
                            },
                        )

                    logger.info(
                        f"Chapter {chapter.chapter_number} done: "
                        f"entities={sync_result.entities_created}, "
                        f"relations={sync_result.relationships_created}"
                    )

                except Exception as e:
                    error_msg = f"Chapter {chapter.chapter_number}: {str(e)}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    # 继续处理下一章节，不中断

            result["duration_seconds"] = round(time.time() - start_time, 2)
            logger.info(
                f"Extract all completed: "
                f"{result['processed_chapters']}/{result['total_chapters']} chapters, "
                f"entities={result['total_entities']}, relations={result['total_relations']}"
            )

        except Exception as e:
            result["status"] = "failed"
            result["errors"].append(f"Global error: {str(e)}")
            logger.error(f"Extract all task failed: {e}")

    return result


@celery_app.task(
    name="workers.generation_worker.run_extract_all_chapters_task",
    bind=True,
)
def run_extract_all_chapters_task(
    self, novel_id: str, start_chapter: int, end_chapter: int
):
    """Celery task: 全量章节图谱抽取.

    Args:
        novel_id: 小说ID
        start_chapter: 起始章节号
        end_chapter: 结束章节号
    """
    logger.info(
        f"Starting extract all task for novel {novel_id}, "
        f"chapters {start_chapter}-{end_chapter}"
    )
    # 更新任务状态为进行中
    self.update_state(
        state="PROGRESS",
        meta={
            "current": 0,
            "total": end_chapter - start_chapter + 1,
            "status": "初始化中...",
        },
    )
    return _run_async(
        _execute_extract_all_chapters(novel_id, start_chapter, end_chapter, self)
    )
