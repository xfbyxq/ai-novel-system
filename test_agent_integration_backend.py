"""Agent集成测试脚本 - 后端模式"""

import asyncio
import logging
import time

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import async_session_factory
from core.models.novel import Novel, NovelStatus
from core.models.generation_task import GenerationTask
from backend.config import settings

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_BASE_URL = f"http://localhost:{settings.APP_PORT}/api/v1"


async def create_test_novel():
    """创建测试小说"""
    async with async_session_factory() as session:
        novel = Novel(
            title="测试小说 - Agent集成 (后端模式)",
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
    from sqlalchemy import delete
    
    async with async_session_factory() as session:
        try:
            # 先删除相关任务
            await session.execute(
                delete(GenerationTask).where(GenerationTask.novel_id == novel_id)
            )
            
            # 再删除小说
            await session.execute(
                delete(Novel).where(Novel.id == novel_id)
            )
            
            await session.commit()
            logger.info("清理测试数据完成")
        except Exception as e:
            logger.error(f"清理测试数据失败: {e}")
            await session.rollback()


async def wait_for_task_completion(task_id, timeout=300):
    """等待任务完成"""
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start_time < timeout:
            response = await client.get(f"{API_BASE_URL}/generation/tasks/{task_id}")
            if response.status_code == 200:
                task_data = response.json()
                status = task_data.get("status")
                logger.info(f"任务 {task_id} 状态: {status}")
                if status in ["completed", "failed", "cancelled"]:
                    return task_data
            await asyncio.sleep(5)
    raise TimeoutError(f"任务 {task_id} 超时未完成")


async def test_agent_integration_backend():
    """测试Agent集成功能 - 后端模式"""
    logger.info("开始测试Agent集成功能 (后端模式)...")
    
    novel = None
    try:
        # 1. 创建测试小说
        novel = await create_test_novel()
        
        # 2. 初始化HTTP客户端
        async with httpx.AsyncClient() as client:
            # 3. 创建并执行企划任务
            logger.info("创建企划任务...")
            planning_response = await client.post(
                f"{API_BASE_URL}/generation/tasks",
                json={
                    "novel_id": str(novel.id),
                    "task_type": "planning",
                    "phase": "planning",
                    "input_data": {}
                }
            )
            
            if planning_response.status_code != 201:
                logger.error(f"创建企划任务失败: {planning_response.text}")
                raise Exception(f"创建企划任务失败: {planning_response.status_code}")
            
            planning_task = planning_response.json()
            planning_task_id = planning_task.get("id")
            logger.info(f"创建企划任务成功: ID: {planning_task_id}")
            
            # 4. 等待企划任务完成
            logger.info("等待企划任务完成...")
            planning_result = await wait_for_task_completion(planning_task_id)
            if planning_result.get("status") != "completed":
                logger.error(f"企划任务失败: {planning_result}")
                raise Exception(f"企划任务失败: {planning_result.get('status')}")
            logger.info("企划任务执行完成！")
            
            # 5. 创建并执行写作任务
            logger.info("创建写作任务...")
            writing_response = await client.post(
                f"{API_BASE_URL}/generation/tasks",
                json={
                    "novel_id": str(novel.id),
                    "task_type": "writing",
                    "phase": "writing",
                    "input_data": {
                        "chapter_number": 1,
                        "volume_number": 1
                    }
                }
            )
            
            if writing_response.status_code != 201:
                logger.error(f"创建写作任务失败: {writing_response.text}")
                raise Exception(f"创建写作任务失败: {writing_response.status_code}")
            
            writing_task = writing_response.json()
            writing_task_id = writing_task.get("id")
            logger.info(f"创建写作任务成功: ID: {writing_task_id}")
            
            # 6. 等待写作任务完成
            logger.info("等待写作任务完成...")
            writing_result = await wait_for_task_completion(writing_task_id)
            if writing_result.get("status") != "completed":
                logger.error(f"写作任务失败: {writing_result}")
                raise Exception(f"写作任务失败: {writing_result.get('status')}")
            logger.info("写作任务执行完成！")
            
        logger.info("✅ Agent集成测试 (后端模式) 成功！")
    except Exception as e:
        logger.error(f"❌ Agent集成测试 (后端模式) 失败: {e}")
        raise
    finally:
        # 清理测试数据
        if novel:
            await delete_test_data(novel.id)


if __name__ == "__main__":
    asyncio.run(test_agent_integration_backend())
