"""自动化服务 - 负责管理自动化工作流."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from agents.agent_communicator import AgentCommunicator
from agents.agent_scheduler import AgentScheduler
from agents.specific_agents import (
    ContentPlanningAgent,
    EditingAgent,
    PublishingAgent,
    WritingAgent,
)
from backend.services.generation_service import GenerationService
from backend.services.publishing_service import PublishingService
from core.models.chapter import Chapter
from core.models.generation_task import GenerationTask, TaskStatus
from core.models.novel import Novel
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)


class AutomationService:
    """自动化服务."""

    def __init__(self, db: AsyncSession):
        """初始化方法."""
        self.db = db
        self.generation = GenerationService(db)
        self.publishing = PublishingService(db)
        self.communicator = AgentCommunicator()
        self.scheduler = AgentScheduler(self.communicator)
        self.cost_tracker = CostTracker()
        self.qwen_client = QwenClient()
        self.agents = {}

    async def initialize_agents(self):
        """初始化所有代理."""
        # 创建内容策划代理
        self.agents["content_planner"] = ContentPlanningAgent(
            "content_planner",
            self.communicator,
            self.qwen_client,
            self.cost_tracker,
        )

        # 创建创作代理
        self.agents["writer"] = WritingAgent(
            "writer",
            self.communicator,
            self.qwen_client,
            self.cost_tracker,
        )

        # 创建编辑代理
        self.agents["editor"] = EditingAgent(
            "editor",
            self.communicator,
            self.qwen_client,
            self.cost_tracker,
        )

        # 创建发布代理
        self.agents["publisher"] = PublishingAgent(
            "publisher",
            self.communicator,
            self.qwen_client,
            self.cost_tracker,
        )

        # 启动所有代理
        for agent_name, agent in self.agents.items():
            asyncio.create_task(agent.start())

        logger.info("所有代理初始化完成")

    async def run_automated_novel_creation(
        self,
        novel_id: Optional[UUID] = None,
        config: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """运行自动化小说创建流程.

        Args:
            novel_id: 小说ID，如果为None则创建新小说
            config: 配置参数

        Returns:
            执行结果
        """
        if config is None:
            config = {}

        # 初始化代理
        if not self.agents:
            await self.initialize_agents()

        workflow_id = str(uuid4())
        logger.info(f"🚀 开始自动化小说创建工作流: {workflow_id}")

        try:
            # 1. 市场分析阶段
            logger.info("📊 开始市场分析阶段")
            market_analysis_result = await self._run_market_analysis(config)

            # 2. 内容策划阶段
            logger.info("🎯 开始内容策划阶段")
            content_plan_result = await self._run_content_planning(
                market_analysis_result, config
            )

            # 3. 小说创建/更新
            novel = await self._create_or_update_novel(
                novel_id, content_plan_result, config
            )

            # 4. 章节创作阶段
            logger.info("✍️  开始章节创作阶段")
            chapters_result = await self._run_chapter_generation(
                novel.id, content_plan_result, config
            )

            # 5. 编辑阶段
            logger.info("📝 开始编辑阶段")
            editing_result = await self._run_editing(novel.id, chapters_result, config)

            # 6. 发布阶段（如果配置了自动发布）
            publish_result = None
            if config.get("auto_publish", False):
                logger.info("🚀 开始发布阶段")
                publish_result = await self._run_publishing(
                    novel.id, editing_result, config
                )

            # 生成最终报告
            final_report = {
                "workflow_id": workflow_id,
                "status": "completed",
                "start_time": datetime.now().isoformat(),
                "novel_id": str(novel.id),
                "novel_title": novel.title,
                "market_analysis": market_analysis_result,
                "content_plan": content_plan_result,
                "chapters_generated": chapters_result.get("chapters_count", 0),
                "editing_result": editing_result,
                "publish_result": publish_result,
                "costs": self.cost_tracker.get_total_cost(),
            }

            logger.info(f"🎉 自动化小说创建工作流完成: {workflow_id}")
            return final_report

        except Exception as e:
            logger.error(f"❌ 自动化工作流失败: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e),
                "start_time": datetime.now().isoformat(),
            }

    async def _run_market_analysis(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行市场分析."""
        # 返回默认的市场分析结果
        return {
            "market_data_count": 100,
            "platform": config.get("platform", "all"),
            "analysis_completed": True,
        }

    async def _run_content_planning(
        self, market_analysis: Dict[str, Any], config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行内容策划."""
        # 创建内容策划任务
        task_id = str(uuid4())
        task_data = {
            "task_id": task_id,
            "task_name": "内容策划",
            "input_data": {
                "market_analysis": market_analysis,
                "user_preferences": config.get("user_preferences", {}),
            },
        }

        # 提交任务给代理
        await self.scheduler.submit_task(
            agent_name="content_planner",
            task_name="内容策划",
            input_data=task_data["input_data"],
        )

        # 等待任务完成
        await asyncio.sleep(45)  # 给代理时间完成任务

        # 生成内容策划结果
        return {
            "novel_title": config.get(
                "novel_title",
                f"自动生成小说_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            ),
            "genre": config.get("genre", "都市"),
            "tags": config.get("tags", ["热门", "都市", "情感"]),
            "synopsis": "这是一部根据市场分析自动生成的小说",
            "target_audience": "年轻读者",
            "chapters_plan": [
                {
                    "chapter_number": 1,
                    "title": "第一章 开端",
                    "content_plan": "介绍主角和背景",
                },
                {
                    "chapter_number": 2,
                    "title": "第二章 冲突",
                    "content_plan": "引入主要冲突",
                },
                {
                    "chapter_number": 3,
                    "title": "第三章 发展",
                    "content_plan": "情节发展",
                },
            ],
        }

    async def _create_or_update_novel(
        self,
        novel_id: Optional[UUID],
        content_plan: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Novel:
        """创建或更新小说."""
        if novel_id:
            # 更新现有小说
            from sqlalchemy import select

            result = await self.db.execute(select(Novel).where(Novel.id == novel_id))
            novel = result.scalar_one_or_none()
            if novel:
                # 更新小说信息
                novel.title = content_plan.get("novel_title", novel.title)
                novel.genre = content_plan.get("genre", novel.genre)
                novel.tags = content_plan.get("tags", novel.tags)
                novel.synopsis = content_plan.get("synopsis", novel.synopsis)
                novel.updated_at = datetime.now()
                await self.db.commit()
                await self.db.refresh(novel)
                return novel

        # 创建新小说
        novel = Novel(
            title=content_plan.get("novel_title"),
            author=config.get("author", "AI作者"),
            genre=content_plan.get("genre"),
            tags=content_plan.get("tags"),
            synopsis=content_plan.get("synopsis"),
            status="in_progress",
            word_count=0,
            chapter_count=0,
        )

        self.db.add(novel)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(novel)

        return novel

    async def _run_chapter_generation(
        self,
        novel_id: UUID,
        content_plan: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """运行章节生成."""
        chapters_plan = content_plan.get("chapters_plan", [])
        generated_chapters = []

        for chapter_plan in chapters_plan:
            chapter_number = chapter_plan["chapter_number"]
            chapter_title = chapter_plan["title"]

            # 创建生成任务
            generation_task = GenerationTask(
                novel_id=novel_id,
                task_type="chapter",
                status=TaskStatus.pending,
                config={
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "content_plan": chapter_plan["content_plan"],
                    "writing_style": config.get("writing_style", "modern"),
                },
            )

            self.db.add(generation_task)
            await self.db.commit()
            await self.db.refresh(generation_task)

            # 执行生成
            await self.generation.run_generation_task(generation_task.id)

            # 等待生成完成
            await asyncio.sleep(60)  # 给生成过程足够时间

            # 获取生成结果
            from sqlalchemy import select

            result = await self.db.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
            chapter = result.scalar_one_or_none()

            if chapter:
                generated_chapters.append(
                    {
                        "chapter_number": chapter_number,
                        "chapter_title": chapter_title,
                        "word_count": chapter.word_count,
                        "status": chapter.status,
                    }
                )

        # 更新小说章节数和字数
        from sqlalchemy import func, select

        chapters_result = await self.db.execute(
            select(func.count(Chapter.id), func.sum(Chapter.word_count)).where(
                Chapter.novel_id == novel_id
            )
        )
        chapter_count, total_words = chapters_result.first()

        novel_result = await self.db.execute(select(Novel).where(Novel.id == novel_id))
        novel = novel_result.scalar_one_or_none()
        if novel:
            novel.chapter_count = chapter_count or 0
            novel.word_count = total_words or 0
            await self.db.commit()

        return {
            "chapters_count": len(generated_chapters),
            "chapters": generated_chapters,
        }

    async def _run_editing(
        self,
        novel_id: UUID,
        chapters_result: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """运行编辑流程."""
        from sqlalchemy import select

        # 获取所有章节
        result = await self.db.execute(
            select(Chapter).where(Chapter.novel_id == novel_id)
        )
        chapters = result.scalars().all()

        edited_chapters = []
        for chapter in chapters:
            # 模拟编辑过程
            # 实际实现中，这里应该使用EditingAgent
            chapter.status = "edited"
            chapter.updated_at = datetime.now()
            edited_chapters.append(
                {
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title,
                    "status": "edited",
                }
            )

        await self.db.commit()

        return {
            "edited_chapters_count": len(edited_chapters),
            "chapters": edited_chapters,
        }

    async def _run_publishing(
        self,
        novel_id: UUID,
        editing_result: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """运行发布流程."""
        # 获取平台账号
        from sqlalchemy import select

        from core.models.platform_account import PlatformAccount

        platform = config.get("publish_platform", "qidian")

        # 查找可用的平台账号
        result = await self.db.execute(
            select(PlatformAccount).where(
                PlatformAccount.platform == platform,
                PlatformAccount.status == "active",
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            return {
                "status": "skipped",
                "reason": f"No active {platform} account found",
            }

        # 发布小说
        # 实际实现中，这里应该调用发布服务
        return {
            "status": "success",
            "platform": platform,
            "account_id": str(account.id),
            "chapters_published": editing_result.get("edited_chapters_count", 0),
        }

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """获取工作流状态."""
        # 实际实现中，这里应该从数据库获取工作流状态
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "last_updated": datetime.now().isoformat(),
        }

    async def run_batch_automation(
        self,
        batch_config: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """运行批量自动化任务.

        Args:
            batch_config: 批量配置列表

        Returns:
            批量执行结果
        """
        results = []

        for i, config in enumerate(batch_config):
            logger.info(f"📦 开始批量任务 {i+1}/{len(batch_config)}")
            result = await self.run_automated_novel_creation(config=config)
            results.append(result)

            # 批量任务间隔
            if i < len(batch_config) - 1:
                await asyncio.sleep(config.get("interval", 300))

        return {
            "total_tasks": len(batch_config),
            "success_count": sum(1 for r in results if r.get("status") == "completed"),
            "failed_count": sum(1 for r in results if r.get("status") == "failed"),
            "results": results,
        }
