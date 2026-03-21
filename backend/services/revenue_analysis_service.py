"""收益分析服务 - 负责分析收益数据并提供优化建议"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.chapter import Chapter
from core.models.chapter_publish import ChapterPublish, PublishStatus
from core.models.novel import Novel
from core.models.platform_account import PlatformAccount
from core.models.publish_task import PublishTask
from core.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)


class RevenueAnalysisService:
    """收益分析服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_novel_performance(
        self,
        novel_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """分析小说的性能数据

        Args:
            novel_id: 小说ID
            days: 分析天数

        Returns:
            小说性能分析结果
        """
        cutoff_date = date.today() - timedelta(days=days)

        # 获取小说信息
        novel_result = await self.db.execute(select(Novel).where(Novel.id == novel_id))
        novel = novel_result.scalar_one_or_none()

        if not novel:
            return {
                "error": "小说不存在",
            }

        # 获取章节信息
        chapters_result = await self.db.execute(
            select(Chapter)
            .where(
                Chapter.novel_id == novel_id,
                Chapter.created_at >= cutoff_date,
            )
            .order_by(Chapter.chapter_number)
        )
        chapters = chapters_result.scalars().all()

        # 获取发布记录
        publish_results = await self.db.execute(
            select(ChapterPublish).where(
                ChapterPublish.chapter_id.in_([c.id for c in chapters]),
                ChapterPublish.published_at >= cutoff_date,
            )
        )
        chapter_publishes = publish_results.scalars().all()

        # 获取发布任务
        publish_tasks_result = await self.db.execute(
            select(PublishTask).where(
                PublishTask.novel_id == novel_id,
                PublishTask.created_at >= cutoff_date,
            )
        )
        publish_tasks = publish_tasks_result.scalars().all()

        # 获取Token使用情况
        token_usage_result = await self.db.execute(
            select(TokenUsage).where(
                TokenUsage.novel_id == novel_id,
                TokenUsage.created_at >= cutoff_date,
            )
        )
        token_usages = token_usage_result.scalars().all()

        # 分析数据
        analysis = {
            "novel_id": str(novel_id),
            "novel_title": novel.title,
            "analysis_period": f"最近{days}天",
            "total_chapters": len(chapters),
            "total_word_count": sum(c.word_count for c in chapters),
            "publishing_statistics": {
                "total_publish_attempts": len(publish_tasks),
                "successful_publishes": len(
                    [
                        p
                        for p in chapter_publishes
                        if p.status == PublishStatus.published
                    ]
                ),
                "failed_publishes": len(
                    [p for p in chapter_publishes if p.status == PublishStatus.failed]
                ),
                "platform_distribution": {},
            },
            "cost_analysis": {
                "total_tokens_used": sum(t.total_tokens for t in token_usages),
                "total_cost": sum(t.estimated_cost for t in token_usages),
                "cost_per_chapter": 0,
            },
            "performance_metrics": {
                "average_chapter_length": 0,
                "publishing_success_rate": 0,
                "cost_efficiency": 0,
            },
            "optimization_suggestions": [],
        }

        # 计算出版平台分布
        for task in publish_tasks:
            platform = task.platform
            analysis["publishing_statistics"]["platform_distribution"][platform] = (
                analysis["publishing_statistics"]["platform_distribution"].get(
                    platform, 0
                )
                + 1
            )

        # 计算性能指标
        if chapters:
            analysis["performance_metrics"]["average_chapter_length"] = analysis[
                "total_word_count"
            ] / len(chapters)

        total_publishes = len(chapter_publishes)
        if total_publishes:
            successful_publishes = len(
                [p for p in chapter_publishes if p.status == PublishStatus.published]
            )
            analysis["performance_metrics"]["publishing_success_rate"] = (
                successful_publishes / total_publishes * 100
            )

        total_cost = analysis["cost_analysis"]["total_cost"]
        if total_cost > 0 and analysis["total_word_count"] > 0:
            analysis["performance_metrics"]["cost_efficiency"] = (
                analysis["total_word_count"] / total_cost
            )

        if len(chapters):
            analysis["cost_analysis"]["cost_per_chapter"] = total_cost / len(chapters)

        # 生成优化建议
        analysis["optimization_suggestions"] = self._generate_optimization_suggestions(
            analysis
        )

        return analysis

    async def analyze_platform_performance(
        self,
        platform: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """分析平台的性能数据

        Args:
            platform: 平台名称
            days: 分析天数

        Returns:
            平台性能分析结果
        """
        cutoff_date = date.today() - timedelta(days=days)

        # 获取平台账号
        accounts_result = await self.db.execute(
            select(PlatformAccount).where(
                PlatformAccount.platform == platform,
            )
        )
        accounts = accounts_result.scalars().all()

        # 获取发布任务
        publish_tasks_result = await self.db.execute(
            select(PublishTask).where(
                PublishTask.platform == platform,
                PublishTask.created_at >= cutoff_date,
            )
        )
        publish_tasks = publish_tasks_result.scalars().all()

        # 获取发布记录
        chapter_publishes_result = await self.db.execute(
            select(ChapterPublish).where(
                ChapterPublish.published_at >= cutoff_date,
            )
        )
        chapter_publishes = chapter_publishes_result.scalars().all()

        # 分析数据
        analysis = {
            "platform": platform,
            "analysis_period": f"最近{days}天",
            "total_accounts": len(accounts),
            "total_publish_tasks": len(publish_tasks),
            "successful_tasks": len(
                [t for t in publish_tasks if t.status == "completed"]
            ),
            "failed_tasks": len([t for t in publish_tasks if t.status == "failed"]),
            "total_chapter_publishes": len(chapter_publishes),
            "successful_chapter_publishes": len(
                [p for p in chapter_publishes if p.status == PublishStatus.published]
            ),
            "failed_chapter_publishes": len(
                [p for p in chapter_publishes if p.status == PublishStatus.failed]
            ),
            "publish_success_rate": 0,
            "task_success_rate": 0,
            "optimization_suggestions": [],
        }

        # 计算成功率
        if publish_tasks:
            analysis["task_success_rate"] = (
                analysis["successful_tasks"] / len(publish_tasks) * 100
            )

        if chapter_publishes:
            analysis["publish_success_rate"] = (
                analysis["successful_chapter_publishes"] / len(chapter_publishes) * 100
            )

        # 生成优化建议
        analysis["optimization_suggestions"] = (
            self._generate_platform_optimization_suggestions(analysis)
        )

        return analysis

    async def generate_revenue_forecast(
        self,
        novel_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """生成小说的收益预测

        Args:
            novel_id: 小说ID
            days: 预测天数

        Returns:
            收益预测结果
        """
        # 获取小说性能数据
        performance_data = await self.analyze_novel_performance(novel_id, days=60)

        if "error" in performance_data:
            return performance_data

        # 基于历史数据生成预测
        forecast = {
            "novel_id": str(novel_id),
            "novel_title": performance_data.get("novel_title"),
            "forecast_period": f"未来{days}天",
            "historical_data": {
                "total_chapters": performance_data.get("total_chapters"),
                "total_word_count": performance_data.get("total_word_count"),
                "total_cost": performance_data.get("cost_analysis", {}).get(
                    "total_cost"
                ),
                "publishing_success_rate": performance_data.get(
                    "performance_metrics", {}
                ).get("publishing_success_rate"),
            },
            "forecast": {
                "expected_chapters": int(
                    performance_data.get("total_chapters", 0) * days / 60
                ),
                "expected_word_count": int(
                    performance_data.get("total_word_count", 0) * days / 60
                ),
                "expected_cost": float(
                    performance_data.get("cost_analysis", {}).get("total_cost", 0)
                )
                * days
                / 60,
                "expected_revenue": 0,  # 这里需要根据实际情况实现
                "expected_roi": 0,  # 这里需要根据实际情况实现
            },
            "optimization_tips": [],
        }

        # 生成优化建议
        forecast["optimization_tips"] = self._generate_revenue_optimization_tips(
            forecast
        )

        return forecast

    async def get_content_optimization_suggestions(
        self,
        novel_id: UUID,
    ) -> Dict[str, Any]:
        """获取内容优化建议

        Args:
            novel_id: 小说ID

        Returns:
            内容优化建议
        """
        # 获取小说信息
        novel_result = await self.db.execute(select(Novel).where(Novel.id == novel_id))
        novel = novel_result.scalar_one_or_none()

        if not novel:
            return {
                "error": "小说不存在",
            }

        # 获取章节信息
        chapters_result = await self.db.execute(
            select(Chapter).where(Chapter.novel_id == novel_id)
        )
        chapters = chapters_result.scalars().all()

        # 分析内容
        analysis = {
            "novel_id": str(novel_id),
            "novel_title": novel.title,
            "genre": novel.genre,
            "total_chapters": len(chapters),
            "average_chapter_length": (
                sum(c.word_count for c in chapters) / len(chapters) if chapters else 0
            ),
            "optimization_suggestions": [],
        }

        # 生成内容优化建议
        analysis["optimization_suggestions"] = (
            self._generate_content_optimization_suggestions(analysis)
        )

        return analysis

    def _generate_optimization_suggestions(
        self,
        analysis: Dict[str, Any],
    ) -> List[str]:
        """生成优化建议

        Args:
            analysis: 分析结果

        Returns:
            优化建议列表
        """
        suggestions = []

        # 基于发布成功率的建议
        publish_success_rate = analysis.get("performance_metrics", {}).get(
            "publishing_success_rate", 0
        )
        if publish_success_rate < 80:
            suggestions.append("发布成功率较低，建议检查平台账号状态和网络连接")

        # 基于成本效率的建议
        cost_efficiency = analysis.get("performance_metrics", {}).get(
            "cost_efficiency", 0
        )
        if cost_efficiency < 1000:
            suggestions.append("成本效率较低，建议优化提示词和生成参数以减少Token使用")

        # 基于章节长度的建议
        avg_chapter_length = analysis.get("performance_metrics", {}).get(
            "average_chapter_length", 0
        )
        if avg_chapter_length < 1000:
            suggestions.append("章节长度偏短，建议增加每章内容以提高读者体验")
        elif avg_chapter_length > 5000:
            suggestions.append("章节长度偏长，建议适当缩短以提高更新频率")

        # 基于发布频率的建议
        total_chapters = analysis.get("total_chapters", 0)
        if total_chapters < 5:
            suggestions.append("更新频率较低，建议增加更新频率以保持读者粘性")

        return suggestions

    def _generate_platform_optimization_suggestions(
        self,
        analysis: Dict[str, Any],
    ) -> List[str]:
        """生成平台优化建议

        Args:
            analysis: 平台分析结果

        Returns:
            平台优化建议列表
        """
        suggestions = []

        # 基于任务成功率的建议
        task_success_rate = analysis.get("task_success_rate", 0)
        if task_success_rate < 80:
            suggestions.append(
                f"{analysis['platform']}平台任务成功率较低，建议检查API稳定性和账号权限"
            )

        # 基于发布成功率的建议
        publish_success_rate = analysis.get("publish_success_rate", 0)
        if publish_success_rate < 80:
            suggestions.append(
                f"{analysis['platform']}平台发布成功率较低，建议优化发布内容格式和时机"
            )

        # 基于账号数量的建议
        total_accounts = analysis.get("total_accounts", 0)
        if total_accounts == 0:
            suggestions.append(
                f"未发现{analysis['platform']}平台账号，建议添加账号以启用发布功能"
            )
        elif total_accounts < 2:
            suggestions.append(
                f"{analysis['platform']}平台账号数量较少，建议添加备用账号以提高发布稳定性"
            )

        return suggestions

    def _generate_revenue_optimization_tips(
        self,
        forecast: Dict[str, Any],
    ) -> List[str]:
        """生成收益优化建议

        Args:
            forecast: 收益预测

        Returns:
            收益优化建议列表
        """
        tips = []

        # 基于成本的建议
        expected_cost = forecast.get("forecast", {}).get("expected_cost", 0)
        if expected_cost > 100:
            tips.append("预计成本较高，建议优化生成参数和内容长度以控制成本")

        # 基于发布频率的建议
        expected_chapters = forecast.get("forecast", {}).get("expected_chapters", 0)
        if expected_chapters < 10:
            tips.append("预计更新频率较低，建议增加更新频率以提高读者粘性和收益")

        # 基于内容质量的建议
        tips.append("建议定期分析读者反馈，调整内容方向以提高用户满意度")
        tips.append("建议关注市场热点，及时调整内容题材以适应市场需求")

        return tips

    def _generate_content_optimization_suggestions(
        self,
        analysis: Dict[str, Any],
    ) -> List[str]:
        """生成内容优化建议

        Args:
            analysis: 内容分析结果

        Returns:
            内容优化建议列表
        """
        suggestions = []

        # 基于章节长度的建议
        avg_chapter_length = analysis.get("average_chapter_length", 0)
        if avg_chapter_length < 1500:
            suggestions.append("章节长度偏短，建议增加每章内容以提供更丰富的阅读体验")
        elif avg_chapter_length > 4000:
            suggestions.append(
                "章节长度偏长，建议适当缩短章节或增加章节数量以提高更新频率"
            )

        # 基于类型的建议
        genre = analysis.get("genre", "")
        if genre == "都市":
            suggestions.append("都市题材建议增加现实感和情感共鸣，贴近读者生活")
        elif genre == "玄幻":
            suggestions.append("玄幻题材建议构建独特的世界观，增加想象力和创新元素")
        elif genre == "科幻":
            suggestions.append("科幻题材建议注重科学逻辑，增加前沿科技元素和前瞻性思考")

        # 通用建议
        suggestions.append("建议保持稳定的更新频率，建立读者阅读习惯")
        suggestions.append("建议定期与读者互动，收集反馈以调整内容方向")
        suggestions.append("建议关注市场热点，适当融入流行元素以提高作品吸引力")

        return suggestions
