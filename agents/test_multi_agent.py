"""多Agent协作系统测试脚本"""
import asyncio
import logging
from uuid import uuid4

from agents.agent_communicator import AgentCommunicator, agent_communicator
from agents.agent_scheduler import AgentScheduler, AgentTask, TaskPriority
from agents.specific_agents import (
    MarketAnalysisAgent,
    ContentPlanningAgent,
    WritingAgent,
    EditingAgent,
    PublishingAgent,
)
from llm.qwen_client import QwenClient
from llm.cost_tracker import CostTracker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_multi_agent_system():
    """测试多Agent协作系统"""
    logger.info("🚀 开始多Agent协作系统测试")
    
    try:
        # 初始化客户端和成本跟踪器
        qwen_client = QwenClient()
        cost_tracker = CostTracker()
        
        # 初始化调度器
        scheduler = AgentScheduler(agent_communicator)
        
        # 创建并注册Agent
        market_agent = MarketAnalysisAgent(
            "市场分析Agent",
            agent_communicator,
            qwen_client,
            cost_tracker,
        )
        
        content_agent = ContentPlanningAgent(
            "内容策划Agent",
            agent_communicator,
            qwen_client,
            cost_tracker,
        )
        
        writing_agent = WritingAgent(
            "创作Agent",
            agent_communicator,
            qwen_client,
            cost_tracker,
        )
        
        editing_agent = EditingAgent(
            "编辑Agent",
            agent_communicator,
            qwen_client,
            cost_tracker,
        )
        
        publishing_agent = PublishingAgent(
            "发布Agent",
            agent_communicator,
            qwen_client,
            cost_tracker,
        )
        
        # 注册Agent
        await scheduler.register_agent(market_agent)
        await scheduler.register_agent(content_agent)
        await scheduler.register_agent(writing_agent)
        await scheduler.register_agent(editing_agent)
        await scheduler.register_agent(publishing_agent)
        
        # 等待Agent启动
        await asyncio.sleep(2)
        
        # 1. 创建市场分析任务
        market_task = AgentTask(
            task_name="市场分析任务",
            task_type="market_analysis",
            priority=TaskPriority.HIGH,
            input_data={
                "market_data": ["起点中文网热门排行榜数据", "抖音热门话题数据"],
                "platform": "all",
            },
        )
        
        market_task_id = await scheduler.submit_task(market_task)
        logger.info(f"📊 提交市场分析任务: {market_task_id}")
        
        # 等待市场分析任务完成
        await asyncio.sleep(5)
        
        # 2. 创建内容策划任务（依赖市场分析任务）
        content_task = AgentTask(
            task_name="内容策划任务",
            task_type="content_planning",
            priority=TaskPriority.HIGH,
            dependencies=[market_task_id],
            input_data={
                "market_analysis": "市场分析结果",
                "user_preferences": {"genre": "玄幻", "tags": ["系统", "穿越"]},
            },
        )
        
        content_task_id = await scheduler.submit_task(content_task)
        logger.info(f"🎯 提交内容策划任务: {content_task_id}")
        
        # 等待内容策划任务完成
        await asyncio.sleep(5)
        
        # 3. 创建创作任务（依赖内容策划任务）
        writing_task = AgentTask(
            task_name="创作任务",
            task_type="writing",
            priority=TaskPriority.MEDIUM,
            dependencies=[content_task_id],
            input_data={
                "content_plan": {"title": "第1章 系统觉醒", "summary": "主角获得系统，开始修炼之路"},
                "chapter_number": 1,
                "world_setting": {"world_name": "天元大陆", "world_type": "玄幻"},
                "characters": [{"name": "林小凡", "personality": "勤奋努力", "background": "普通山村少年"}],
                "plot_outline": {"main_plot": "主角通过系统不断成长，最终成为强者"},
            },
        )
        
        writing_task_id = await scheduler.submit_task(writing_task)
        logger.info(f"✍️  提交创作任务: {writing_task_id}")
        
        # 等待创作任务完成
        await asyncio.sleep(10)
        
        # 4. 创建编辑任务（依赖创作任务）
        editing_task = AgentTask(
            task_name="编辑任务",
            task_type="editing",
            priority=TaskPriority.MEDIUM,
            dependencies=[writing_task_id],
            input_data={
                "draft_content": "第1章 系统觉醒\n林小凡从梦中醒来，发现自己获得了一个神秘的系统...",
                "chapter_number": 1,
                "chapter_title": "系统觉醒",
                "chapter_summary": "主角获得系统，开始修炼之路",
            },
        )
        
        editing_task_id = await scheduler.submit_task(editing_task)
        logger.info(f"📝 提交编辑任务: {editing_task_id}")
        
        # 等待编辑任务完成
        await asyncio.sleep(5)
        
        # 5. 创建发布任务（依赖编辑任务）
        publishing_task = AgentTask(
            task_name="发布任务",
            task_type="publishing",
            priority=TaskPriority.LOW,
            dependencies=[editing_task_id],
            input_data={
                "novel_data": {"title": "系统之最强修炼", "id": "123456"},
                "chapter_data": {"chapter_number": 1, "title": "系统觉醒"},
                "platform": "qidian",
                "account_id": "account_1",
            },
        )
        
        publishing_task_id = await scheduler.submit_task(publishing_task)
        logger.info(f"🚀 提交发布任务: {publishing_task_id}")
        
        # 等待发布任务完成
        await asyncio.sleep(5)
        
        # 测试完成
        logger.info("🎉 多Agent协作系统测试完成")
        
        # 打印成本
        logger.info(f"💰 总token消耗: {cost_tracker.get_total_tokens()}")
        logger.info(f"💰 总成本: ¥{cost_tracker.get_total_cost():.2f}")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("📋 测试结束")


if __name__ == "__main__":
    asyncio.run(test_multi_agent_system())
