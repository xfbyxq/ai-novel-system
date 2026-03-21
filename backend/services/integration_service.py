"""集成服务 - 负责协调所有模块的工作，实现端到端的自动化流程"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.automation_service import AutomationService
from backend.services.generation_service import GenerationService
from backend.services.publishing_service import PublishingService
from core.models.novel import Novel

logger = logging.getLogger(__name__)


class IntegrationService:
    """集成服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.automation = AutomationService(db)
        self.generation = GenerationService(db)
        self.publishing = PublishingService(db)

    async def run_end_to_end_workflow(
        self,
        config: Dict[str, Any] = None,
        novel_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """运行端到端的自动化小说创作和发布工作流

        Args:
            config: 工作流配置
            novel_id: 小说ID，如果为None则创建新小说

        Returns:
            工作流执行结果
        """
        if config is None:
            config = {}

        workflow_id = str(uuid4())
        logger.info(f"🚀 开始端到端自动化工作流: {workflow_id}")

        try:
            # 1. 运行自动化小说创建流程
            logger.info("📚 开始自动化小说创建流程")
            novel_creation_result = await self.automation.run_automated_novel_creation(
                novel_id=novel_id,
                config=config,
            )

            if novel_creation_result.get("status") != "completed":
                raise Exception(f"小说创建失败: {novel_creation_result.get('error')}")

            # 获取小说ID
            created_novel_id = UUID(novel_creation_result.get("novel_id"))

            # 2. 模拟市场分析报告
            logger.info("📊 生成市场分析报告")
            market_report = {
                "status": "completed",
                "platforms": [],
                "summary": {
                    "total_books_analyzed": 100,
                    "top_genres": ["都市", "玄幻", "仙侠"],
                    "top_tags": ["热门", "都市", "情感"],
                },
            }

            # 3. 执行发布（如果配置了）
            publish_result = None
            if config.get("auto_publish", False):
                logger.info("🚀 开始多平台发布流程")
                publish_result = await self._run_multi_platform_publish(
                    novel_id=created_novel_id,
                    config=config,
                )

            # 4. 生成综合报告
            comprehensive_report = {
                "workflow_id": workflow_id,
                "status": "completed",
                "start_time": datetime.now().isoformat(),
                "novel_info": {
                    "id": str(created_novel_id),
                    "title": novel_creation_result.get("novel_title"),
                },
                "novel_creation_result": novel_creation_result,
                "market_analysis_report": market_report,
                "publish_result": publish_result,
                "summary": {
                    "chapters_generated": novel_creation_result.get(
                        "chapters_generated", 0
                    ),
                    "platforms_analyzed": len(market_report.get("platforms", {})),
                    "costs": novel_creation_result.get("costs", {}),
                },
            }

            logger.info(f"🎉 端到端自动化工作流完成: {workflow_id}")
            return comprehensive_report

        except Exception as e:
            logger.error(f"❌ 端到端工作流失败: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "failed",
                "error": str(e),
                "start_time": datetime.now().isoformat(),
            }

    async def _run_multi_platform_publish(
        self,
        novel_id: UUID,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """运行多平台发布

        Args:
            novel_id: 小说ID
            config: 发布配置

        Returns:
            发布结果
        """
        platforms = config.get("publish_platforms", ["qidian"])
        publish_results = {}

        for platform in platforms:
            logger.info(f"📤 开始在 {platform} 平台发布")

            try:
                # 获取平台账号
                from sqlalchemy import select

                from core.models.platform_account import AccountStatus, PlatformAccount

                result = await self.db.execute(
                    select(PlatformAccount).where(
                        PlatformAccount.platform == platform,
                        PlatformAccount.status == AccountStatus.active,
                    )
                )
                account = result.scalar_one_or_none()

                if not account:
                    publish_results[platform] = {
                        "status": "failed",
                        "reason": f"No active {platform} account found",
                    }
                    continue

                # 获取小说信息
                novel_result = await self.db.execute(
                    select(Novel).where(Novel.id == novel_id)
                )
                novel = novel_result.scalar_one_or_none()

                if not novel:
                    publish_results[platform] = {
                        "status": "failed",
                        "reason": "Novel not found",
                    }
                    continue

                # 检查是否已在该平台创建书籍
                from core.models.publish_task import PublishTask

                existing_task_result = await self.db.execute(
                    select(PublishTask).where(
                        PublishTask.novel_id == novel_id,
                        PublishTask.platform == platform,
                    )
                )
                existing_task = existing_task_result.scalar_one_or_none()

                if existing_task and existing_task.platform_book_id:
                    # 已有书籍，直接发布章节
                    platform_book_id = existing_task.platform_book_id
                    logger.info(f"📖 书籍已在 {platform} 平台创建: {platform_book_id}")
                else:
                    # 创建新书籍
                    from core.models.publish_task import PublishTaskStatus, PublishType

                    create_book_task = PublishTask(
                        novel_id=novel_id,
                        account_id=account.id,
                        platform=platform,
                        publish_type=PublishType.create_book,
                        status=PublishTaskStatus.pending,
                    )

                    self.db.add(create_book_task)
                    await self.db.commit()
                    await self.db.refresh(create_book_task)

                    # 执行创建书籍任务
                    await self.publishing.run_publish_task(create_book_task.id)

                    # 等待任务完成
                    import asyncio

                    await asyncio.sleep(10)  # 给创建过程足够时间

                    # 刷新任务状态
                    await self.db.refresh(create_book_task)

                    if create_book_task.status != PublishTaskStatus.completed:
                        publish_results[platform] = {
                            "status": "failed",
                            "reason": f"Failed to create book on {platform}",
                            "error": create_book_task.error_message,
                        }
                        continue

                    platform_book_id = create_book_task.platform_book_id
                    logger.info(
                        f"📖 书籍在 {platform} 平台创建成功: {platform_book_id}"
                    )

                # 发布章节
                from core.models.chapter import Chapter

                chapters_result = await self.db.execute(
                    select(Chapter).where(Chapter.novel_id == novel_id)
                )
                chapters = chapters_result.scalars().all()

                if chapters:
                    # 发布最新章节
                    latest_chapter = max(chapters, key=lambda c: c.chapter_number)

                    publish_chapter_task = PublishTask(
                        novel_id=novel_id,
                        account_id=account.id,
                        platform=platform,
                        publish_type=PublishType.publish_chapter,
                        status=PublishTaskStatus.pending,
                        platform_book_id=platform_book_id,
                        config={
                            "chapter_number": latest_chapter.chapter_number,
                            "volume_number": latest_chapter.volume_number,
                        },
                    )

                    self.db.add(publish_chapter_task)
                    await self.db.commit()
                    await self.db.refresh(publish_chapter_task)

                    # 执行发布章节任务
                    await self.publishing.run_publish_task(publish_chapter_task.id)

                    # 等待任务完成
                    await asyncio.sleep(10)  # 给发布过程足够时间

                    # 刷新任务状态
                    await self.db.refresh(publish_chapter_task)

                    if publish_chapter_task.status == PublishTaskStatus.completed:
                        publish_results[platform] = {
                            "status": "success",
                            "platform_book_id": platform_book_id,
                            "chapters_published": 1,
                            "latest_chapter": latest_chapter.chapter_number,
                        }
                    else:
                        publish_results[platform] = {
                            "status": "failed",
                            "reason": f"Failed to publish chapter on {platform}",
                            "error": publish_chapter_task.error_message,
                        }
                else:
                    publish_results[platform] = {
                        "status": "failed",
                        "reason": "No chapters found to publish",
                    }

            except Exception as e:
                logger.error(f"在 {platform} 平台发布失败: {e}")
                publish_results[platform] = {
                    "status": "failed",
                    "reason": str(e),
                }

            # 平台发布间隔
            import asyncio

            await asyncio.sleep(5)

        return {
            "platforms": publish_results,
            "summary": {
                "total_platforms": len(platforms),
                "success_count": sum(
                    1 for r in publish_results.values() if r.get("status") == "success"
                ),
                "failed_count": sum(
                    1 for r in publish_results.values() if r.get("status") == "failed"
                ),
            },
        }

    async def get_workflow_history(
        self,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """获取工作流历史记录

        Args:
            limit: 限制数量
            offset: 偏移量

        Returns:
            工作流历史记录
        """
        # 实际实现中，这里应该从数据库获取工作流历史
        # 这里返回模拟数据
        return {
            "total": 0,
            "items": [],
        }

    async def get_workflow_detail(
        self,
        workflow_id: str,
    ) -> Dict[str, Any]:
        """获取工作流详情

        Args:
            workflow_id: 工作流ID

        Returns:
            工作流详情
        """
        # 实际实现中，这里应该从数据库获取工作流详情
        # 这里返回模拟数据
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "details": {},
        }
