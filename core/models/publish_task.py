"""发布任务模型"""
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class PublishType(str, enum.Enum):
    """发布类型"""
    create_book = "create_book"        # 创建新书
    publish_chapter = "publish_chapter"  # 发布章节
    batch_publish = "batch_publish"    # 批量发布


class PublishTaskStatus(str, enum.Enum):
    """发布任务状态"""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PublishTask(Base):
    """发布任务"""
    __tablename__ = "publish_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    platform_account_id = Column(UUID(as_uuid=True), ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False)
    publish_type = Column(Enum(PublishType), nullable=False)
    target_chapters = Column(ARRAY(Integer), default=list)  # 目标章节号列表
    status = Column(Enum(PublishTaskStatus), default=PublishTaskStatus.pending)
    progress = Column(JSONB, default=dict)
    result_summary = Column(JSONB, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    novel = relationship("Novel", back_populates="publish_tasks")
    platform_account = relationship("PlatformAccount", back_populates="publish_tasks")
    chapter_publishes = relationship("ChapterPublish", back_populates="publish_task", cascade="all, delete-orphan")
