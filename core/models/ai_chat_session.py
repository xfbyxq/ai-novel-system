from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from core.database import Base

import uuid


class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), nullable=False, unique=True, index=True)
    scene = Column(String(50), nullable=False, index=True)
    context = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), ForeignKey("ai_chat_sessions.session_id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
