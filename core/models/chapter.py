import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class ChapterStatus(str, enum.Enum):
    draft = "draft"
    reviewing = "reviewing"
    published = "published"


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    volume_number = Column(Integer, default=1)
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    status = Column(Enum(ChapterStatus), default=ChapterStatus.draft)
    outline = Column(JSONB, default=dict)  # 章节大纲
    characters_appeared = Column(ARRAY(UUID(as_uuid=True)), default=list)
    plot_points = Column(JSONB, default=list)
    foreshadowing = Column(JSONB, default=list)
    quality_score = Column(Float, nullable=True)
    continuity_issues = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)

    novel = relationship("Novel", back_populates="chapters")

    __table_args__ = (
        # Ensure unique chapter numbers per novel
        {"comment": "Novel chapters"},
    )
