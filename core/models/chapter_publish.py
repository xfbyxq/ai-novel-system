"""章节发布记录模型"""
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class PublishStatus(str, enum.Enum):
    """发布状态"""
    pending = "pending"        # 待发布
    publishing = "publishing"  # 发布中
    published = "published"    # 已发布
    failed = "failed"          # 失败


class ChapterPublish(Base):
    """章节发布记录"""
    __tablename__ = "chapter_publishes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publish_task_id = Column(UUID(as_uuid=True), ForeignKey("publish_tasks.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    platform_chapter_id = Column(String(100), nullable=True)  # 平台返回的章节ID
    platform_url = Column(String(500), nullable=True)
    status = Column(Enum(PublishStatus), default=PublishStatus.pending)
    error_message = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    publish_task = relationship("PublishTask", back_populates="chapter_publishes")
    chapter = relationship("Chapter")
