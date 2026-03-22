"""character 模块."""

import enum
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class RoleType(str, enum.Enum):
    """RoleType 类."""

    protagonist = "protagonist"  # 主角
    supporting = "supporting"  # 配角
    antagonist = "antagonist"  # 反派
    minor = "minor"  # 路人


class Gender(str, enum.Enum):
    """Gender 类."""

    male = "male"
    female = "female"
    other = "other"


class CharacterStatus(str, enum.Enum):
    """CharacterStatus 类."""

    alive = "alive"
    dead = "dead"
    unknown = "unknown"


class RelationshipType(str, enum.Enum):
    """标准角色关系类型枚举."""

    # 情感关系
    lover = "lover"  # 恋人
    spouse = "spouse"  # 配偶
    crush = "crush"  # 暗恋
    ex_lover = "ex_lover"  # 前任
    
    # 家庭关系
    parent = "parent"  # 父母
    child = "child"  # 子女
    sibling = "sibling"  # 兄弟姐妹
    grandparent = "grandparent"  # 祖父母
    grandchild = "grandchild"  # 孙子女
    
    # 社会关系
    friend = "friend"  # 朋友
    best_friend = "best_friend"  # 挚友
    enemy = "enemy"  # 敌人
    rival = "rival"  # 对手
    master = "master"  # 师父
    apprentice = "apprentice"  # 徒弟
    colleague = "colleague"  # 同事
    classmate = "classmate"  # 同学
    
    # 组织关系
    leader = "leader"  # 上级/首领
    subordinate = "subordinate"  # 下属
    member = "member"  # 组织成员
    
    # 其他
    ally = "ally"  # 盟友
    neutral = "neutral"  # 中立
    unknown = "unknown"  # 未知关系


# 关系类型的反向映射
RELATIONSHIP_REVERSE_MAP = {
    RelationshipType.lover: RelationshipType.lover,
    RelationshipType.spouse: RelationshipType.spouse,
    RelationshipType.crush: RelationshipType.crush,  # 暗恋保持单向
    RelationshipType.ex_lover: RelationshipType.ex_lover,
    RelationshipType.parent: RelationshipType.child,
    RelationshipType.child: RelationshipType.parent,
    RelationshipType.sibling: RelationshipType.sibling,
    RelationshipType.grandparent: RelationshipType.grandchild,
    RelationshipType.grandchild: RelationshipType.grandparent,
    RelationshipType.friend: RelationshipType.friend,
    RelationshipType.best_friend: RelationshipType.best_friend,
    RelationshipType.enemy: RelationshipType.enemy,
    RelationshipType.rival: RelationshipType.rival,
    RelationshipType.master: RelationshipType.apprentice,
    RelationshipType.apprentice: RelationshipType.master,
    RelationshipType.colleague: RelationshipType.colleague,
    RelationshipType.classmate: RelationshipType.classmate,
    RelationshipType.leader: RelationshipType.subordinate,
    RelationshipType.subordinate: RelationshipType.leader,
    RelationshipType.member: RelationshipType.member,
    RelationshipType.ally: RelationshipType.ally,
    RelationshipType.neutral: RelationshipType.neutral,
    RelationshipType.unknown: RelationshipType.unknown,
}


class Character(Base):
    """Character 类."""

    __tablename__ = "characters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(
        UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False
    )
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
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    novel = relationship("Novel", back_populates="characters")
    name_versions = relationship(
        "CharacterNameVersion", back_populates="character", cascade="all, delete-orphan"
    )
