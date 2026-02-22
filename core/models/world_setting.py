import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class WorldSetting(Base):
    __tablename__ = "world_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, unique=True)
    world_name = Column(String(200), nullable=True)
    world_type = Column(String(50), nullable=True)  # 现代/古代/架空/异界
    power_system = Column(JSONB, default=dict)  # 力量体系
    geography = Column(JSONB, default=dict)
    factions = Column(JSONB, default=dict)
    rules = Column(JSONB, default=dict)
    timeline = Column(JSONB, default=dict)
    special_elements = Column(JSONB, default=dict)
    raw_content = Column(Text, nullable=True)  # Agent 原始输出
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    novel = relationship("Novel", back_populates="world_setting")
