"""修订计划数据模型 - 支持人机协作修订流程."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from core.database import Base


class RevisionPlanStatus(str, enum.Enum):
    """修订计划状态."""

    pending = "pending"  # 待确认
    confirmed = "confirmed"  # 用户已确认
    executed = "executed"  # 已执行
    rejected = "rejected"  # 用户拒绝


class RevisionTargetType(str, enum.Enum):
    """修订目标类型."""

    character = "character"  # 角色
    chapter = "chapter"  # 章节内容
    world_setting = "world_setting"  # 世界观
    outline = "outline"  # 大纲
    plot = "plot"  # 情节


class RevisionPlan(Base):
    """修订计划表.

    记录用户反馈 → AI理解 → 修改方案的完整流程。
    """

    __tablename__ = "revision_plans"
    __table_args__ = (
        Index("idx_revision_plans_novel_id", "novel_id"),
        Index("idx_revision_plans_status", "status"),
        Index("idx_revision_plans_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 用户反馈原文
    feedback_text = Column(Text, nullable=False)

    # AI理解结果
    understood_intent = Column(Text)  # "修改角色'张三'的性格设定"
    confidence = Column(Float, default=0.0)  # 理解置信度

    # 定位到的修改目标 (JSONB)
    # [{
    #   "type": "character",
    #   "target_id": "uuid",
    #   "target_name": "张三",
    #   "field": "personality",
    #   "current_value": "...",
    #   "issue_description": "性格前后不一致"
    # }]
    targets = Column(JSONB, default=list)

    # 提议的修改方案 (JSONB)
    # [{
    #   "target_type": "character",
    #   "target_id": "uuid",
    #   "field": "personality",
    #   "old_value": "...",
    #   "new_value": "...",
    #   "reasoning": "统一为稳重性格"
    # }]
    proposed_changes = Column(JSONB, default=list)

    # 影响范围评估
    # {"affected_chapters": [5, 6, 7], "affected_characters": ["xxx"]}
    impact_assessment = Column(JSONB)

    # 状态
    status = Column(
        String(20),
        default=RevisionPlanStatus.pending.value,
    )

    # 用户调整 (用户确认时可能修改方案)
    user_modifications = Column(JSONB)

    # 时间戳
    confirmed_at = Column(DateTime(timezone=True))
    executed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": str(self.id),
            "novel_id": str(self.novel_id),
            "feedback_text": self.feedback_text,
            "understood_intent": self.understood_intent,
            "confidence": self.confidence,
            "targets": self.targets,
            "proposed_changes": self.proposed_changes,
            "impact_assessment": self.impact_assessment,
            "status": self.status,
            "user_modifications": self.user_modifications,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
