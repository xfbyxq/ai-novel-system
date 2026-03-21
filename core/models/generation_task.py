import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class TaskType(str, enum.Enum):
    planning = "planning"
    writing = "writing"
    editing = "editing"
    batch_writing = "batch_writing"
    outline_refinement = "outline_refinement"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(
        UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
    task_type = Column(String(50), nullable=False)
    status = Column(String(50), default="pending")
    phase = Column(String(50), nullable=True)
    input_data = Column(JSONB, default=dict)
    output_data = Column(JSONB, default=dict)
    agent_logs = Column(JSONB, default=list)
    token_usage = Column(Integer, default=0)
    cost = Column(Numeric(10, 4), default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    novel = relationship("Novel", back_populates="generation_tasks")
    token_usages = relationship(
        "TokenUsage", back_populates="task", cascade="all, delete-orphan"
    )
