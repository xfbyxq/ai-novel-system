"""Agent集成测试脚本 - 后台任务模式"""

import asyncio
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_factory
from core.models.novel import Novel, NovelStatus
from core.models.generation_task import GenerationTask, TaskStatus
from backend.services.generation_service import GenerationService

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def create_test_novel():
    """创建测试小说"""
    async with async_session_factory() as session:
        novel = Novel(
            title="测试小说 - Agent集成 (后台任务模式)",
            genre="玄幻",
            tags=["修仙", "冒险", "玄幻"],
            synopsis="这是一本测试Agent集成功能的小说",
            status=NovelStatus.planning,
            author="测试用户"
        )
        session.add(novel)
        await session.commit()
        await session.refresh(novel)
        logger.info(f"创建测试小说成功: {novel.title} (ID: {novel.id})")
        return novel


async def delete_test_data(novel_id):
    """清理测试数据"""
    async with async_session_factory() as session:
        try:
            # 先删除相关任务
            from core.models.generation_task import GenerationTask
            task_result = await session.execute(
                GenerationTask.__table__.select().where(GenerationTask.novel_id == novel_id)
            )
            tasks = task_result.all()
            for task in tasks:
                await session.delete(GenerationTask(id=task.id))
            
            # 再删除小说
            from core.models.novel import Novel
            novel_result = await session.execute(
                Novel.__table__.select().where(Novel.id == novel_id)
            )
            novel = novel_result.scalar_one_or_none()
            if novel:
                await session.delete(novel)
            
            await session.commit()
            logger.info("清理测试数据完成")
        except Exception as e:
            logger.error(f"清理测试数据失败: {e}")
            await session.rollback()


async def run_task_in_background(novel_id, task_type, input_data=None):
    """在后台执行任务"""
    async with async_session_factory() as session:
        # 创建任务记录
        task = GenerationTask(
            novel_id=novel_id,
            task_type=task_type,
            phase=task_type,
            input_data=input_data or {},
            status=TaskStatus.pending,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        logger.info(f"创建任务成功: ID: {task.id}, 类型: {task_type}")
        
        # 执行任务
        service = GenerationService(session)
        try:
            if task_type == "planning":
                result = await service.run_planning(novel_id, task.id)
                logger.info(f"企划任务执行完成: {result}")
            elif task_type == "writing":
                chapter_number = input_data.get("chapter_number", 1)
                volume_number = input_data.get("volume_number", 1)
                result = await service.run_chapter_writing(
                    novel_id, task.id, chapter_number, volume_number
                )
                logger.info(f"写作任务执行完成: 第{chapter_number}章，{len(result.get('final_content', ''))}字")
            task.status = TaskStatus.completed
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            task.status = TaskStatus.failed
            task.error_message = str(e)
        finally:
            await session.commit()
            return task


async def test_agent_integration_background():
    """测试Agent集成功能 - 后台任务模式"""
    logger.info("开始测试Agent集成功能 (后台任务模式)...")
    
    novel = None
    try:
        # 1. 创建测试小说
        novel = await create_test_novel()
        
        # 2. 执行企划任务
        logger.info("开始执行企划任务...")
        planning_task = await run_task_in_background(novel.id, "planning")
        if planning_task.status != TaskStatus.completed:
            logger.error(f"企划任务失败: {planning_task.error_message}")
            raise Exception(f"企划任务失败: {planning_task.status}")
        logger.info("企划任务执行完成！")
        
        # 3. 执行写作任务
        logger.info("开始执行写作任务...")
        writing_task = await run_task_in_background(
            novel.id, "writing",
            input_data={"chapter_number": 1, "volume_number": 1}
        )
        if writing_task.status != TaskStatus.completed:
            logger.error(f"写作任务失败: {writing_task.error_message}")
            raise Exception(f"写作任务失败: {writing_task.status}")
        logger.info("写作任务执行完成！")
        
        logger.info("✅ Agent集成测试 (后台任务模式) 成功！")
        
    except Exception as e:
        logger.error(f"❌ Agent集成测试 (后台任务模式) 失败: {e}")
        raise
    finally:
        # 清理测试数据
        if novel:
            await delete_test_data(novel.id)


if __name__ == "__main__":
    asyncio.run(test_agent_integration_background())
