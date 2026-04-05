"""图查询服务单元测试.

测试 backend/services/graph_query_service.py 中的查询功能。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPathNode:
    """PathNode 数据类测试."""

    def test_path_node_creation(self):
        """测试路径节点创建."""
        from backend.services.graph_query_service import PathNode

        node = PathNode(
            id="char-001",
            name="张三",
            label="Character",
            properties={"role_type": "protagonist"},
        )

        assert node.id == "char-001"
        assert node.name == "张三"
        assert node.label == "Character"
        assert node.properties["role_type"] == "protagonist"


class TestPathEdge:
    """PathEdge 数据类测试."""

    def test_path_edge_creation(self):
        """测试路径边创建."""
        from backend.services.graph_query_service import PathEdge

        edge = PathEdge(
            from_id="char-001",
            to_id="char-002",
            relation_type="CHARACTER_RELATION",
            properties={"type": "friend", "strength": 8},
        )

        assert edge.from_id == "char-001"
        assert edge.to_id == "char-002"
        assert edge.relation_type == "CHARACTER_RELATION"
        assert edge.properties["strength"] == 8


class TestCharacterPath:
    """CharacterPath 数据类测试."""

    def test_character_path_creation(self):
        """测试角色路径创建."""
        from backend.services.graph_query_service import CharacterPath, PathEdge, PathNode

        nodes = [
            PathNode(id="1", name="张三", label="Character"),
            PathNode(id="2", name="李四", label="Character"),
        ]
        edges = [
            PathEdge(from_id="1", to_id="2", relation_type="CHARACTER_RELATION"),
        ]

        path = CharacterPath(
            from_character="张三",
            to_character="李四",
            nodes=nodes,
            edges=edges,
            length=1,
        )

        assert path.from_character == "张三"
        assert path.to_character == "李四"
        assert path.length == 1
        assert len(path.nodes) == 2

    def test_character_path_to_prompt(self):
        """测试路径转换为提示词格式."""
        from backend.services.graph_query_service import CharacterPath, PathEdge, PathNode

        nodes = [
            PathNode(id="1", name="张三", label="Character"),
            PathNode(id="2", name="李四", label="Character"),
        ]
        edges = [
            PathEdge(from_id="1", to_id="2", relation_type="FRIEND"),
        ]

        path = CharacterPath(
            from_character="张三",
            to_character="李四",
            nodes=nodes,
            edges=edges,
            length=1,
        )

        prompt = path.to_prompt()
        assert "张三" in prompt
        assert "李四" in prompt
        assert "1跳" in prompt

    def test_character_path_empty_to_prompt(self):
        """测试空路径转换为提示词."""
        from backend.services.graph_query_service import CharacterPath

        path = CharacterPath(
            from_character="张三",
            to_character="李四",
            nodes=[],
            edges=[],
            length=0,
        )

        prompt = path.to_prompt()
        assert "没有发现关联路径" in prompt


class TestCharacterNetwork:
    """CharacterNetwork 数据类测试."""

    def test_character_network_creation(self):
        """测试角色网络创建."""
        from backend.services.graph_query_service import CharacterNetwork

        network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[{"id": "1", "name": "张三"}, {"id": "2", "name": "李四"}],
            edges=[{"target_name": "李四", "properties": {"type": "friend"}}],
            total_relations=5,
        )

        assert network.character_id == "char-001"
        assert network.character_name == "张三"
        assert network.depth == 2
        assert network.total_relations == 5

    def test_character_network_to_prompt(self):
        """测试网络转换为提示词格式."""
        from backend.services.graph_query_service import CharacterNetwork

        network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[
                {"properties": {"type": "friend"}, "target_name": "李四"},
                {"properties": {"type": "enemy"}, "target_name": "王五"},
            ],
            total_relations=2,
        )

        prompt = network.to_prompt()
        assert "张三" in prompt
        assert "总关系数: 2" in prompt
        assert "friend" in prompt


class TestConflictReport:
    """ConflictReport 数据类测试."""

    def test_conflict_report_creation(self):
        """测试冲突报告创建."""
        from backend.services.graph_query_service import ConflictReport

        report = ConflictReport(
            conflict_type="dead_character_appearance",
            description="已死亡角色出现在后续章节",
            severity="high",
            characters=["张三"],
            details="角色在第5章死亡，但在第10章出现",
        )

        assert report.conflict_type == "dead_character_appearance"
        assert report.severity == "high"
        assert "张三" in report.characters

    def test_conflict_report_to_dict(self):
        """测试冲突报告转换为字典."""
        from backend.services.graph_query_service import ConflictReport

        report = ConflictReport(
            conflict_type="contradictory_relationship",
            description="矛盾的关系",
            severity="medium",
            characters=["张三", "李四"],
        )

        result = report.to_dict()
        assert result["conflict_type"] == "contradictory_relationship"
        assert result["severity"] == "medium"


class TestInfluenceReport:
    """InfluenceReport 数据类测试."""

    def test_influence_report_creation(self):
        """测试影响力报告创建."""
        from backend.services.graph_query_service import InfluenceReport

        report = InfluenceReport(
            character_id="char-001",
            character_name="张三",
            influence_score=85.5,
            direct_relations=10,
            indirect_relations=25,
            centrality_score=3.5,
            key_connections=["李四", "王五"],
        )

        assert report.character_name == "张三"
        assert report.influence_score == 85.5
        assert report.direct_relations == 10

    def test_influence_report_to_dict(self):
        """测试影响力报告转换为字典."""
        from backend.services.graph_query_service import InfluenceReport

        report = InfluenceReport(
            character_id="char-001",
            character_name="张三",
            influence_score=50.0,
            direct_relations=5,
            indirect_relations=10,
            centrality_score=2.0,
            key_connections=[],
        )

        result = report.to_dict()
        assert result["influence_score"] == 50.0
        assert result["direct_relations"] == 5


class TestGraphQueryService:
    """GraphQueryService 服务测试."""

    @pytest.fixture
    def mock_client(self):
        """创建mock Neo4j客户端."""
        client = MagicMock()
        client.execute_query = AsyncMock()
        client.is_connected = True
        return client

    @pytest.fixture
    def service(self, mock_client):
        """创建服务实例."""
        from backend.services.graph_query_service import GraphQueryService

        return GraphQueryService(mock_client)

    @pytest.mark.asyncio
    async def test_get_character_network_success(self, service, mock_client):
        """测试获取角色网络成功."""
        mock_client.execute_query.return_value = [
            {
                "c": {"id": "char-001", "name": "张三"},
                "nodes": [{"id": "char-002", "name": "李四"}],
                "relationships": [{"from_id": "char-001", "to_id": "char-002"}],
            }
        ]

        network = await service.get_character_network("novel-001", "张三", depth=2)

        assert network is not None
        assert network.character_name == "张三"
        assert network.depth == 2

    @pytest.mark.asyncio
    async def test_get_character_network_not_found(self, service, mock_client):
        """测试获取不存在的角色网络."""
        mock_client.execute_query.return_value = []

        network = await service.get_character_network("novel-001", "不存在的角色")

        assert network is None

    @pytest.mark.asyncio
    async def test_get_character_network_depth_limit(self, service, mock_client):
        """测试深度限制."""
        mock_client.execute_query.return_value = []

        # 测试深度超过上限
        await service.get_character_network("novel-001", "张三", depth=10)

        # 应该被限制到5
        call_args = mock_client.execute_query.call_args
        query = call_args[0][0] if call_args else ""
        assert "maxLevel: 5" in query

    @pytest.mark.asyncio
    async def test_get_character_network_exception(self, service, mock_client):
        """测试获取角色网络异常."""
        mock_client.execute_query.side_effect = Exception("查询失败")

        network = await service.get_character_network("novel-001", "张三")

        assert network is None

    @pytest.mark.asyncio
    async def test_find_shortest_path_success(self, service, mock_client):
        """测试查找最短路径成功."""
        mock_client.execute_query.return_value = [{"p": {}}]

        path = await service.find_shortest_path("novel-001", "张三", "李四")

        assert path is not None
        assert path.from_character == "张三"
        assert path.to_character == "李四"

    @pytest.mark.asyncio
    async def test_find_shortest_path_no_path(self, service, mock_client):
        """测试查找不存在的路径."""
        mock_client.execute_query.return_value = []

        path = await service.find_shortest_path("novel-001", "张三", "李四")

        assert path is not None
        assert path.length == 0

    @pytest.mark.asyncio
    async def test_get_all_relationships_success(self, service, mock_client):
        """测试获取所有关系成功."""
        mock_client.execute_query.return_value = [
            {"from_name": "张三", "to_name": "李四", "relation_type": "friend"},
            {"from_name": "张三", "to_name": "王五", "relation_type": "enemy"},
        ]

        relationships = await service.get_all_relationships("novel-001")

        assert len(relationships) == 2

    @pytest.mark.asyncio
    async def test_get_all_relationships_with_filter(self, service, mock_client):
        """测试按类型过滤关系."""
        mock_client.execute_query.return_value = [
            {"from_name": "张三", "to_name": "李四", "relation_type": "friend"},
        ]

        relationships = await service.get_all_relationships("novel-001", "friend")

        assert len(relationships) == 1

    @pytest.mark.asyncio
    async def test_get_all_relationships_exception(self, service, mock_client):
        """测试获取关系异常."""
        mock_client.execute_query.side_effect = Exception("查询失败")

        relationships = await service.get_all_relationships("novel-001")

        assert relationships == []

    @pytest.mark.asyncio
    async def test_check_consistency_conflicts_dead_character(self, service, mock_client):
        """测试检测死亡角色冲突."""
        # 第一次查询返回死亡角色冲突，第二次查询返回空（矛盾关系检测）
        mock_client.execute_query.side_effect = [
            [
                {  # 死亡角色检测
                    "character_name": "张三",
                    "death_chapter": 5,
                    "event_name": "大战",
                    "event_chapter": 10,
                }
            ],
            [],  # 矛盾关系检测返回空
        ]

        conflicts = await service.check_consistency_conflicts("novel-001")

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "dead_character_appearance"
        assert conflicts[0].severity == "high"

    @pytest.mark.asyncio
    async def test_check_consistency_conflicts_contradictory_rel(self, service, mock_client):
        """测试检测矛盾关系冲突."""
        # 第一次查询返回空（死亡角色检测）
        # 第二次查询返回矛盾关系
        mock_client.execute_query.side_effect = [
            [],  # 死亡角色检测
            [
                {  # 矛盾关系检测
                    "char_a": "张三",
                    "char_b": "李四",
                    "rel1": "enemy",
                    "rel2": "friend",
                }
            ],
        ]

        conflicts = await service.check_consistency_conflicts("novel-001")

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "contradictory_relationship"

    @pytest.mark.asyncio
    async def test_find_character_influence_success(self, service, mock_client):
        """测试计算角色影响力成功."""
        mock_client.execute_query.return_value = [
            {
                "id": "char-001",
                "name": "张三",
                "direct_relations": 5,
                "indirect_relations": 10,
                "centrality_score": 5.0,
            }
        ]

        influence = await service.find_character_influence("novel-001", "张三")

        assert influence is not None
        assert influence.character_name == "张三"
        assert influence.direct_relations == 5
        assert influence.influence_score == 70  # 5*10 + 10*2

    @pytest.mark.asyncio
    async def test_find_character_influence_not_found(self, service, mock_client):
        """测试计算不存在角色的影响力."""
        mock_client.execute_query.return_value = []

        influence = await service.find_character_influence("novel-001", "不存在的角色")

        assert influence is None

    @pytest.mark.asyncio
    async def test_get_event_timeline_success(self, service, mock_client):
        """测试获取事件时间线成功."""
        mock_client.execute_query.return_value = [
            {"id": "evt-001", "name": "事件1", "chapter": 1},
            {"id": "evt-002", "name": "事件2", "chapter": 2},
        ]

        timeline = await service.get_event_timeline("novel-001")

        assert len(timeline) == 2

    @pytest.mark.asyncio
    async def test_get_event_timeline_with_character(self, service, mock_client):
        """测试按角色过滤事件时间线."""
        mock_client.execute_query.return_value = [
            {"id": "evt-001", "name": "事件1", "chapter": 1},
        ]

        timeline = await service.get_event_timeline("novel-001", "张三")

        assert len(timeline) == 1

    @pytest.mark.asyncio
    async def test_find_pending_foreshadowings_success(self, service, mock_client):
        """测试查找待回收伏笔成功."""
        mock_client.execute_query.return_value = [
            {
                "id": "fore-001",
                "content": "神秘玉佩",
                "planted_chapter": 3,
                "expected_chapter": 10,
                "importance": 8,
            },
        ]

        foreshadowings = await service.find_pending_foreshadowings("novel-001", 8)

        assert len(foreshadowings) == 1

    @pytest.mark.asyncio
    async def test_find_pending_foreshadowings_exception(self, service, mock_client):
        """测试查找伏笔异常."""
        mock_client.execute_query.side_effect = Exception("查询失败")

        foreshadowings = await service.find_pending_foreshadowings("novel-001", 1)

        assert foreshadowings == []


class TestConvenienceFunctions:
    """便捷函数测试."""

    @pytest.mark.asyncio
    async def test_get_character_network_async_disabled(self):
        """测试图数据库禁用时获取网络."""
        with patch("core.graph.neo4j_client.get_neo4j_client", return_value=None):
            from backend.services.graph_query_service import get_character_network_async

            result = await get_character_network_async("novel-001", "张三")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_character_network_async_not_connected(self):
        """测试客户端未连接时获取网络."""
        mock_client = MagicMock()
        mock_client.is_connected = False

        with patch("core.graph.neo4j_client.get_neo4j_client", return_value=mock_client):
            from backend.services.graph_query_service import get_character_network_async

            result = await get_character_network_async("novel-001", "张三")

            assert result is None
