"""novel_creation_flow 模块."""

from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from core.database import Base
import uuid


class NovelCreationFlow(Base):
    """小说创建流程数据库模型."""

    __tablename__ = "novel_creation_flows"

    id = Column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(
        String(100),
        ForeignKey("ai_chat_sessions.session_id"),
        unique=True,
        nullable=False,
        index=True,
    )
    novel_id = Column(String(100), nullable=True, index=True)  # 创建成功后关联

    # 对话场景
    scene = Column(String(50), default="create")  # create/query/revise

    # 流程状态
    current_step = Column(String(50), default="initial")

    # 创建相关数据
    genre = Column(String(100), nullable=True)
    world_setting_data = Column(JSONB, default=dict)
    synopsis_data = Column(JSONB, default=dict)
    novel_title = Column(String(200), nullable=True)
    tags = Column(JSONB, default=list)
    target_platform = Column(String(100), default="番茄小说")
    length_type = Column(String(50), default="medium")

    # 查询相关数据
    selected_novel_id = Column(String(100), nullable=True, index=True)
    query_target = Column(String(100), nullable=True)
    query_result = Column(JSONB, default=dict)

    # 修改相关数据
    revision_target = Column(String(100), nullable=True)
    revision_details = Column(JSONB, default=dict)

    # 确认状态
    genre_confirmed = Column(Boolean, default=False)
    world_setting_confirmed = Column(Boolean, default=False)
    synopsis_confirmed = Column(Boolean, default=False)
    final_confirmed = Column(Boolean, default=False)
    revision_confirmed = Column(Boolean, default=False)

    # 对话历史（最近 10 轮）
    conversation_history = Column(JSONB, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
