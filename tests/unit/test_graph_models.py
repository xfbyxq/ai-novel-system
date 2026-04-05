"""图数据模型单元测试.

测试 core/graph/graph_models.py 中的节点模型、边模型和枚举类型。
"""

from datetime import datetime


class TestNodeTypeEnum:
    """NodeType 枚举测试."""

    def test_node_type_enum_values(self):
        """测试 NodeType 枚举值."""
        from core.graph.graph_models import NodeType

        assert NodeType.CHARACTER.value == "Character"
        assert NodeType.LOCATION.value == "Location"
        assert NodeType.EVENT.value == "Event"
        assert NodeType.FACTION.value == "Faction"
        assert NodeType.ITEM.value == "Item"
        assert NodeType.FORESHADOWING.value == "Foreshadowing"

    def test_node_type_enum_count(self):
        """测试 NodeType 枚举数量."""
        from core.graph.graph_models import NodeType

        assert len(NodeType) == 6


class TestRelationTypeEnum:
    """RelationType 枚举测试."""

    def test_character_relation_types(self):
        """测试角色间关系类型."""
        from core.graph.graph_models import RelationType

        assert RelationType.CHARACTER_RELATION.value == "CHARACTER_RELATION"

    def test_location_relation_types(self):
        """测试地点关系类型."""
        from core.graph.graph_models import RelationType

        assert RelationType.LOCATED_AT.value == "LOCATED_AT"
        assert RelationType.VISITED.value == "VISITED"
        assert RelationType.BORN_IN.value == "BORN_IN"

    def test_event_relation_types(self):
        """测试事件关系类型."""
        from core.graph.graph_models import RelationType

        assert RelationType.PARTICIPATED_IN.value == "PARTICIPATED_IN"
        assert RelationType.CAUSED.value == "CAUSED"
        assert RelationType.AFFECTED_BY.value == "AFFECTED_BY"

    def test_faction_relation_types(self):
        """测试势力关系类型."""
        from core.graph.graph_models import RelationType

        assert RelationType.MEMBER_OF.value == "MEMBER_OF"
        assert RelationType.LEADER_OF.value == "LEADER_OF"
        assert RelationType.ALLIED_WITH.value == "ALLIED_WITH"
        assert RelationType.ENEMY_WITH.value == "ENEMY_WITH"


class TestCharacterNode:
    """CharacterNode 模型测试."""

    def test_character_node_creation(self):
        """测试角色节点创建."""
        from core.graph.graph_models import CharacterNode

        node = CharacterNode(
            id="char-001",
            novel_id="novel-001",
            name="张三",
            role_type="protagonist",
            gender="male",
            age=25,
            status="alive",
        )

        assert node.id == "char-001"
        assert node.novel_id == "novel-001"
        assert node.name == "张三"
        assert node.role_type == "protagonist"
        assert node.gender == "male"
        assert node.age == 25
        assert node.status == "alive"

    def test_character_node_default_values(self):
        """测试角色节点默认值."""
        from core.graph.graph_models import CharacterNode

        node = CharacterNode(
            id="char-002",
            novel_id="novel-001",
            name="李四",
        )

        assert node.role_type == "minor"
        assert node.status == "alive"
        assert node.importance_level == 5
        assert node.personality_traits == []
        assert node.gender is None
        assert node.age is None

    def test_character_node_label(self):
        """测试角色节点标签."""
        from core.graph.graph_models import CharacterNode, NodeType

        node = CharacterNode(
            id="char-001",
            novel_id="novel-001",
            name="张三",
        )

        assert node.label == NodeType.CHARACTER.value

    def test_character_node_to_neo4j_properties(self):
        """测试角色节点转换为Neo4j属性."""
        from core.graph.graph_models import CharacterNode

        node = CharacterNode(
            id="char-001",
            novel_id="novel-001",
            name="张三",
            role_type="protagonist",
            personality_traits=["勇敢", "正义"],
        )

        props = node.to_neo4j_properties()

        assert props["id"] == "char-001"
        assert props["novel_id"] == "novel-001"
        assert props["name"] == "张三"
        assert props["role_type"] == "protagonist"
        assert props["personality_traits"] == ["勇敢", "正义"]
        assert "created_at" in props
        assert "updated_at" in props

    def test_character_node_from_neo4j(self):
        """测试从Neo4j属性创建角色节点."""
        from core.graph.graph_models import CharacterNode

        now = datetime.now().isoformat()
        props = {
            "id": "char-001",
            "novel_id": "novel-001",
            "name": "张三",
            "role_type": "supporting",
            "gender": "female",
            "age": 20,
            "status": "alive",
            "importance_level": 8,
            "core_motivation": "复仇",
            "personal_code": "坚持正义",
            "personality_traits": ["聪明", "冷静"],
            "created_at": now,
            "updated_at": now,
        }

        node = CharacterNode.from_neo4j(props)

        assert node.id == "char-001"
        assert node.name == "张三"
        assert node.role_type == "supporting"
        assert node.gender == "female"
        assert node.age == 20
        assert node.importance_level == 8
        assert node.core_motivation == "复仇"
        assert node.personality_traits == ["聪明", "冷静"]

    def test_character_node_from_neo4j_minimal(self):
        """测试从最小Neo4j属性创建角色节点."""
        from core.graph.graph_models import CharacterNode

        props = {"id": "char-001"}

        node = CharacterNode.from_neo4j(props)

        assert node.id == "char-001"
        assert node.novel_id == ""
        assert node.name == ""
        assert node.role_type == "minor"


class TestLocationNode:
    """LocationNode 模型测试."""

    def test_location_node_creation(self):
        """测试地点节点创建."""
        from core.graph.graph_models import LocationNode

        node = LocationNode(
            id="loc-001",
            novel_id="novel-001",
            name="青云门",
            location_type="sect",
            description="修仙宗门",
            significance=9,
        )

        assert node.id == "loc-001"
        assert node.name == "青云门"
        assert node.location_type == "sect"
        assert node.description == "修仙宗门"
        assert node.significance == 9

    def test_location_node_default_values(self):
        """测试地点节点默认值."""
        from core.graph.graph_models import LocationNode

        node = LocationNode(
            id="loc-001",
            novel_id="novel-001",
            name="未知地点",
        )

        assert node.location_type == "region"
        assert node.description == ""
        assert node.parent_location is None
        assert node.significance == 5

    def test_location_node_label(self):
        """测试地点节点标签."""
        from core.graph.graph_models import LocationNode, NodeType

        node = LocationNode(
            id="loc-001",
            novel_id="novel-001",
            name="测试地点",
        )

        assert node.label == NodeType.LOCATION.value

    def test_location_node_to_neo4j_properties(self):
        """测试地点节点转换为Neo4j属性."""
        from core.graph.graph_models import LocationNode

        node = LocationNode(
            id="loc-001",
            novel_id="novel-001",
            name="青云门",
            location_type="sect",
            description="修仙宗门",
        )

        props = node.to_neo4j_properties()

        assert props["id"] == "loc-001"
        assert props["name"] == "青云门"
        assert props["location_type"] == "sect"
        assert "created_at" in props

    def test_location_node_from_neo4j(self):
        """测试从Neo4j属性创建地点节点."""
        from core.graph.graph_models import LocationNode

        now = datetime.now().isoformat()
        props = {
            "id": "loc-001",
            "novel_id": "novel-001",
            "name": "青云门",
            "location_type": "sect",
            "description": "修仙宗门",
            "significance": 8,
            "created_at": now,
            "updated_at": now,
        }

        node = LocationNode.from_neo4j(props)

        assert node.id == "loc-001"
        assert node.name == "青云门"
        assert node.location_type == "sect"
        assert node.significance == 8


class TestEventNode:
    """EventNode 模型测试."""

    def test_event_node_creation(self):
        """测试事件节点创建."""
        from core.graph.graph_models import EventNode

        node = EventNode(
            id="evt-001",
            novel_id="novel-001",
            name="宗门大比",
            event_type="battle",
            chapter_number=10,
            description="年度宗门大比开始",
            importance=8,
            participants=["张三", "李四"],
        )

        assert node.id == "evt-001"
        assert node.name == "宗门大比"
        assert node.event_type == "battle"
        assert node.chapter_number == 10
        assert node.importance == 8
        assert "张三" in node.participants

    def test_event_node_default_values(self):
        """测试事件节点默认值."""
        from core.graph.graph_models import EventNode

        node = EventNode(
            id="evt-001",
            novel_id="novel-001",
            name="测试事件",
            chapter_number=1,
        )

        assert node.event_type == "plot"
        assert node.importance == 5
        assert node.consequences == []
        assert node.participants == []
        assert node.story_day is None

    def test_event_node_label(self):
        """测试事件节点标签."""
        from core.graph.graph_models import EventNode, NodeType

        node = EventNode(
            id="evt-001",
            novel_id="novel-001",
            name="测试事件",
            chapter_number=1,
        )

        assert node.label == NodeType.EVENT.value


class TestFactionNode:
    """FactionNode 模型测试."""

    def test_faction_node_creation(self):
        """测试势力节点创建."""
        from core.graph.graph_models import FactionNode

        node = FactionNode(
            id="fac-001",
            novel_id="novel-001",
            name="青云门",
            faction_type="sect",
            description="修仙正道宗门",
            power_level="S",
            leader_name="掌门真人",
        )

        assert node.id == "fac-001"
        assert node.name == "青云门"
        assert node.faction_type == "sect"
        assert node.power_level == "S"
        assert node.leader_name == "掌门真人"

    def test_faction_node_default_values(self):
        """测试势力节点默认值."""
        from core.graph.graph_models import FactionNode

        node = FactionNode(
            id="fac-001",
            novel_id="novel-001",
            name="测试势力",
        )

        assert node.faction_type == "organization"
        assert node.power_level == "unknown"
        assert node.territory == ""
        assert node.goals == ""

    def test_faction_node_label(self):
        """测试势力节点标签."""
        from core.graph.graph_models import FactionNode, NodeType

        node = FactionNode(
            id="fac-001",
            novel_id="novel-001",
            name="测试势力",
        )

        assert node.label == NodeType.FACTION.value


class TestForeshadowingNode:
    """ForeshadowingNode 模型测试."""

    def test_foreshadowing_node_creation(self):
        """测试伏笔节点创建."""
        from core.graph.graph_models import ForeshadowingNode

        node = ForeshadowingNode(
            id="fore-001",
            novel_id="novel-001",
            name="神秘玉佩",
            content="主角获得的神秘玉佩",
            planted_chapter=3,
            ftype="item",
            importance=8,
            related_characters=["张三"],
        )

        assert node.id == "fore-001"
        assert node.name == "神秘玉佩"
        assert node.content == "主角获得的神秘玉佩"
        assert node.planted_chapter == 3
        assert node.ftype == "item"
        assert node.importance == 8
        assert "张三" in node.related_characters

    def test_foreshadowing_node_default_values(self):
        """测试伏笔节点默认值."""
        from core.graph.graph_models import ForeshadowingNode

        node = ForeshadowingNode(
            id="fore-001",
            novel_id="novel-001",
            name="测试伏笔",
            content="测试内容",
            planted_chapter=1,
        )

        assert node.ftype == "plot"
        assert node.status == "pending"
        assert node.importance == 5
        assert node.expected_resolve_chapter is None
        assert node.resolved_chapter is None

    def test_foreshadowing_node_label(self):
        """测试伏笔节点标签."""
        from core.graph.graph_models import ForeshadowingNode, NodeType

        node = ForeshadowingNode(
            id="fore-001",
            novel_id="novel-001",
            name="测试伏笔",
            content="测试",
            planted_chapter=1,
        )

        assert node.label == NodeType.FORESHADOWING.value


class TestGraphEdge:
    """GraphEdge 模型测试."""

    def test_graph_edge_creation(self):
        """测试图边创建."""
        from core.graph.graph_models import GraphEdge, RelationType

        edge = GraphEdge(
            from_node_id="char-001",
            to_node_id="char-002",
            relation_type=RelationType.CHARACTER_RELATION,
            properties={"type": "friend", "strength": 8},
        )

        assert edge.from_node_id == "char-001"
        assert edge.to_node_id == "char-002"
        assert edge.relation_type == RelationType.CHARACTER_RELATION
        assert edge.properties["type"] == "friend"

    def test_graph_edge_to_cypher_properties_empty(self):
        """测试边转换为空Cypher属性."""
        from core.graph.graph_models import GraphEdge, RelationType

        edge = GraphEdge(
            from_node_id="char-001",
            to_node_id="char-002",
            relation_type=RelationType.CHARACTER_RELATION,
        )

        result = edge.to_cypher_properties()
        assert result == ""

    def test_graph_edge_to_cypher_properties_with_values(self):
        """测试边转换为Cypher属性."""
        from core.graph.graph_models import GraphEdge, RelationType

        edge = GraphEdge(
            from_node_id="char-001",
            to_node_id="char-002",
            relation_type=RelationType.CHARACTER_RELATION,
            properties={"type": "friend", "strength": 8},
        )

        result = edge.to_cypher_properties()
        assert "type: 'friend'" in result
        assert "strength: 8" in result

    def test_graph_edge_to_cypher_properties_with_list(self):
        """测试边转换包含列表的Cypher属性."""
        from core.graph.graph_models import GraphEdge, RelationType

        edge = GraphEdge(
            from_node_id="char-001",
            to_node_id="char-002",
            relation_type=RelationType.CHARACTER_RELATION,
            properties={"tags": ["重要", "主线"]},
        )

        result = edge.to_cypher_properties()
        assert "tags: [" in result
        assert "'重要'" in result

    def test_graph_edge_create_character_relation(self):
        """测试创建角色关系边."""
        from core.graph.graph_models import GraphEdge, RelationType

        edge = GraphEdge.create_character_relation(
            from_char_id="char-001",
            to_char_id="char-002",
            relation_subtype="friend",
            strength=9,
            since_chapter=5,
        )

        assert edge.from_node_id == "char-001"
        assert edge.to_node_id == "char-002"
        assert edge.relation_type == RelationType.CHARACTER_RELATION
        assert edge.properties["type"] == "friend"
        assert edge.properties["strength"] == 9
        assert edge.properties["since_chapter"] == 5

    def test_graph_edge_default_values(self):
        """测试边默认值."""
        from core.graph.graph_models import GraphEdge, RelationType

        edge = GraphEdge(
            from_node_id="char-001",
            to_node_id="char-002",
            relation_type=RelationType.CHARACTER_RELATION,
        )

        assert edge.properties == {}
        assert edge.created_at is not None
