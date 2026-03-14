import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class RoleType(str, enum.Enum):
    protagonist = "protagonist"  # 主角
    supporting = "supporting"    # 配角
    antagonist = "antagonist"    # 反派
    minor = "minor"              # 路人


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class CharacterStatus(str, enum.Enum):
    alive = "alive"
    dead = "dead"
    unknown = "unknown"


class Character(Base):
    __tablename__ = "characters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    role_type = Column(String(50), default="minor")
    gender = Column(String(20), nullable=True)
    age = Column(Integer, nullable=True)
    appearance = Column(Text, nullable=True)
    personality = Column(Text, nullable=True)
    background = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    abilities = Column(JSONB, default=dict)
    relationships = Column(JSONB, default=dict)  # {character_id: relationship_type}
    growth_arc = Column(JSONB, default=dict)
    status = Column(String(50), default="alive")
    first_appearance_chapter = Column(Integer, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    novel = relationship("Novel", back_populates="characters")
    name_versions = relationship("CharacterNameVersion", back_populates="character", cascade="all, delete-orphan")
