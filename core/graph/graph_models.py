"""图数据模型定义.

定义图数据库中的节点和关系的Python模型。
这些模型用于在Python代码中表示图数据，并提供与Neo4j之间的转换。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeType(str, Enum):
    """节点类型枚举."""

    CHARACTER = "Character"
    LOCATION = "Location"
    EVENT = "Event"
    FACTION = "Faction"
    ITEM = "Item"
    FORESHADOWING = "Foreshadowing"


class RelationType(str, Enum):
    """关系类型枚举.

    基于现有 RelationshipType 扩展，支持更丰富的实体关系。
    """

    # 角色间关系 (基于现有 RelationshipType)
    CHARACTER_RELATION = "CHARACTER_RELATION"

    # 角色-地点关系
    LOCATED_AT = "LOCATED_AT"
    VISITED = "VISITED"
    BORN_IN = "BORN_IN"

    # 角色-事件关系
    PARTICIPATED_IN = "PARTICIPATED_IN"
    CAUSED = "CAUSED"
    AFFECTED_BY = "AFFECTED_BY"

    # 角色-势力关系
    MEMBER_OF = "MEMBER_OF"
    LEADER_OF = "LEADER_OF"
    ENEMY_OF_FACTION = "ENEMY_OF_FACTION"

    # 角色-物品关系
    OWNS = "OWNS"
    USES = "USES"
    CREATED = "CREATED"

    # 事件关系
    HAPPENED_AT = "HAPPENED_AT"
    FORESHADOWED_BY = "FORESHADOWED_BY"
    RESOLVES = "RESOLVES"

    # 势力关系
    ALLIED_WITH = "ALLIED_WITH"
    ENEMY_WITH = "ENEMY_WITH"
    SUBORDINATE_OF = "SUBORDINATE_OF"

    # 地点关系
    CONTAINS = "CONTAINS"
    NEAR = "NEAR"


@dataclass
class GraphNode(ABC):
    """图节点基类.

    所有节点类型的抽象基类，定义通用属性和方法。
    """

    id: str  # 节点唯一标识
    novel_id: str  # 所属小说ID，用于数据隔离
    name: str  # 节点名称
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    @abstractmethod
    def label(self) -> str:
        """获取Neo4j节点标签."""
        pass

    @abstractmethod
    def to_neo4j_properties(self) -> Dict[str, Any]:
        """转换为Neo4j节点属性."""
        pass

    @classmethod
    @abstractmethod
    def from_neo4j(cls, properties: Dict[str, Any]) -> "GraphNode":
        """从Neo4j节点属性创建实例."""
        pass


@dataclass
class CharacterNode(GraphNode):
    """角色节点.

    存储小说中的角色信息及其核心属性。
    """

    role_type: str = "minor"  # protagonist/supporting/antagonist/minor
    gender: Optional[str] = None
    age: Optional[int] = None
    status: str = "alive"  # alive/dead/unknown
    first_appearance_chapter: Optional[int] = None
    importance_level: int = 5  # 1-10，主角=10
    core_motivation: str = ""
    personal_code: str = ""
    personality_traits: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return NodeType.CHARACTER.value

    def to_neo4j_properties(self) -> Dict[str, Any]:
        """转换为Neo4j节点属性."""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "role_type": self.role_type,
            "gender": self.gender,
            "age": self.age,
            "status": self.status,
            "first_appearance_chapter": self.first_appearance_chapter,
            "importance_level": self.importance_level,
            "core_motivation": self.core_motivation,
            "personal_code": self.personal_code,
            "personality_traits": self.personality_traits,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_neo4j(cls, properties: Dict[str, Any]) -> "CharacterNode":
        """从Neo4j节点属性创建实例."""
        return cls(
            id=properties.get("id", ""),
            novel_id=properties.get("novel_id", ""),
            name=properties.get("name", ""),
            role_type=properties.get("role_type", "minor"),
            gender=properties.get("gender"),
            age=properties.get("age"),
            status=properties.get("status", "alive"),
            first_appearance_chapter=properties.get("first_appearance_chapter"),
            importance_level=properties.get("importance_level", 5),
            core_motivation=properties.get("core_motivation", ""),
            personal_code=properties.get("personal_code", ""),
            personality_traits=properties.get("personality_traits", []),
            created_at=datetime.fromisoformat(properties["created_at"])
            if "created_at" in properties
            else datetime.now(),
            updated_at=datetime.fromisoformat(properties["updated_at"])
            if "updated_at" in properties
            else datetime.now(),
        )


@dataclass
class LocationNode(GraphNode):
    """地点节点.

    存储小说中的地点信息。
    """

    location_type: str = "region"  # 城市/区域/建筑/秘境
    description: str = ""
    parent_location: Optional[str] = None  # 父级地点名
    significance: int = 5  # 重要性 1-10
    first_appearance_chapter: Optional[int] = None

    @property
    def label(self) -> str:
        return NodeType.LOCATION.value

    def to_neo4j_properties(self) -> Dict[str, Any]:
        """转换为Neo4j节点属性."""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "location_type": self.location_type,
            "description": self.description,
            "parent_location": self.parent_location,
            "significance": self.significance,
            "first_appearance_chapter": self.first_appearance_chapter,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_neo4j(cls, properties: Dict[str, Any]) -> "LocationNode":
        """从Neo4j节点属性创建实例."""
        return cls(
            id=properties.get("id", ""),
            novel_id=properties.get("novel_id", ""),
            name=properties.get("name", ""),
            location_type=properties.get("location_type", "region"),
            description=properties.get("description", ""),
            parent_location=properties.get("parent_location"),
            significance=properties.get("significance", 5),
            first_appearance_chapter=properties.get("first_appearance_chapter"),
            created_at=datetime.fromisoformat(properties["created_at"])
            if "created_at" in properties
            else datetime.now(),
            updated_at=datetime.fromisoformat(properties["updated_at"])
            if "updated_at" in properties
            else datetime.now(),
        )


@dataclass
class EventNode(GraphNode):
    """事件节点.

    存储小说中的关键事件信息。
    """

    event_type: str = "plot"  # 冲突/转折/揭示/战斗/情感
    chapter_number: int = 1
    story_day: Optional[int] = None  # 故事时间线中的天数
    description: str = ""
    importance: int = 5  # 1-10
    consequences: List[str] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)  # 参与角色名

    @property
    def label(self) -> str:
        return NodeType.EVENT.value

    def to_neo4j_properties(self) -> Dict[str, Any]:
        """转换为Neo4j节点属性."""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "event_type": self.event_type,
            "chapter_number": self.chapter_number,
            "story_day": self.story_day,
            "description": self.description,
            "importance": self.importance,
            "consequences": self.consequences,
            "participants": self.participants,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_neo4j(cls, properties: Dict[str, Any]) -> "EventNode":
        """从Neo4j节点属性创建实例."""
        return cls(
            id=properties.get("id", ""),
            novel_id=properties.get("novel_id", ""),
            name=properties.get("name", ""),
            event_type=properties.get("event_type", "plot"),
            chapter_number=properties.get("chapter_number", 1),
            story_day=properties.get("story_day"),
            description=properties.get("description", ""),
            importance=properties.get("importance", 5),
            consequences=properties.get("consequences", []),
            participants=properties.get("participants", []),
            created_at=datetime.fromisoformat(properties["created_at"])
            if "created_at" in properties
            else datetime.now(),
            updated_at=datetime.fromisoformat(properties["updated_at"])
            if "updated_at" in properties
            else datetime.now(),
        )


@dataclass
class FactionNode(GraphNode):
    """势力节点.

    存储小说中的势力/组织信息。
    """

    faction_type: str = "organization"  # 门派/家族/组织/国家
    description: str = ""
    power_level: str = "unknown"  # 势力等级
    leader_name: Optional[str] = None  # 首领名称
    territory: str = ""  # 领地
    goals: str = ""  # 势力目标
    first_appearance_chapter: Optional[int] = None

    @property
    def label(self) -> str:
        return NodeType.FACTION.value

    def to_neo4j_properties(self) -> Dict[str, Any]:
        """转换为Neo4j节点属性."""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "faction_type": self.faction_type,
            "description": self.description,
            "power_level": self.power_level,
            "leader_name": self.leader_name,
            "territory": self.territory,
            "goals": self.goals,
            "first_appearance_chapter": self.first_appearance_chapter,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_neo4j(cls, properties: Dict[str, Any]) -> "FactionNode":
        """从Neo4j节点属性创建实例."""
        return cls(
            id=properties.get("id", ""),
            novel_id=properties.get("novel_id", ""),
            name=properties.get("name", ""),
            faction_type=properties.get("faction_type", "organization"),
            description=properties.get("description", ""),
            power_level=properties.get("power_level", "unknown"),
            leader_name=properties.get("leader_name"),
            territory=properties.get("territory", ""),
            goals=properties.get("goals", ""),
            first_appearance_chapter=properties.get("first_appearance_chapter"),
            created_at=datetime.fromisoformat(properties["created_at"])
            if "created_at" in properties
            else datetime.now(),
            updated_at=datetime.fromisoformat(properties["updated_at"])
            if "updated_at" in properties
            else datetime.now(),
        )


@dataclass
class ForeshadowingNode(GraphNode):
    """伏笔节点.

    存储小说中的伏笔信息。
    """

    content: str = ""
    planted_chapter: int = 1
    expected_resolve_chapter: Optional[int] = None
    ftype: str = "plot"  # plot/character/item/mystery/hint
    importance: int = 5  # 1-10
    status: str = "pending"  # pending/resolved/abandoned/partial
    resolved_chapter: Optional[int] = None
    related_characters: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return NodeType.FORESHADOWING.value

    def to_neo4j_properties(self) -> Dict[str, Any]:
        """转换为Neo4j节点属性."""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "content": self.content,
            "planted_chapter": self.planted_chapter,
            "expected_resolve_chapter": self.expected_resolve_chapter,
            "ftype": self.ftype,
            "importance": self.importance,
            "status": self.status,
            "resolved_chapter": self.resolved_chapter,
            "related_characters": self.related_characters,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_neo4j(cls, properties: Dict[str, Any]) -> "ForeshadowingNode":
        """从Neo4j节点属性创建实例."""
        return cls(
            id=properties.get("id", ""),
            novel_id=properties.get("novel_id", ""),
            name=properties.get("name", ""),
            content=properties.get("content", ""),
            planted_chapter=properties.get("planted_chapter", 1),
            expected_resolve_chapter=properties.get("expected_resolve_chapter"),
            ftype=properties.get("ftype", "plot"),
            importance=properties.get("importance", 5),
            status=properties.get("status", "pending"),
            resolved_chapter=properties.get("resolved_chapter"),
            related_characters=properties.get("related_characters", []),
            created_at=datetime.fromisoformat(properties["created_at"])
            if "created_at" in properties
            else datetime.now(),
            updated_at=datetime.fromisoformat(properties["updated_at"])
            if "updated_at" in properties
            else datetime.now(),
        )


@dataclass
class GraphEdge:
    """图关系边.

    表示两个节点之间的关系。
    """

    from_node_id: str  # 源节点ID
    to_node_id: str  # 目标节点ID
    relation_type: RelationType  # 关系类型
    properties: Dict[str, Any] = field(default_factory=dict)  # 关系属性
    created_at: datetime = field(default_factory=datetime.now)

    def to_cypher_properties(self) -> str:
        """转换为Cypher属性字符串."""
        if not self.properties:
            return ""

        props = []
        for key, value in self.properties.items():
            if isinstance(value, str):
                props.append(f"{key}: '{value}'")
            elif isinstance(value, list):
                # 列表转换为Cypher格式
                items = ", ".join(
                    f"'{item}'" if isinstance(item, str) else str(item)
                    for item in value
                )
                props.append(f"{key}: [{items}]")
            else:
                props.append(f"{key}: {value}")

        return "{" + ", ".join(props) + "}"

    @classmethod
    def create_character_relation(
        cls,
        from_char_id: str,
        to_char_id: str,
        relation_subtype: str,  # lover/enemy/friend/master等
        strength: int = 5,
        since_chapter: Optional[int] = None,
    ) -> "GraphEdge":
        """创建角色间关系边.

        Args:
            from_char_id: 源角色ID
            to_char_id: 目标角色ID
            relation_subtype: 关系子类型（基于RelationshipType）
            strength: 关系强度 1-10
            since_chapter: 关系建立章节

        Returns:
            GraphEdge实例
        """
        properties = {"type": relation_subtype, "strength": strength}
        if since_chapter:
            properties["since_chapter"] = since_chapter

        return cls(
            from_node_id=from_char_id,
            to_node_id=to_char_id,
            relation_type=RelationType.CHARACTER_RELATION,
            properties=properties,
        )
