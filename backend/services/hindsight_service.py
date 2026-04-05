"""Hindsight服务 - 事后回顾和策略追踪."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    HindsightExperience,
    StrategyEffectiveness,
    UserPreference,
    RevisionPlan,
)
from core.models.hindsight_memory import StrategyTrend, TaskType


class HindsightService:
    """事后回顾服务 - 核心的学习机制.

    核心功能：
    1. execute_review: 执行事后回顾，记录经验
    2. get_applicable_lessons: 获取适用于当前任务的过往经验
    3. record_strategy_result: 记录策略应用效果
    4. get_strategy_recommendations: 获取策略建议
    """

    # 分析的系统提示
    SYSTEM_PROMPT = """你是专业的小说编辑，擅长事后分析写作和修订任务。

给定一个任务的初始目标、实际结果和质量评分，请分析：

## 分析维度
1. **偏差分析**：计划与实际的偏差是什么？
2. **原因追溯**：偏差的根本原因是什么？
3. **成功策略**：哪些做法是有效的？
4. **失败策略**：哪些做法需要改进？
5. **改进建议**：下次如何做得更好？

## 输出格式
返回JSON格式：
{
    "deviations": [
        {"type": "未完成", "detail": "少了2个场景"}
    ],
    "reasons": ["对话太长", "场景切换频繁"],
    "lessons": ["简洁对话更有效", "场景切换不超过3次"],
    "successful_strategies": [
        {"name": "动作描写", "effectiveness": 0.8}
    ],
    "failed_strategies": [
        {"name": "长对话", "issue": "节奏拖沓"}
    ],
    "applied_strategies": ["动作描写", "短句节奏"]
}
"""

    def __init__(self, db: AsyncSession, llm: Optional[Any] = None):
        """初始化服务.

        Args:
            db: 数据库会话
            llm: LLM客户端
        """
        self.db = db
        self.llm = llm

    async def execute_review(
        self,
        novel_id: str,
        task_type: str,
        chapter_number: int = 0,
        initial_goal: Optional[str] = None,
        initial_plan: Optional[dict] = None,
        actual_result: Optional[str] = None,
        outcome_score: float = 0.0,
        applied_strategies: Optional[list[str]] = None,
        original_feedback: Optional[str] = None,
        revision_plan_id: Optional[str] = None,
    ) -> HindsightExperience:
        """执行事后回顾.

        Args:
            novel_id: 小说ID
            task_type: 任务类型 (planning/writing/revision)
            chapter_number: 章节号，0表示企划阶段
            initial_goal: 初始目标
            initial_plan: 初始计划
            actual_result: 实际结果
            outcome_score: 质量评分 (0-10)
            applied_strategies: 应用的策略列表
            original_feedback: 用户原始反馈
            revision_plan_id: 关联的修订计划ID

        Returns:
            HindsightExperience: 创建的回顾记录
        """
        # Step 1: LLM分析（如果可用）
        analysis = await self._analyze_outcome(
            initial_goal=initial_goal,
            initial_plan=initial_plan,
            actual_result=actual_result,
            outcome_score=outcome_score,
        )

        # Step 2: 检测反复模式
        pattern = await self._detect_pattern(novel_id, task_type, chapter_number)

        # Step 3: 创建回顾记录
        experience = HindsightExperience(
            novel_id=UUID(novel_id),
            revision_plan_id=UUID(revision_plan_id) if revision_plan_id else None,
            task_type=task_type,
            chapter_number=chapter_number,
            initial_goal=initial_goal,
            initial_plan=initial_plan,
            actual_result=actual_result,
            outcome_score=outcome_score,
            original_feedback=original_feedback,
            deviations=analysis.get("deviations", []),
            deviation_reasons=analysis.get("reasons", []),
            lessons_learned=analysis.get("lessons", []),
            successful_strategies=analysis.get("successful_strategies", []),
            failed_strategies=analysis.get("failed_strategies", []),
            recurring_pattern=pattern.get("pattern") if pattern else None,
            pattern_confidence=pattern.get("confidence") if pattern else None,
        )

        self.db.add(experience)
        await self.db.commit()
        await self.db.refresh(experience)

        # Step 4: 更新策略有效性
        if applied_strategies or analysis.get("applied_strategies"):
            strategies = applied_strategies or analysis.get("applied_strategies", [])
            await self._update_strategies(
                novel_id=novel_id,
                strategies=strategies,
                outcome_score=outcome_score,
                task_type=task_type,
                chapter_number=chapter_number,
            )

        return experience

    async def get_applicable_lessons(
        self,
        novel_id: str,
        task_type: str = "writing",
        current_chapter: int = 0,
        limit: int = 5,
    ) -> list[str]:
        """获取适用于当前任务的过往经验.

        Args:
            novel_id: 小说ID
            task_type: 任务类型
            current_chapter: 当前章节号
            limit: 返回数量限制

        Returns:
            list[str]: 经验教训列表
        """
        # 查询相关经验
        experiences = await self._query_experiences(
            novel_id=novel_id,
            task_type=task_type,
            current_chapter=current_chapter,
            limit=limit,
        )

        # 格式化经验
        lessons = []
        for exp in experiences:
            if exp.lessons_learned:
                for lesson in exp.lessons_learned:
                    lessons.append(f"【经验】{lesson}")

            if exp.recurring_pattern and exp.pattern_confidence and exp.pattern_confidence > 0.6:
                lessons.append(f"【模式预警】{exp.recurring_pattern}")

            if exp.improvement_suggestions:
                for suggestion in exp.improvement_suggestions[:1]:  # 只取一条
                    lessons.append(f"【建议】{suggestion}")

        return lessons[:limit]

    async def record_strategy_result(
        self,
        novel_id: str,
        strategy_name: str,
        strategy_type: str,
        target_dimension: str,
        effectiveness_score: float,
    ) -> StrategyEffectiveness:
        """记录策略应用结果.

        Args:
            novel_id: 小说ID
            strategy_name: 策略名称
            strategy_type: 策略类型
            target_dimension: 目标维度
            effectiveness_score: 效果评分 (0-1)

        Returns:
            StrategyEffectiveness: 更新后的策略记录
        """
        # 查找或创建策略记录
        strategy = await self._get_or_create_strategy(
            novel_id=novel_id,
            strategy_name=strategy_name,
            strategy_type=strategy_type,
            target_dimension=target_dimension,
        )

        # 更新统计
        strategy.application_count += 1
        if effectiveness_score > 0.6:
            strategy.success_count += 1

        # 更新效果分（移动平均）
        old_avg = strategy.avg_effectiveness or 0.5
        strategy.avg_effectiveness = old_avg * 0.7 + effectiveness_score * 0.3

        # 更新最近结果
        recent = list(strategy.recent_results or [])
        recent.append(effectiveness_score)
        if len(recent) > 5:
            recent = recent[-5:]
        strategy.recent_results = recent

        # 更新趋势
        strategy.trend = self._calculate_trend(recent)
        strategy.last_applied_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(strategy)

        return strategy

    async def get_strategy_recommendations(
        self,
        novel_id: str,
        target_dimension: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """获取策略建议 - 推荐最有效的策略.

        Args:
            novel_id: 小说ID
            target_dimension: 目标维度（可选）
            limit: 返回数量限制

        Returns:
            list[dict]: 策略建议列表
        """
        stmt = select(StrategyEffectiveness).where(
            StrategyEffectiveness.novel_id == UUID(novel_id)
        )

        if target_dimension:
            stmt = stmt.where(
                StrategyEffectiveness.target_dimension == target_dimension
            )

        stmt = stmt.order_by(StrategyEffectiveness.avg_effectiveness.desc())
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        strategies = result.scalars().all()

        return [
            {
                "strategy_name": s.strategy_name,
                "strategy_type": s.strategy_type,
                "target_dimension": s.target_dimension,
                "effectiveness": s.avg_effectiveness,
                "application_count": s.application_count,
                "success_count": s.success_count,
                "trend": s.trend,
            }
            for s in strategies
        ]

    async def record_user_preference(
        self,
        user_id: str,
        preference_type: str,
        preference_key: str,
        preference_value: Any,
        source: str = "explicit",
        novel_id: Optional[str] = None,
        confidence: float = 0.8,
    ) -> UserPreference:
        """记录用户偏好.

        Args:
            user_id: 用户ID
            preference_type: 偏好类型
            preference_key: 偏好键
            preference_value: 偏好值
            source: 来源 (explicit/inferred)
            novel_id: 小说ID（可选）
            confidence: 置信度

        Returns:
            UserPreference: 创建的偏好记录
        """
        # 检查是否已存在
        existing = await self._get_existing_preference(
            user_id=user_id,
            preference_key=preference_key,
            novel_id=novel_id,
        )

        if existing:
            # 更新现有偏好
            existing.preference_value = preference_value
            existing.confidence = min(existing.confidence + 0.1, 1.0)
            existing.source = source
            existing.last_activated_at = datetime.utcnow()
            existing.times_activated += 1

            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        # 创建新偏好
        preference = UserPreference(
            user_id=user_id,
            novel_id=UUID(novel_id) if novel_id else None,
            preference_type=preference_type,
            preference_key=preference_key,
            preference_value=preference_value,
            confidence=confidence,
            source=source,
            last_activated_at=datetime.utcnow(),
        )

        self.db.add(preference)
        await self.db.commit()
        await self.db.refresh(preference)

        return preference

    async def get_user_preferences(
        self,
        user_id: str,
        preference_types: Optional[list[str]] = None,
        min_confidence: float = 0.5,
    ) -> list[UserPreference]:
        """获取用户偏好列表.

        Args:
            user_id: 用户ID
            preference_types: 偏好类型列表（可选）
            min_confidence: 最低置信度

        Returns:
            list[UserPreference]: 偏好列表
        """
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.confidence >= min_confidence,
        )

        if preference_types:
            stmt = stmt.where(UserPreference.preference_type.in_(preference_types))

        stmt = stmt.order_by(UserPreference.confidence.desc())

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _analyze_outcome(
        self,
        initial_goal: Optional[str],
        initial_plan: Optional[dict],
        actual_result: Optional[str],
        outcome_score: float,
    ) -> dict:
        """LLM分析任务结果.

        Args:
            initial_goal: 初始目标
            initial_plan: 初始计划
            actual_result: 实际结果
            outcome_score: 质量评分

        Returns:
            dict: 分析结果
        """
        if not self.llm:
            return self._simple_analyze(outcome_score)

        prompt = f"""{self.SYSTEM_PROMPT}

## 初始目标
{initial_goal or "未设定"}

## 初始计划
{json.dumps(initial_plan, ensure_ascii=False, indent=2) if initial_plan else "未设定"}

## 实际结果
{actual_result or "未记录"}

## 质量评分
{outcome_score}/10
"""
        try:
            response = await self.llm.chat([{"role": "user", "content": prompt}])
            return json.loads(response)
        except (json.JSONDecodeError, Exception):
            return self._simple_analyze(outcome_score)

    def _simple_analyze(self, outcome_score: float) -> dict:
        """简化分析 - 无LLM时的fallback.

        Args:
            outcome_score: 质量评分

        Returns:
            dict: 简化分析结果
        """
        if outcome_score >= 8:
            return {
                "deviations": [],
                "reasons": [],
                "lessons": ["本次任务完成良好"],
                "successful_strategies": [],
                "failed_strategies": [],
                "applied_strategies": [],
            }
        elif outcome_score >= 6:
            return {
                "deviations": ["评分中等，有改进空间"],
                "reasons": ["可能存在细节问题"],
                "lessons": ["下次注意细节打磨"],
                "successful_strategies": [],
                "failed_strategies": [],
                "applied_strategies": [],
            }
        else:
            return {
                "deviations": ["评分较低，需要显著改进"],
                "reasons": ["可能存在结构性问题"],
                "lessons": ["建议重新审视整体设计"],
                "successful_strategies": [],
                "failed_strategies": [],
                "applied_strategies": [],
            }

    async def _detect_pattern(
        self,
        novel_id: str,
        task_type: str,
        chapter_number: int,
    ) -> Optional[dict]:
        """检测反复出现的问题模式.

        Args:
            novel_id: 小说ID
            task_type: 任务类型
            chapter_number: 章节号

        Returns:
            Optional[dict]: 模式信息
        """
        # 查询最近的经验
        recent_threshold = datetime.utcnow() - timedelta(days=7)
        stmt = select(HindsightExperience).where(
            HindsightExperience.novel_id == UUID(novel_id),
            HindsightExperience.task_type == task_type,
            HindsightExperience.created_at >= recent_threshold,
            HindsightExperience.is_archived == 0,
        )

        result = await self.db.execute(stmt)
        experiences = result.scalars().all()

        if len(experiences) < 2:
            return None

        # 简单模式检测：统计重复的教训
        lesson_counts: dict[str, int] = {}
        for exp in experiences:
            if exp.lessons_learned:
                for lesson in exp.lessons_learned:
                    # 简化匹配
                    key = lesson[:20] if lesson else ""
                    lesson_counts[key] = lesson_counts.get(key, 0) + 1

        # 找到出现多次的教训
        for lesson, count in lesson_counts.items():
            if count >= 2:
                return {
                    "pattern": f"{lesson}... (出现{count}次)",
                    "confidence": min(count / len(experiences), 1.0),
                }

        return None

    async def _query_experiences(
        self,
        novel_id: str,
        task_type: str,
        current_chapter: int,
        limit: int = 5,
    ) -> list[HindsightExperience]:
        """查询相关经验.

        Args:
            novel_id: 小说ID
            task_type: 任务类型
            current_chapter: 当前章节
            limit: 数量限制

        Returns:
            list[HindsightExperience]: 经验列表
        """
        stmt = select(HindsightExperience).where(
            HindsightExperience.novel_id == UUID(novel_id),
            HindsightExperience.is_archived == 0,
        )

        # 优先查询相同任务类型的经验
        stmt = stmt.order_by(
            HindsightExperience.task_type == task_type,
            HindsightExperience.chapter_number.desc(),
        )

        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_or_create_strategy(
        self,
        novel_id: str,
        strategy_name: str,
        strategy_type: str,
        target_dimension: str,
    ) -> StrategyEffectiveness:
        """获取或创建策略记录.

        Args:
            novel_id: 小说ID
            strategy_name: 策略名称
            strategy_type: 策略类型
            target_dimension: 目标维度

        Returns:
            StrategyEffectiveness: 策略记录
        """
        stmt = select(StrategyEffectiveness).where(
            StrategyEffectiveness.novel_id == UUID(novel_id),
            StrategyEffectiveness.strategy_name == strategy_name,
            StrategyEffectiveness.target_dimension == target_dimension,
        )

        result = await self.db.execute(stmt)
        strategy = result.scalar_one_or_none()

        if not strategy:
            strategy = StrategyEffectiveness(
                novel_id=UUID(novel_id),
                strategy_name=strategy_name,
                strategy_type=strategy_type,
                target_dimension=target_dimension,
                application_count=0,
                success_count=0,
                avg_effectiveness=0.5,
                recent_results=[],
                trend=StrategyTrend.stable.value,
            )
            self.db.add(strategy)

        return strategy

    async def _update_strategies(
        self,
        novel_id: str,
        strategies: list[str],
        outcome_score: float,
        task_type: str,
        chapter_number: int,
    ) -> None:
        """更新策略有效性.

        Args:
            novel_id: 小说ID
            strategies: 策略列表
            outcome_score: 评分
            task_type: 任务类型
            chapter_number: 章节号
        """
        # 计算效果分 (0-1)
        effectiveness = outcome_score / 10.0

        for strategy_name in strategies:
            strategy_type = self._infer_strategy_type(strategy_name)
            dimension = self._infer_dimension(task_type)

            await self.record_strategy_result(
                novel_id=novel_id,
                strategy_name=strategy_name,
                strategy_type=strategy_type,
                target_dimension=dimension,
                effectiveness_score=effectiveness,
            )

    def _infer_strategy_type(self, strategy_name: str) -> str:
        """推断策略类型.

        Args:
            strategy_name: 策略名称

        Returns:
            str: 策略类型
        """
        name_lower = strategy_name.lower()
        if any(k in name_lower for k in ["对话", "语言", "描述"]):
            return "description"
        elif any(k in name_lower for k in ["节奏", "场景", "转换"]):
            return "pacing"
        elif any(k in name_lower for k in ["修订", "修改", "调整"]):
            return "revision"
        return "general"

    def _infer_dimension(self, task_type: str) -> str:
        """推断目标维度.

        Args:
            task_type: 任务类型

        Returns:
            str: 目标维度
        """
        if task_type == "revision":
            return "一致性"
        elif task_type == "writing":
            return "质量"
        return "整体"

    def _calculate_trend(self, recent_results: list[float]) -> str:
        """计算趋势.

        Args:
            recent_results: 最近结果列表

        Returns:
            str: 趋势 (improving/declining/stable)
        """
        if len(recent_results) < 2:
            return StrategyTrend.stable.value

        # 简单趋势计算：比较前一半和后一半的平均值
        mid = len(recent_results) // 2
        first_half = sum(recent_results[:mid]) / mid if mid > 0 else 0
        second_half = sum(recent_results[mid:]) / (len(recent_results) - mid)

        diff = second_half - first_half

        if diff > 0.1:
            return StrategyTrend.improving.value
        elif diff < -0.1:
            return StrategyTrend.declining.value
        return StrategyTrend.stable.value

    async def _get_existing_preference(
        self,
        user_id: str,
        preference_key: str,
        novel_id: Optional[str],
    ) -> Optional[UserPreference]:
        """检查现有偏好.

        Args:
            user_id: 用户ID
            preference_key: 偏好键
            novel_id: 小说ID

        Returns:
            Optional[UserPreference]: 现有偏好
        """
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.preference_key == preference_key,
        )

        if novel_id:
            stmt = stmt.where(UserPreference.novel_id == UUID(novel_id))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
