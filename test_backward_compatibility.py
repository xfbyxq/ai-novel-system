"""向后兼容性测试脚本"""

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
            title="测试小说 - 向后兼容性",
            genre="玄幻",
            tags=["修仙", "冒险", "玄幻"],
            synopsis="这是一本测试向后兼容性的小说",
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


async def test_crewai_style_system():
    """测试CrewAI风格系统（向后兼容性）"""
    logger.info("开始测试CrewAI风格系统 (向后兼容性)...")
    
    novel = None
    try:
        # 1. 创建测试小说
        novel = await create_test_novel()
        
        # 2. 初始化GenerationService
        async with async_session_factory() as session:
            service = GenerationService(session)
            
            # 3. 禁用基于调度器的Agent系统，使用CrewAI风格系统
            service.dispatcher.set_use_scheduled_agents(False)
            
            # 4. 执行企划阶段
            logger.info("开始执行企划阶段 (CrewAI风格)...")
            task_id = uuid4()
            planning_result = await service.run_planning(novel.id, task_id)
            logger.info(f"企划阶段执行完成: {planning_result}")
            
            # 5. 执行写作阶段（第一章）
            logger.info("开始执行写作阶段 (CrewAI风格)...")
            writing_result = await service.run_chapter_writing(novel.id, task_id, chapter_number=1, volume_number=1)
            logger.info(f"写作阶段执行完成: 第1章，{len(writing_result.get('final_content', ''))}字")
            
            # 6. 验证结果
            logger.info("验证生成结果...")
            assert planning_result, "企划结果为空"
            assert writing_result, "写作结果为空"
            assert "final_content" in writing_result, "写作结果中缺少final_content"
            
            logger.info("✅ CrewAI风格系统测试成功！")
            
    except Exception as e:
        logger.error(f"❌ CrewAI风格系统测试失败: {e}")
        raise
    finally:
        # 清理测试数据
        if novel:
            await delete_test_data(novel.id)


async def test_scheduled_agents_system():
    """测试基于调度器的Agent系统"""
    logger.info("开始测试基于调度器的Agent系统...")
    
    novel = None
    try:
        # 1. 创建测试小说
        novel = await create_test_novel()
        
        # 2. 初始化GenerationService
        async with async_session_factory() as session:
            service = GenerationService(session)
            
            # 3. 启用基于调度器的Agent系统
            service.dispatcher.set_use_scheduled_agents(True)
            
            # 4. 执行企划阶段
            logger.info("开始执行企划阶段 (基于调度器)...")
            task_id = uuid4()
            planning_result = await service.run_planning(novel.id, task_id)
            logger.info(f"企划阶段执行完成: {planning_result}")
            
            # 5. 执行写作阶段（第一章）
            logger.info("开始执行写作阶段 (基于调度器)...")
            writing_result = await service.run_chapter_writing(novel.id, task_id, chapter_number=1, volume_number=1)
            logger.info(f"写作阶段执行完成: 第1章，{len(writing_result.get('final_content', ''))}字")
            
            # 6. 验证结果
            logger.info("验证生成结果...")
            assert planning_result, "企划结果为空"
            assert writing_result, "写作结果为空"
            assert "final_content" in writing_result, "写作结果中缺少final_content"
            
            logger.info("✅ 基于调度器的Agent系统测试成功！")
            
    except Exception as e:
        logger.error(f"❌ 基于调度器的Agent系统测试失败: {e}")
        raise
    finally:
        # 清理测试数据
        if novel:
            await delete_test_data(novel.id)


async def test_backward_compatibility():
    """测试向后兼容性"""
    logger.info("开始向后兼容性测试...")
    
    try:
        # 测试CrewAI风格系统
        await test_crewai_style_system()
        
        # 测试基于调度器的Agent系统
        await test_scheduled_agents_system()
        
        logger.info("✅ 向后兼容性测试成功！两个系统都能正常工作")
        
    except Exception as e:
        logger.error(f"❌ 向后兼容性测试失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_backward_compatibility())
