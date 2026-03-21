"""Agent 活动日志模型 - 记录每个 Agent 的详细活动."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class AgentActivity(Base):
    """
    Agent 活动记录表

    记录每个 Agent 在执行过程中的详细活动，包括：
    - 输入数据
    - 输出结果
    - Token 使用
    - 成本
    - 元数据（审查轮次、投票详情等）
    """

    __tablename__ = "agent_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 关联信息
    novel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("generation_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Agent 信息
    agent_name = Column(String(100), nullable=False, index=True)
    agent_role = Column(String(200), nullable=True)  # Agent 的角色描述

    # 活动类型
    activity_type = Column(String(50), nullable=False, index=True)
    # 类型包括：
    # - planning: 企划阶段
    #   - topic_analysis: 主题分析
    #   - world_building: 世界观构建
    #   - character_design: 角色设计
    #   - plot_architecture: 情节架构
    #   - world_review: 世界观审查
    #   - character_review: 角色审查
    #   - plot_review: 大纲审查
    # - writing: 写作阶段
    #   - chapter_planning: 章节策划
    #   - outline_refinement: 大纲细化
    #   - draft_writing: 初稿写作
    #   - query_handling: 查询处理
    #   - editing: 编辑审查
    #   - continuity_check: 连续性检查
    #   - continuity_fix: 连续性修复
    # - voting: 投票决策
    #   - vote_initiation: 投票发起
    #   - vote_cast: 投票执行
    #   - vote_result: 投票结果

    # 阶段/步骤信息
    phase = Column(String(50), nullable=True)  # 所属阶段
    step_number = Column(Integer, nullable=True)  # 步骤序号
    iteration_number = Column(Integer, nullable=True)  # 迭代轮次（用于审查循环）

    # 输入输出
    input_data = Column(JSONB, default=dict)  # 输入数据
    output_data = Column(JSONB, default=dict)  # 输出结果
    raw_output = Column(Text, nullable=True)  # 原始输出（用于非结构化数据）

    # 元数据
    activity_metadata = Column("metadata", JSONB, default=dict)
    # activity_metadata 结构示例：
    # {
    #     "review_score": 8.5,  # 审查评分
    #     "review_dimensions": {...},  # 各维度评分
    #     "improvement_suggestions": [...],  # 改进建议
    #     "voter_name": "...",  # 投票者名称
    #     "voter_role": "...",  # 投票者角色
    #     "chosen_option": "...",  # 选择的方案
    #     "voting_reasoning": "...",  # 投票理由
    #     "confidence": 0.85,  # 置信度
    #     "query_type": "world",  # 查询类型
    #     "query_content": "...",  # 查询内容
    #     "query_answer": "..."  # 查询答案
    # }

    # Token 和成本
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Numeric(10, 6), default=0)  # 使用更多小数位以提高精度

    # 状态
    status = Column(String(20), default="success")  # success/failed/retry
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # 时间戳
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    # task = relationship("GenerationTask", back_populates="agent_activities")

    # Indexes
    __table_args__ = (
        Index("idx_agent_activities_novel_task", "novel_id", "task_id"),
        Index("idx_agent_activities_type", "activity_type"),
        Index("idx_agent_activities_created", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "id": str(self.id),
            "novel_id": str(self.novel_id),
            "task_id": str(self.task_id),
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "activity_type": self.activity_type,
            "phase": self.phase,
            "step_number": self.step_number,
            "iteration_number": self.iteration_number,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "raw_output": self.raw_output,
            "metadata": self.activity_metadata,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": float(self.cost) if self.cost else 0,
            "status": self.status,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @classmethod
    def from_activity(cls, data: Dict[str, Any]) -> "AgentActivity":
        """从字典创建实例."""
        return cls(
            novel_id=data.get("novel_id"),
            task_id=data.get("task_id"),
            agent_name=data.get("agent_name"),
            agent_role=data.get("agent_role"),
            activity_type=data.get("activity_type"),
            phase=data.get("phase"),
            step_number=data.get("step_number"),
            iteration_number=data.get("iteration_number"),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            raw_output=data.get("raw_output"),
            activity_metadata=data.get("metadata", {}),
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            cost=data.get("cost", 0),
            status=data.get("status", "success"),
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
        )
