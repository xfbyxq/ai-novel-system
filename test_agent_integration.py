"""Agent集成测试脚本"""

import asyncio
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import create_engine

from core.database import Base, async_session_factory
from backend.config import settings
from core.models.novel import Novel, NovelStatus
from core.models.generation_task import GenerationTask, TaskStatus
from backend.services.generation_service import GenerationService

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_agent_integration():
    """测试Agent集成功能"""
    logger.info("开始测试Agent集成功能...")
    
    # 使用现有的会话工厂
    async with async_session_factory() as session:
        try:
            # 1. 创建测试小说
            novel = Novel(
                title="测试小说 - Agent集成",
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
            
            # 2. 创建测试任务
            task_id = uuid4()
            task = GenerationTask(
                novel_id=novel.id,
                task_type="planning",
                phase="planning",
                input_data={},
                status=TaskStatus.pending
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            logger.info(f"创建测试任务成功: ID: {task.id}")
            
            # 3. 初始化GenerationService
            service = GenerationService(session)
            
            # 4. 执行企划阶段
            logger.info("开始执行企划阶段...")
            planning_result = await service.run_planning(novel.id, task.id)
            logger.info(f"企划阶段执行完成: {planning_result}")
            
            # 5. 执行写作阶段（第一章）
            logger.info("开始执行写作阶段...")
            writing_result = await service.run_chapter_writing(novel.id, task.id, chapter_number=1, volume_number=1)
            logger.info(f"写作阶段执行完成: 第1章，{len(writing_result.get('final_content', ''))}字")
            
            # 6. 验证结果
            logger.info("验证生成结果...")
            assert planning_result, "企划结果为空"
            assert writing_result, "写作结果为空"
            assert "final_content" in writing_result, "写作结果中缺少final_content"
            assert len(writing_result["final_content"]) > 0, "生成的内容为空"
            
            logger.info("✅ Agent集成测试成功！")
            
        except Exception as e:
            logger.error(f"❌ Agent集成测试失败: {e}")
            raise
        finally:
            # 清理测试数据
            try:
                # 先删除任务
                if 'task' in locals():
                    await session.delete(task)
                # 再删除小说
                await session.delete(novel)
                await session.commit()
                logger.info("清理测试数据完成")
            except Exception as e:
                logger.error(f"清理测试数据失败: {e}")
                await session.rollback()


if __name__ == "__main__":
    asyncio.run(test_agent_integration())