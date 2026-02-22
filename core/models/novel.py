import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base

import uuid


class NovelStatus(str, enum.Enum):
    planning = "planning"
    writing = "writing"
    completed = "completed"
    published = "published"


class Novel(Base):
    __tablename__ = "novels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    author = Column(String(100), default="AI创作")
    genre = Column(String(50), nullable=False)
    tags = Column(ARRAY(String), default=list)
    status = Column(Enum(NovelStatus), default=NovelStatus.planning)
    word_count = Column(Integer, default=0)
    chapter_count = Column(Integer, default=0)
    cover_url = Column(String(500), nullable=True)
    synopsis = Column(Text, nullable=True)
    target_platform = Column(String(50), default="番茄小说")
    estimated_revenue = Column(Numeric(10, 2), default=0)
    actual_revenue = Column(Numeric(10, 2), default=0)
    token_cost = Column(Numeric(10, 4), default=0)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    world_setting = relationship("WorldSetting", back_populates="novel", uselist=False, cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="novel", cascade="all, delete-orphan")
    plot_outline = relationship("PlotOutline", back_populates="novel", uselist=False, cascade="all, delete-orphan")
    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan", order_by="Chapter.chapter_number")
    generation_tasks = relationship("GenerationTask", back_populates="novel", cascade="all, delete-orphan")
