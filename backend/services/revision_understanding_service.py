"""修订理解服务 - 理解用户反馈并生成修改方案."""

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from core.models import Character, Chapter, WorldSetting, PlotOutline, RevisionPlan
from core.models.revision_plan import RevisionPlanStatus
from llm.qwen_client import QwenClient


class RevisionUnderstandingService:
    """修订理解服务 - 理解用户反馈并生成修改方案."""

    # LLM分析的系统提示
    SYSTEM_PROMPT = """你是专业的小说编辑，擅长分析用户的修订反馈。

请分析用户的修订反馈，理解其意图，并生成修改方案。

## 输出格式
返回JSON格式：
{
    "intent": "修改意图描述，如：修改角色'张三'的性格设定",
    "confidence": 0.85,  // 理解置信度 0-1
    "target_type": "character|chapter|world_setting|outline|plot",  // 修改目标类型
    "targets": [
        {
            "type": "character",
            "target_name": "张三",
            "field": "personality",
            "issue": "性格前后不一致"
        }
    ],
    "changes": [
        {
            "target_type": "character",
            "field": "personality",
            "old_value": "原性格描述",
            "new_value": "新性格描述",
            "reasoning": "统一为稳重性格，保持角色一致性"
        }
    ],
    "affected_chapters": [5, 6, 7],  // 可能受影响的章节
    "suggestions": ["建议用户确认修改方案后再执行"]
}
"""

    def __init__(self, db: AsyncSession, llm: Optional[QwenClient] = None):
        """初始化服务.

        Args:
            db: 数据库会话
            llm: LLM客户端，如果为None则使用简化分析
        """
        self.db = db
        self.llm = llm

    async def understand_feedback(
        self,
        user_feedback: str,
        novel_id: str,
    ) -> RevisionPlan:
        """理解用户反馈，生成修订计划.

        核心流程：
        1. 加载小说上下文（角色、章节摘要、世界观）
        2. LLM分析反馈意图
        3. 定位修改目标（哪个角色？哪几章？）
        4. 生成修改方案
        5. 保存修订计划

        Args:
            user_feedback: 用户反馈文本
            novel_id: 小说ID

        Returns:
            RevisionPlan: 创建的修订计划
        """
        # Step 1: 加载上下文
        context = await self._load_novel_context(novel_id)

        # Step 2: LLM分析
        analysis = await self._analyze_with_llm(user_feedback, context)

        # Step 3: 补充目标ID
        targets = self._enrich_targets(analysis.get("targets", []), context)

        # Step 4: 评估影响
        impact = await self._assess_impact(analysis, targets, context)

        # Step 5: 创建修订计划
        plan = RevisionPlan(
            novel_id=UUID(novel_id),
            feedback_text=user_feedback,
            understood_intent=analysis.get("intent", ""),
            confidence=analysis.get("confidence", 0.5),
            targets=targets,
            proposed_changes=analysis.get("changes", []),
            impact_assessment=impact,
            status=RevisionPlanStatus.pending.value,
        )

        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)

        return plan

    async def _load_novel_context(self, novel_id: str) -> dict:
        """加载小说上下文用于理解反馈.

        Args:
            novel_id: 小说ID

        Returns:
            dict: 包含角色、章节、世界观的上下文
        """
        novel_uuid = UUID(novel_id)

        # 加载角色列表
        stmt_chars = select(Character).where(Character.novel_id == novel_uuid)
        result_chars = await self.db.execute(stmt_chars)
        characters = result_chars.scalars().all()

        # 加载章节摘要
        stmt_chapters = (
            select(Chapter)
            .where(Chapter.novel_id == novel_uuid)
            .order_by(Chapter.chapter_number)
        )
        result_chapters = await self.db.execute(stmt_chapters)
        chapters = result_chapters.scalars().all()

        # 加载世界观
        stmt_ws = select(WorldSetting).where(WorldSetting.novel_id == novel_uuid)
        result_ws = await self.db.execute(stmt_ws)
        world_setting = result_ws.scalar_one_or_none()

        # 加载大纲
        stmt_outline = select(PlotOutline).where(PlotOutline.novel_id == novel_uuid)
        result_outline = await self.db.execute(stmt_outline)
        plot_outline = result_outline.scalar_one_or_none()

        return {
            "novel_id": novel_id,
            "characters": [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "role_type": c.role_type,
                    "personality": c.personality,
                    "background": c.background,
                    "first_appearance_chapter": c.first_appearance_chapter,
                }
                for c in characters
            ],
            "chapters": [
                {
                    "id": str(c.id),
                    "chapter_number": c.chapter_number,
                    "title": c.title,
                    "summary": getattr(c, "summary", None),
                    "plot_points": getattr(c, "plot_points", None),
                }
                for c in chapters
            ],
            "world_setting": {
                "power_system": world_setting.power_system if world_setting else None,
                "factions": world_setting.factions if world_setting else None,
            }
            if world_setting
            else None,
            "plot_outline": (
                {
                    "main_plot": plot_outline.main_plot if plot_outline else None,
                    "volumes": plot_outline.volumes if plot_outline else None,
                }
                if plot_outline
                else None
            ),
        }

    async def _analyze_with_llm(self, feedback: str, context: dict) -> dict:
        """使用LLM分析用户反馈.

        Args:
            feedback: 用户反馈文本
            context: 小说上下文

        Returns:
            dict: 分析结果
        """
        if self.llm is None:
            # 无LLM时使用简化分析
            return self._simple_analyze(feedback, context)

        # 构建分析prompt
        prompt = self._build_analysis_prompt(feedback, context)

        try:
            response = await self.llm.chat([{"role": "user", "content": prompt}])
            result = json.loads(response)
            return result
        except (json.JSONDecodeError, Exception):
            # 解析失败时使用简化分析
            return self._simple_analyze(feedback, context)

    def _build_analysis_prompt(self, feedback: str, context: dict) -> str:
        """构建分析prompt."""
        # 格式化角色列表
        characters_text = "\n".join(
            f"- {c['name']} ({c['role_type']}): {c.get('personality', '未设定')}"
            for c in context.get("characters", [])
        )

        # 格式化章节列表
        chapters_text = "\n".join(
            f"- 第{c['chapter_number']}章: {c.get('title', '未命名')}"
            for c in context.get("chapters", [])[-10:]  # 只显示最近10章
        )

        prompt = f"""{self.SYSTEM_PROMPT}

## 用户反馈
{feedback}

## 小说上下文
### 角色列表
{characters_text or "（暂无角色）"}

### 章节列表
{chapters_text or "（暂无章节）"}
"""
        return prompt

    def _simple_analyze(self, feedback: str, context: dict) -> dict:
        """简化分析 - 无LLM时的fallback.

        Args:
            feedback: 用户反馈
            context: 上下文

        Returns:
            dict: 简化的分析结果
        """
        feedback_lower = feedback.lower()

        # 尝试识别目标类型
        target_type = "character"
        if "世界观" in feedback or "设定" in feedback:
            target_type = "world_setting"
        elif "大纲" in feedback or "情节" in feedback:
            target_type = "outline"
        elif "章节" in feedback or "第" in feedback:
            target_type = "chapter"

        # 尝试识别角色名
        target_name = None
        for char in context.get("characters", []):
            if char["name"] in feedback:
                target_name = char["name"]
                break

        # 构建简化结果
        targets = []
        if target_name:
            targets.append(
                {
                    "type": "character",
                    "target_name": target_name,
                    "field": "personality",
                    "issue": "用户反馈需要修改",
                }
            )

        return {
            "intent": f"理解用户反馈：{feedback[:50]}...",
            "confidence": 0.5,
            "target_type": target_type,
            "targets": targets,
            "changes": [],
            "affected_chapters": [],
            "suggestions": ["请用户提供更多细节"],
        }

    def _enrich_targets(
        self, targets: list[dict], context: dict
    ) -> list[dict]:
        """补充目标的ID信息.

        Args:
            targets: 目标列表
            context: 上下文

        Returns:
            list: 补充ID后的目标列表
        """
        characters_map = {c["name"]: c for c in context.get("characters", [])}
        chapters_map = {c["chapter_number"]: c for c in context.get("chapters", [])}

        enriched = []
        for target in targets:
            enriched_target = target.copy()

            if target.get("type") == "character":
                name = target.get("target_name")
                if name in characters_map:
                    enriched_target["target_id"] = characters_map[name]["id"]
                    enriched_target["current_value"] = characters_map[name].get(
                        "personality", ""
                    )

            elif target.get("type") == "chapter":
                chapter_num = target.get("chapter_number")
                if chapter_num in chapters_map:
                    enriched_target["target_id"] = chapters_map[chapter_num]["id"]

            enriched.append(enriched_target)

        return enriched

    async def _assess_impact(
        self, analysis: dict, targets: list[dict], context: dict
    ) -> dict:
        """评估修改的影响范围.

        Args:
            analysis: 分析结果
            targets: 目标列表
            context: 上下文

        Returns:
            dict: 影响评估
        """
        affected_chapters = set()
        affected_characters = set()

        # 分析涉及的章节
        for target in targets:
            if target.get("type") == "character":
                char_name = target.get("target_name")
                # 查找角色出现的章节
                for char in context.get("characters", []):
                    if char["name"] == char_name:
                        chapter = char.get("first_appearance_chapter")
                        if chapter:
                            # 影响从首次出场到最新的章节
                            for c in context.get("chapters", []):
                                if c["chapter_number"] >= chapter:
                                    affected_chapters.add(c["chapter_number"])

            elif target.get("type") == "chapter":
                chapter_num = target.get("chapter_number")
                if chapter_num:
                    affected_chapters.add(chapter_num)

        return {
            "affected_chapters": sorted(list(affected_chapters)),
            "affected_characters": list(affected_characters),
            "severity": "high" if len(affected_chapters) > 3 else "medium"
            if affected_chapters
            else "low",
        }

    def format_plan_for_display(self, plan: RevisionPlan) -> str:
        """格式化修订计划用于显示.

        Args:
            plan: 修订计划

        Returns:
            str: 格式化的文本
        """
        lines = [
            "我理解了您的反馈。",
            "",
            "【AI分析】",
            f"- 理解置信度：{plan.confidence:.0%}",
            f"- 修改类型：{plan.targets[0]['type'] if plan.targets else '未知'}",
            "",
        ]

        if plan.targets:
            lines.append("【涉及对象】")
            for target in plan.targets:
                lines.append(f"- {target.get('target_name', '未知')}: {target.get('issue', '')}")
            lines.append("")

        if plan.proposed_changes:
            lines.append("【建议修改】")
            for i, change in enumerate(plan.proposed_changes, 1):
                lines.append(f"{i}. {change.get('reasoning', '')}")
            lines.append("")

        if plan.impact_assessment:
            chapters = plan.impact_assessment.get("affected_chapters", [])
            if chapters:
                lines.append(f"【影响范围】")
                lines.append(f"- 可能影响章节：第{min(chapters)}-{max(chapters)}章")
                lines.append("")

        lines.append("是否执行此修改？")
        lines.append("(回复'是'确认执行，'否'取消，或提出修改意见)")

        return "\n".join(lines)
