"""图数据库功能集成测试.

测试图数据库模块的跨模块交互和端到端流程。
包括：
1. 模型与服务层的交互
2. 服务层与数据库的交互
3. API端点的端到端流程
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Mock数据和Fixtures
# ---------------------------------------------------------------------------

MOCK_NOVEL_ID = str(uuid4())
MOCK_CHARACTER_ID = str(uuid4())

MOCK_CHARACTER_DATA = {
    "id": MOCK_CHARACTER_ID,
    "novel_id": MOCK_NOVEL_ID,
    "name": "张三",
    "role_type": "protagonist",
    "gender": "male",
    "age": 25,
    "status": "alive",
    "first_appearance_chapter": 1,
    "importance_level": 10,
}

MOCK_CHARACTER_RELATIONSHIPS = [
    {
        "target": "李四",
        "type": "friend",
        "strength": 8,
        "since_chapter": 3,
    }
]

MOCK_WORLD_SETTING = {
    "world_name": "青玄大陆",
    "world_type": "仙侠",
    "geography": {
        "major_regions": [
            {"name": "东域", "description": "修仙圣地"},
        ]
    },
    "factions": [
        {"name": "青云门", "type": "sect", "leader": "掌门真人"},
    ],
}

MOCK_EXTRACTION_RESULT = {
    "summary": "第一章：主角出场",
    "characters": [
        {
            "name": "张三",
            "role_type": "protagonist",
            "gender": "male",
            "is_new": True,
            "actions": ["出场", "获得传承"],
        }
    ],
    "events": [
        {
            "name": "获得传承",
            "event_type": "revelation",
            "participants": ["张三"],
            "significance": 9,
        }
    ],
    "foreshadowings": [
        {
            "content": "神秘玉佩",
            "ftype": "item",
            "importance": 8,
            "related_characters": ["张三"],
        }
    ],
    "relationships": [
        {
            "from_character": "张三",
            "to_character": "李四",
            "relation_type": "friend",
            "strength": 7,
        }
    ],
}


# ---------------------------------------------------------------------------
# 模型与服务交互测试
# ---------------------------------------------------------------------------


class TestModelServiceIntegration:
    """模型与服务层集成测试."""

    @pytest.mark.asyncio
    async def test_character_node_to_neo4j_flow(self):
        """测试角色节点创建并同步到Neo4j的流程."""
        from backend.services.graph_sync_service import GraphSyncService
        from core.graph.graph_models import CharacterNode

        # 创建角色节点
        node = CharacterNode(
            id=MOCK_CHARACTER_ID,
            novel_id=MOCK_NOVEL_ID,
            name="张三",
            role_type="protagonist",
            gender="male",
            age=25,
        )

        # Mock Neo4j客户端
        mock_client = MagicMock()
        mock_client.create_node = AsyncMock(return_value=MOCK_CHARACTER_ID)

        # Mock数据库会话
        mock_db = MagicMock()

        # 创建同步服务（用于验证构造）
        GraphSyncService(mock_client, mock_db)

        # 验证节点属性转换
        props = node.to_neo4j_properties()
        assert props["name"] == "张三"
        assert props["role_type"] == "protagonist"

        # 模拟创建节点
        node_id = await mock_client.create_node(node.label, props)
        assert node_id == MOCK_CHARACTER_ID

    @pytest.mark.asyncio
    async def test_event_node_extraction_and_sync(self):
        """测试事件节点从抽取到同步的流程."""
        from backend.services.entity_extractor_service import ExtractedEvent
        from core.graph.graph_models import EventNode

        # 模拟抽取的事件
        extracted = ExtractedEvent(
            name="宗门大比",
            chapter_number=10,
            event_type="battle",
            participants=["张三", "李四"],
            description="年度大比",
            significance=8,
        )

        # 转换为图节点
        event_node = EventNode(
            id=str(uuid4()),
            novel_id=MOCK_NOVEL_ID,
            name=extracted.name,
            chapter_number=extracted.chapter_number,
            event_type=extracted.event_type,
            participants=extracted.participants,
            description=extracted.description,
            importance=extracted.significance,
        )

        # 验证数据一致性
        assert event_node.name == extracted.name
        assert event_node.chapter_number == extracted.chapter_number
        assert event_node.importance == extracted.significance


# ---------------------------------------------------------------------------
# 服务与数据库交互测试
# ---------------------------------------------------------------------------


class TestServiceDatabaseIntegration:
    """服务与数据库集成测试."""

    @pytest.fixture
    def mock_db_session(self):
        """创建mock数据库会话."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_neo4j_client(self):
        """创建mock Neo4j客户端."""
        client = MagicMock()
        client.is_connected = True
        client.create_node = AsyncMock(return_value="node-001")
        client.create_relationship = AsyncMock(return_value=True)
        client.execute_query = AsyncMock(return_value=[])
        client.delete_novel_graph = AsyncMock(return_value=5)
        return client

    @pytest.mark.asyncio
    async def test_full_sync_flow(self, mock_db_session, mock_neo4j_client):
        """测试完整的同步流程."""
        from backend.services.graph_sync_service import GraphSyncService
        from core.models.character import Character

        # Mock角色查询结果
        mock_char = MagicMock(spec=Character)
        mock_char.id = uuid4()
        mock_char.name = "张三"
        mock_char.role_type = "protagonist"
        mock_char.gender = "male"
        mock_char.age = 25
        mock_char.status = "alive"
        mock_char.first_appearance_chapter = 1
        mock_char.relationships = []

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_char]
        mock_result.scalars.return_value = mock_scalars

        # Mock世界观和大纲查询返回None
        mock_empty_result = MagicMock()
        mock_empty_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [
            mock_result,  # 角色查询
            mock_empty_result,  # 世界观查询
            mock_empty_result,  # 大纲查询
        ]

        service = GraphSyncService(mock_neo4j_client, mock_db_session)
        result = await service.sync_novel_full(uuid4())

        assert result.success is True
        assert result.sync_type == "full"
        mock_neo4j_client.create_node.assert_called()

    @pytest.mark.asyncio
    async def test_character_sync_with_relationships(self, mock_db_session, mock_neo4j_client):
        """测试带关系的角色同步."""
        from backend.services.graph_sync_service import GraphSyncService
        from core.models.character import Character

        char1 = MagicMock(spec=Character)
        char1.id = uuid4()
        char1.name = "张三"
        char1.role_type = "protagonist"
        char1.gender = "male"
        char1.age = 25
        char1.status = "alive"
        char1.first_appearance_chapter = 1
        # relationships应该是字典格式: {角色名: 关系类型}
        char1.relationships = {"李四": "friend"}

        char2 = MagicMock(spec=Character)
        char2.id = uuid4()
        char2.name = "李四"
        char2.role_type = "supporting"
        char2.gender = "female"
        char2.age = 22
        char2.status = "alive"
        char2.first_appearance_chapter = 1
        char2.relationships = {}

        service = GraphSyncService(mock_neo4j_client, mock_db_session)
        result = await service.sync_characters(uuid4(), [char1, char2])

        assert result.success is True
        # 应该创建2个节点
        assert mock_neo4j_client.create_node.call_count == 2

    @pytest.mark.asyncio
    async def test_entity_extraction_and_storage(self, mock_db_session):
        """测试实体抽取并存储的流程."""
        from backend.services.entity_extractor_service import (
            EntityExtractorService,
        )

        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock(
            return_value={
                "content": json.dumps(MOCK_EXTRACTION_RESULT),
                "usage": {"total_tokens": 500},
            }
        )

        service = EntityExtractorService(llm_client=mock_llm)
        result = await service.extract_from_chapter(
            chapter_number=1,
            chapter_content="第一章内容...",
            known_characters=[],
        )

        assert result.chapter_number == 1
        assert len(result.characters) == 1
        assert result.characters[0].name == "张三"
        assert len(result.events) == 1
        assert len(result.foreshadowings) == 1


# ---------------------------------------------------------------------------
# 查询服务集成测试
# ---------------------------------------------------------------------------


class TestQueryServiceIntegration:
    """查询服务集成测试."""

    @pytest.fixture
    def mock_client(self):
        """创建mock Neo4j客户端."""
        client = MagicMock()
        client.is_connected = True
        client.execute_query = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_character_network_query_flow(self, mock_client):
        """测试角色网络查询流程."""
        from backend.services.graph_query_service import GraphQueryService

        # Mock查询结果
        mock_client.execute_query.return_value = [
            {
                "c": {"id": "char-001", "name": "张三", "role_type": "protagonist"},
                "nodes": [
                    {"id": "char-001", "name": "张三"},
                    {"id": "char-002", "name": "李四"},
                ],
                "relationships": [
                    {"from_id": "char-001", "to_id": "char-002", "properties": {"type": "friend"}},
                ],
            }
        ]

        service = GraphQueryService(mock_client)
        network = await service.get_character_network(MOCK_NOVEL_ID, "张三", depth=2)

        assert network is not None
        assert network.character_name == "张三"
        assert network.total_relations == 1

    @pytest.mark.asyncio
    async def test_conflict_detection_flow(self, mock_client):
        """测试冲突检测流程."""
        from backend.services.graph_query_service import GraphQueryService

        # Mock死亡角色出现冲突
        mock_client.execute_query.side_effect = [
            [
                {  # 死亡角色检测
                    "character_name": "张三",
                    "death_chapter": 5,
                    "event_name": "大战",
                    "event_chapter": 10,
                }
            ],
            [],  # 矛盾关系检测
        ]

        service = GraphQueryService(mock_client)
        conflicts = await service.check_consistency_conflicts(MOCK_NOVEL_ID)

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "dead_character_appearance"
        assert conflicts[0].severity == "high"

    @pytest.mark.asyncio
    async def test_influence_calculation_flow(self, mock_client):
        """测试影响力计算流程."""
        from backend.services.graph_query_service import GraphQueryService

        mock_client.execute_query.return_value = [
            {
                "id": "char-001",
                "name": "张三",
                "direct_relations": 10,
                "indirect_relations": 25,
                "centrality_score": 5.0,
            }
        ]

        service = GraphQueryService(mock_client)
        influence = await service.find_character_influence(MOCK_NOVEL_ID, "张三")

        assert influence is not None
        assert influence.direct_relations == 10
        assert influence.influence_score == 150  # 10*10 + 25*2


# ---------------------------------------------------------------------------
# API端点端到端测试
# ---------------------------------------------------------------------------


class TestAPIEndpointIntegration:
    """API端点端到端集成测试."""

    @pytest.mark.asyncio
    async def test_health_to_init_flow(self):
        """测试健康检查到初始化的流程."""
        from backend.api.v1.graph import get_graph_health, initialize_graph_connection

        # 1. 健康检查 - 未连接（启用但无客户端）
        with (
            patch("backend.api.v1.graph.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=None),
        ):
            health = await get_graph_health()
            assert health["enabled"] is True
            assert health["connected"] is False

        # 2. 初始化连接
        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("backend.api.v1.graph.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.init_neo4j_client"),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
        ):
            init_result = await initialize_graph_connection()
            assert init_result["success"] is True

    @pytest.mark.asyncio
    async def test_sync_to_query_flow(self):
        """测试从同步到查询的完整流程."""
        from backend.api.v1.graph import get_character_network, sync_novel_to_graph_db
        from backend.services.graph_query_service import CharacterNetwork

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.create_node = AsyncMock(return_value="node-001")
        mock_client.execute_query = AsyncMock()

        mock_db = MagicMock()
        mock_db.execute = AsyncMock()

        # Mock小说查询
        mock_novel = MagicMock()
        mock_novel.id = uuid4()
        mock_novel.title = "测试小说"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_novel
        mock_db.execute.return_value = mock_result

        novel_id = mock_novel.id

        # 1. 同步数据 - 需要patch settings.ENABLE_GRAPH_DATABASE
        with (
            patch("backend.api.v1.graph.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch(
                "backend.api.v1.graph.sync_novel_to_graph",
                AsyncMock(return_value=MagicMock(success=True)),
            ),
        ):
            sync_result = await sync_novel_to_graph_db(
                novel_id=novel_id,
                background_tasks=MagicMock(),
                db=mock_db,
            )
            assert sync_result["success"] is True

        # 2. 查询角色网络
        mock_network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[],
            total_relations=5,
        )

        with (
            patch("backend.api.v1.graph.settings.ENABLE_GRAPH_DATABASE", True),
            patch(
                "backend.api.v1.graph.get_character_network_async",
                AsyncMock(return_value=mock_network),
            ),
        ):
            network_result = await get_character_network(
                novel_id=novel_id,
                character_name="张三",
                depth=2,
            )
            assert network_result["success"] is True


# ---------------------------------------------------------------------------
# Agent混入集成测试
# ---------------------------------------------------------------------------


class TestAgentMixinIntegration:
    """Agent混入集成测试."""

    @pytest.fixture
    def agent(self):
        """创建测试Agent."""
        from agents.graph_query_mixin import GraphQueryMixin

        class TestAgent(GraphQueryMixin):
            pass

        # Mock settings.ENABLE_GRAPH_DATABASE为True
        with patch("agents.graph_query_mixin.settings.ENABLE_GRAPH_DATABASE", True):
            agent = TestAgent()
            agent.set_graph_context(MOCK_NOVEL_ID)
            # 确保设置成功
            agent._graph_enabled = True
        return agent

    @pytest.mark.asyncio
    async def test_agent_full_context_flow(self, agent):
        """测试Agent获取完整上下文的流程."""
        from backend.services.graph_query_service import CharacterNetwork, InfluenceReport

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[{"properties": {"type": "friend"}, "target_name": "李四"}],
            total_relations=1,
        )

        mock_influence = InfluenceReport(
            character_id="char-001",
            character_name="张三",
            influence_score=50.0,
            direct_relations=5,
            indirect_relations=10,
            centrality_score=2.5,
            key_connections=["李四"],
        )

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch("agents.graph_query_mixin.GraphQueryService") as mock_service,
        ):
            mock_instance = MagicMock()
            mock_instance.get_character_network = AsyncMock(return_value=mock_network)
            mock_instance.find_character_influence = AsyncMock(return_value=mock_influence)
            mock_instance.check_consistency_conflicts = AsyncMock(return_value=[])
            mock_service.return_value = mock_instance

            context = await agent.get_full_character_context("张三")

            assert "张三" in context
            assert "关系网络" in context
            assert "影响力" in context

    @pytest.mark.asyncio
    async def test_agent_conflict_warning_flow(self, agent):
        """测试Agent冲突警告流程."""
        from backend.services.graph_query_service import ConflictReport

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_conflicts = [
            ConflictReport(
                conflict_type="dead_character_appearance",
                description="已死亡角色出现在后续章节",
                severity="high",
                characters=["张三"],
                details="第5章死亡，第10章出现",
            )
        ]

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch("agents.graph_query_mixin.GraphQueryService") as mock_service,
        ):
            mock_instance = MagicMock()
            mock_instance.check_consistency_conflicts = AsyncMock(return_value=mock_conflicts)
            mock_service.return_value = mock_instance

            conflicts = await agent.check_conflicts()
            context = agent.format_conflicts_context(conflicts)

            assert len(conflicts) == 1
            assert "严重" in context or "[高]" in context


# ---------------------------------------------------------------------------
# 错误处理集成测试
# ---------------------------------------------------------------------------


class TestErrorHandlingIntegration:
    """错误处理集成测试."""

    @pytest.mark.asyncio
    async def test_connection_failure_graceful_degradation(self):
        """测试连接失败的优雅降级."""
        from backend.services.graph_sync_service import sync_novel_to_graph

        # Mock客户端返回None（连接失败）
        with patch("core.graph.neo4j_client.get_neo4j_client", return_value=None):
            result = await sync_novel_to_graph(uuid4(), MagicMock())

            assert result.success is False
            assert "未启用" in result.errors[0] or "未连接" in result.errors[0]

    @pytest.mark.asyncio
    async def test_query_service_error_handling(self):
        """测试查询服务错误处理."""
        from backend.services.graph_query_service import GraphQueryService

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.execute_query = AsyncMock(side_effect=Exception("查询失败"))

        service = GraphQueryService(mock_client)

        # 所有查询应该优雅地处理错误
        network = await service.get_character_network(MOCK_NOVEL_ID, "张三")
        assert network is None

        path = await service.find_shortest_path(MOCK_NOVEL_ID, "张三", "李四")
        assert path is None

        conflicts = await service.check_consistency_conflicts(MOCK_NOVEL_ID)
        assert conflicts == []

    @pytest.mark.asyncio
    async def test_api_error_responses(self):
        """测试API错误响应."""
        from fastapi import HTTPException

        from backend.api.v1.graph import get_character_network, get_graph_health

        # 测试禁用状态 - 直接patch模块中导入的settings
        with patch("backend.api.v1.graph.settings.ENABLE_GRAPH_DATABASE", False):
            result = await get_graph_health()
            assert result["enabled"] is False

        # 测试未找到资源
        with (
            patch("backend.api.v1.graph.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_character_network_async", return_value=None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_character_network(
                    novel_id=uuid4(),
                    character_name="不存在的角色",
                )
            assert exc_info.value.status_code == 404
