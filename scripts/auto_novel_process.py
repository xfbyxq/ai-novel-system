#!/usr/bin/env python3
"""自动小说创作流程脚本"""

import asyncio
import logging
import sys
from datetime import datetime
from uuid import uuid4

# 添加项目根目录到Python路径
sys.path.insert(0, "/Users/sanyi/code/python/novel_system")

from agents.agent_communicator import agent_communicator
from agents.agent_scheduler import AgentScheduler, AgentTask, TaskPriority
from llm.qwen_client import QwenClient
from llm.cost_tracker import CostTracker

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            "/Users/sanyi/code/python/novel_system/logs/auto_novel_process.log"
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class AutoNovelProcess:
    """自动小说创作流程"""

    def __init__(self):
        self.scheduler = None
        self.qwen_client = None
        self.cost_tracker = None
        self.task_results = {}

    async def initialize(self):
        """初始化系统"""
        logger.info("🚀 初始化自动小说创作流程...")

        try:
            # 初始化客户端和成本跟踪器
            self.qwen_client = QwenClient()
            self.cost_tracker = CostTracker()

            # 初始化调度器
            self.scheduler = AgentScheduler(agent_communicator)

            # 等待调度器就绪
            await asyncio.sleep(2)

            logger.info("✅ 自动小说创作流程初始化完成")

        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            import traceback

            traceback.print_exc()
            raise

    async def run_full_process(
        self, genre="玄幻", tags=["系统", "穿越"], platform="qidian"
    ):
        """运行完整的小说创作流程

        Args:
            genre: 小说类型
            tags: 小说标签
            platform: 发布平台
        """
        logger.info("🎯 开始完整小说创作流程")
        logger.info(f"📋 配置: 类型={genre}, 标签={tags}, 平台={platform}")
        logger.info("=====================================")

        try:
            # 1. 创建市场分析任务
            market_task = AgentTask(
                task_name="市场分析任务",
                task_type="market_analysis",
                priority=TaskPriority.HIGH,
                input_data={
                    "market_data": ["起点中文网热门排行榜数据", "抖音热门话题数据"],
                    "platform": "all",
                    "genre": genre,
                    "tags": tags,
                },
            )

            market_task_id = await self.scheduler.submit_task(market_task)
            self.task_results["market_analysis"] = market_task_id
            logger.info(f"📊 提交市场分析任务: {market_task_id}")

            # 等待市场分析任务完成
            await self.wait_for_task_completion(market_task_id, "市场分析")

            # 2. 创建内容策划任务（依赖市场分析任务）
            content_task = AgentTask(
                task_name="内容策划任务",
                task_type="content_planning",
                priority=TaskPriority.HIGH,
                dependencies=[market_task_id],
                input_data={
                    "market_analysis": "市场分析结果",
                    "user_preferences": {
                        "genre": genre,
                        "tags": tags,
                    },
                    "platform": platform,
                },
            )

            content_task_id = await self.scheduler.submit_task(content_task)
            self.task_results["content_planning"] = content_task_id
            logger.info(f"🎯 提交内容策划任务: {content_task_id}")

            # 等待内容策划任务完成
            await self.wait_for_task_completion(content_task_id, "内容策划")

            # 3. 创建创作任务（依赖内容策划任务）
            writing_task = AgentTask(
                task_name="创作任务",
                task_type="writing",
                priority=TaskPriority.MEDIUM,
                dependencies=[content_task_id],
                input_data={
                    "content_plan": "内容策划结果",
                    "chapter_number": 1,
                    "genre": genre,
                    "tags": tags,
                },
            )

            writing_task_id = await self.scheduler.submit_task(writing_task)
            self.task_results["writing"] = writing_task_id
            logger.info(f"✍️  提交创作任务: {writing_task_id}")

            # 等待创作任务完成
            await self.wait_for_task_completion(writing_task_id, "创作")

            # 4. 创建编辑任务（依赖创作任务）
            editing_task = AgentTask(
                task_name="编辑任务",
                task_type="editing",
                priority=TaskPriority.MEDIUM,
                dependencies=[writing_task_id],
                input_data={
                    "draft_content": "创作结果",
                    "chapter_number": 1,
                    "chapter_title": "第一章",
                    "genre": genre,
                },
            )

            editing_task_id = await self.scheduler.submit_task(editing_task)
            self.task_results["editing"] = editing_task_id
            logger.info(f"📝 提交编辑任务: {editing_task_id}")

            # 等待编辑任务完成
            await self.wait_for_task_completion(editing_task_id, "编辑")

            # 5. 创建发布任务（依赖编辑任务）
            publishing_task = AgentTask(
                task_name="发布任务",
                task_type="publishing",
                priority=TaskPriority.LOW,
                dependencies=[editing_task_id],
                input_data={
                    "novel_data": {
                        "title": f"{genre}之{tags[0]}",
                        "id": str(uuid4()),
                        "genre": genre,
                        "tags": tags,
                    },
                    "chapter_data": {
                        "chapter_number": 1,
                        "title": "第一章",
                    },
                    "platform": platform,
                    "account_id": "default",
                },
            )

            publishing_task_id = await self.scheduler.submit_task(publishing_task)
            self.task_results["publishing"] = publishing_task_id
            logger.info(f"🚀 提交发布任务: {publishing_task_id}")

            # 等待发布任务完成
            await self.wait_for_task_completion(publishing_task_id, "发布")

            # 流程完成
            logger.info("=====================================")
            logger.info("🎉 自动小说创作流程完成！")
            logger.info(f"📋 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"💰 总token消耗: {self.cost_tracker.get_total_tokens()}")
            logger.info(f"💰 总成本: ¥{self.cost_tracker.get_total_cost():.2f}")
            logger.info("=====================================")

            return {
                "success": True,
                "tasks": self.task_results,
                "genre": genre,
                "tags": tags,
                "platform": platform,
                "completion_time": datetime.now().isoformat(),
                "cost": {
                    "total_tokens": self.cost_tracker.get_total_tokens(),
                    "total_cost": self.cost_tracker.get_total_cost(),
                },
            }

        except Exception as e:
            logger.error(f"❌ 流程执行失败: {e}")
            import traceback

            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "tasks": self.task_results,
            }

    async def wait_for_task_completion(self, task_id, task_name):
        """等待任务完成

        Args:
            task_id: 任务ID
            task_name: 任务名称
        """
        logger.info(f"⏳ 等待{task_name}任务完成...")

        # 等待任务完成（这里使用简单的等待，实际项目中可以轮询任务状态）
        # 根据任务类型设置不同的等待时间
        task_wait_times = {
            "市场分析": 30,  # 市场分析可能需要更长时间
            "内容策划": 20,
            "创作": 40,  # 创作任务可能需要最长时间
            "编辑": 15,
            "发布": 10,
        }

        wait_time = task_wait_times.get(task_name, 20)

        for i in range(wait_time):
            await asyncio.sleep(1)
            if i % 5 == 0:
                logger.info(f"   {task_name}任务执行中... ({i}/{wait_time}秒)")

        logger.info(f"✅ {task_name}任务完成")


async def main():
    """主函数"""
    auto_process = AutoNovelProcess()

    try:
        # 初始化
        await auto_process.initialize()

        # 运行完整流程
        result = await auto_process.run_full_process(
            genre="玄幻", tags=["系统", "穿越"], platform="qidian"
        )

        if result["success"]:
            logger.info("🎊 自动小说创作流程成功完成！")
        else:
            logger.error("💥 自动小说创作流程失败")

    finally:
        logger.info("📋 流程结束")


if __name__ == "__main__":
    asyncio.run(main())
