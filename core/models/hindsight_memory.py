"""Hindsight记忆数据模型 - 支持Agent事后回顾学习."""

import enum
import uuid

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from core.database import Base


class TaskType(str, enum.Enum):
    """任务类型."""

    planning = "planning"  # 企划阶段
    writing = "writing"  # 写作阶段
    revision = "revision"  # 修订阶段


class StrategyTrend(str, enum.Enum):
    """策略趋势."""

    improving = "improving"  # 上升
    declining = "declining"  # 下降
    stable = "stable"  # 稳定


class HindsightExperience(Base):
    """事后回顾经验表.

    每次修订完成后自动生成，记录：
    - 初始目标 vs 实际结果
    - 偏差分析和原因
    - 经验教训
    - 成功的策略
    - 失败的策略
    """

    __tablename__ = "hindsight_experiences"
    __table_args__ = (
        Index("idx_hindsight_novel_id", "novel_id"),
        Index("idx_hindsight_task_type", "task_type"),
        Index("idx_hindsight_chapter", "chapter_number"),
        Index("idx_hindsight_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 关联的修订计划ID
    revision_plan_id = Column(UUID(as_uuid=True), nullable=True)

    # 任务上下文
    task_type = Column(String(50), nullable=False)  # planning/writing/revision
    chapter_number = Column(Integer, default=0)  # 0表示企划阶段
    agent_name = Column(String(100))

    # 用户反馈 (如果是修订触发的)
    original_feedback = Column(Text)
    user_satisfaction = Column(Float)  # 用户满意度评分 0-10

    # 初始目标 (计划阶段)
    initial_goal = Column(Text)  # "写一个紧张刺激的追逐场景"
    initial_plan = Column(JSONB)  # {"scenes": 5, "pacing": "fast"}

    # 实际结果 (执行后)
    actual_result = Column(Text)  # "只完成了3个场景，节奏偏慢"
    outcome_score = Column(Float)  # 0-10 质量评分

    # 事后分析 (LLM生成)
    deviations = Column(JSONB, default=list)  # 偏差列表
    deviation_reasons = Column(JSONB, default=list)  # 偏差原因
    lessons_learned = Column(JSONB, default=list)  # 经验教训列表
    successful_strategies = Column(JSONB, default=list)  # 成功的策略
    failed_strategies = Column(JSONB, default=list)  # 失败的策略

    # 模式识别
    recurring_pattern = Column(String(200))  # 识别的反复模式
    pattern_confidence = Column(Float)  # 模式置信度

    # 建议
    improvement_suggestions = Column(JSONB, default=list)  # 改进建议

    # 归档状态
    is_archived = Column(Integer, default=0)  # 0=活跃, 1=已归档

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": str(self.id),
            "novel_id": str(self.novel_id),
            "revision_plan_id": str(self.revision_plan_id) if self.revision_plan_id else None,
            "task_type": self.task_type,
            "chapter_number": self.chapter_number,
            "agent_name": self.agent_name,
            "original_feedback": self.original_feedback,
            "user_satisfaction": self.user_satisfaction,
            "initial_goal": self.initial_goal,
            "initial_plan": self.initial_plan,
            "actual_result": self.actual_result,
            "outcome_score": self.outcome_score,
            "deviations": self.deviations,
            "deviation_reasons": self.deviation_reasons,
            "lessons_learned": self.lessons_learned,
            "successful_strategies": self.successful_strategies,
            "failed_strategies": self.failed_strategies,
            "recurring_pattern": self.recurring_pattern,
            "pattern_confidence": self.pattern_confidence,
            "improvement_suggestions": self.improvement_suggestions,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StrategyEffectiveness(Base):
    """策略有效性追踪表.

    统计各策略的实际效果，用于：
    - 哪种修订策略最有效？
    - "增加对话"策略 → 情感维度平均提升0.3分
    - "压缩场景"策略 → 节奏维度平均提升0.5分
    """

    __tablename__ = "strategy_effectiveness"
    __table_args__ = (
        Index("idx_strategy_novel_id", "novel_id"),
        Index("idx_strategy_dimension", "target_dimension"),
        Index("idx_strategy_name", "strategy_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 策略信息
    strategy_name = Column(String(100), nullable=False)  # "增加对话"
    strategy_type = Column(String(50))  # revision/description/pacing
    target_dimension = Column(String(50))  # 情感/节奏/逻辑/一致性

    # 统计数据
    application_count = Column(Integer, default=0)  # 应用次数
    success_count = Column(Integer, default=0)  # 成功次数
    avg_effectiveness = Column(Float, default=0.5)  # 平均效果分 (0-1)

    # 最近的样本 (最近5次结果)
    recent_results = Column(JSONB, default=list)  # [0.3, 0.5, 0.2, 0.4, 0.1]

    # 趋势
    trend = Column(String(20), default=StrategyTrend.stable.value)

    # 元数据
    last_applied_chapter = Column(Integer)
    last_applied_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": str(self.id),
            "novel_id": str(self.novel_id),
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "target_dimension": self.target_dimension,
            "application_count": self.application_count,
            "success_count": self.success_count,
            "avg_effectiveness": self.avg_effectiveness,
            "recent_results": self.recent_results,
            "trend": self.trend,
            "last_applied_chapter": self.last_applied_chapter,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserPreference(Base):
    """用户偏好表.

    记录用户显式偏好和Hindsight推断的偏好。
    """

    __tablename__ = "user_preferences"
    __table_args__ = (
        Index("idx_user_pref_user_id", "user_id"),
        Index("idx_user_pref_novel_id", "novel_id"),
        Index("idx_user_pref_type", "preference_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False, index=True)  # UUID，前端存储
    novel_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # 可选的小说关联

    # 偏好信息
    preference_type = Column(String(50), nullable=False)  # ending/character/pacing/theme
    preference_key = Column(String(200), nullable=False)  # "hate_be"/"like_simple_dialogue"
    preference_value = Column(JSONB)  # {"value": True, "strength": 0.8}

    # 置信度
    confidence = Column(Float, default=0.5)  # 置信度 0-1
    source = Column(String(20))  # explicit(显式)/inferred(Hindsight推断)

    # 使用统计
    times_activated = Column(Integer, default=0)
    last_activated_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "novel_id": str(self.novel_id) if self.novel_id else None,
            "preference_type": self.preference_type,
            "preference_key": self.preference_key,
            "preference_value": self.preference_value,
            "confidence": self.confidence,
            "source": self.source,
            "times_activated": self.times_activated,
            "last_activated_at": self.last_activated_at.isoformat() if self.last_activated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
