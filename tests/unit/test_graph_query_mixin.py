"""图查询混入类单元测试.

测试 agents/graph_query_mixin.py 中的混入功能。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 先导入混入类
from agents.graph_query_mixin import GraphQueryMixin


class MockAgent(GraphQueryMixin):
    """用于测试的模拟Agent类."""

    def __init__(self):
        self._graph_enabled = False
        self._novel_id = None


class TestGraphQueryMixinSetup:
    """混入类设置测试."""

    def test_set_graph_context(self):
        """测试设置图查询上下文."""
        agent = MockAgent()
        agent.set_graph_context("novel-001")

        assert agent._novel_id == "novel-001"
        assert agent._graph_enabled is not None


class TestGraphQueryMixinQueries:
    """混入类查询方法测试."""

    @pytest.fixture
    def agent(self):
        """创建已设置上下文的Agent."""
        agent = MockAgent()
        agent.set_graph_context("novel-001")
        # 确保图数据库启用
        agent._graph_enabled = True
        return agent

    @pytest.mark.asyncio
    async def test_query_character_network_disabled(self):
        """测试图数据库禁用时查询角色网络."""
        agent = MockAgent()
        agent._graph_enabled = False
        agent._novel_id = "novel-001"

        result = await agent.query_character_network("张三")

        assert result is None

    @pytest.mark.asyncio
    async def test_query_character_network_no_novel_id(self):
        """测试未设置小说ID时查询角色网络."""
        agent = MockAgent()
        agent._graph_enabled = True
        agent._novel_id = None

        result = await agent.query_character_network("张三")

        assert result is None

    @pytest.mark.asyncio
    async def test_query_character_network_not_connected(self, agent):
        """测试客户端未连接时查询角色网络."""
        with patch("agents.graph_query_mixin.get_neo4j_client", return_value=None):
            result = await agent.query_character_network("张三")

            assert result is None

    @pytest.mark.asyncio
    async def test_query_character_network_success(self, agent):
        """测试成功查询角色网络."""
        from backend.services.graph_query_service import CharacterNetwork, GraphQueryService

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[],
            total_relations=5,
        )

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService, "get_character_network", AsyncMock(return_value=mock_network)
            ),
        ):
            result = await agent.query_character_network("张三", depth=2)

            assert result is not None
            assert result.character_name == "张三"

    @pytest.mark.asyncio
    async def test_query_character_network_exception(self, agent):
        """测试查询角色网络异常."""
        from backend.services.graph_query_service import GraphQueryService

        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService, "get_character_network", AsyncMock(side_effect=Exception("错误"))
            ),
        ):
            result = await agent.query_character_network("张三")

            assert result is None

    @pytest.mark.asyncio
    async def test_query_character_path_success(self, agent):
        """测试成功查询角色路径."""
        from backend.services.graph_query_service import CharacterPath, GraphQueryService, PathNode

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_path = CharacterPath(
            from_character="张三",
            to_character="李四",
            nodes=[
                PathNode(id="1", name="张三", label="Character"),
                PathNode(id="2", name="李四", label="Character"),
            ],
            edges=[],
            length=1,
        )

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService, "find_shortest_path", AsyncMock(return_value=mock_path)
            ),
        ):
            result = await agent.query_character_path("张三", "李四")

            assert result is not None
            assert result.from_character == "张三"

    @pytest.mark.asyncio
    async def test_query_influence_success(self, agent):
        """测试成功查询影响力."""
        from backend.services.graph_query_service import GraphQueryService, InfluenceReport

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_influence = InfluenceReport(
            character_id="char-001",
            character_name="张三",
            influence_score=50.0,
            direct_relations=5,
            indirect_relations=10,
            centrality_score=2.5,
            key_connections=[],
        )

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService,
                "find_character_influence",
                AsyncMock(return_value=mock_influence),
            ),
        ):
            result = await agent.query_influence("张三")

            assert result is not None
            assert result.influence_score == 50.0

    @pytest.mark.asyncio
    async def test_check_conflicts_success(self, agent):
        """测试成功检测冲突."""
        from backend.services.graph_query_service import ConflictReport, GraphQueryService

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_conflicts = [
            ConflictReport(
                conflict_type="test",
                description="测试冲突",
                severity="high",
                characters=["张三"],
            )
        ]

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService,
                "check_consistency_conflicts",
                AsyncMock(return_value=mock_conflicts),
            ),
        ):
            result = await agent.check_conflicts()

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_pending_foreshadowings_success(self, agent):
        """测试成功查询待回收伏笔."""
        from backend.services.graph_query_service import GraphQueryService

        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService,
                "find_pending_foreshadowings",
                AsyncMock(
                    return_value=[
                        {"id": "fore-001", "content": "玉佩"},
                    ]
                ),
            ),
        ):
            result = await agent.query_pending_foreshadowings(10)

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_event_timeline_success(self, agent):
        """测试成功查询事件时间线."""
        from backend.services.graph_query_service import GraphQueryService

        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService,
                "get_event_timeline",
                AsyncMock(
                    return_value=[
                        {"id": "evt-001", "name": "事件"},
                    ]
                ),
            ),
        ):
            result = await agent.query_event_timeline("张三")

            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_all_relationships_success(self, agent):
        """测试成功查询所有关系."""
        from backend.services.graph_query_service import GraphQueryService

        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService,
                "get_all_relationships",
                AsyncMock(
                    return_value=[
                        {"from_name": "张三", "to_name": "李四"},
                    ]
                ),
            ),
        ):
            result = await agent.query_all_relationships()

            assert len(result) == 1


class TestFormattingMethods:
    """格式化方法测试."""

    @pytest.fixture
    def agent(self):
        """创建Agent实例."""
        agent = MockAgent()
        agent.set_graph_context("novel-001")
        return agent

    def test_format_network_context_with_data(self, agent):
        """测试格式化有数据的网络上下文."""
        from backend.services.graph_query_service import CharacterNetwork

        network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[
                {"properties": {"type": "friend"}, "target_name": "李四"},
            ],
            total_relations=1,
        )

        result = agent.format_network_context(network)

        assert "张三" in result
        assert "总关系数: 1" in result

    def test_format_network_context_empty(self, agent):
        """测试格式化空网络上下文."""
        result = agent.format_network_context(None)

        assert "无角色关系数据" in result

    def test_format_path_context_with_data(self, agent):
        """测试格式化有数据的路径上下文."""
        from backend.services.graph_query_service import CharacterPath, PathEdge, PathNode

        path = CharacterPath(
            from_character="张三",
            to_character="李四",
            nodes=[
                PathNode(id="1", name="张三", label="Character"),
                PathNode(id="2", name="李四", label="Character"),
            ],
            edges=[
                PathEdge(from_id="1", to_id="2", relation_type="FRIEND"),
            ],
            length=1,
        )

        result = agent.format_path_context(path)

        assert "张三" in result
        assert "李四" in result

    def test_format_path_context_empty(self, agent):
        """测试格式化空路径上下文."""
        result = agent.format_path_context(None)

        assert "无路径数据" in result

    def test_format_conflicts_context_with_data(self, agent):
        """测试格式化有冲突的上下文."""
        from backend.services.graph_query_service import ConflictReport

        conflicts = [
            ConflictReport(
                conflict_type="dead_character",
                description="已死亡角色出现",
                severity="high",
                characters=["张三"],
                details="第5章死亡，第10章出现",
            )
        ]

        result = agent.format_conflicts_context(conflicts)

        assert "一致性问题" in result
        assert "已死亡角色出现" in result
        assert "[高]" in result

    def test_format_conflicts_context_empty(self, agent):
        """测试格式化无冲突的上下文."""
        result = agent.format_conflicts_context([])

        assert "无一致性冲突" in result

    def test_format_foreshadowings_context_with_data(self, agent):
        """测试格式化有伏笔的上下文."""
        foreshadowings = [
            {
                "content": "神秘玉佩的来历",
                "planted_chapter": 3,
                "expected_chapter": 20,
                "related_characters": ["张三"],
                "importance": 8,
            }
        ]

        result = agent.format_foreshadowings_context(foreshadowings)

        assert "待回收" in result
        assert "玉佩" in result
        assert "第3章" in result

    def test_format_foreshadowings_context_empty(self, agent):
        """测试格式化无伏笔的上下文."""
        result = agent.format_foreshadowings_context([])

        assert "无待回收伏笔" in result

    def test_format_influence_context_with_data(self, agent):
        """测试格式化有影响力数据的上下文."""
        from backend.services.graph_query_service import InfluenceReport

        influence = InfluenceReport(
            character_id="char-001",
            character_name="张三",
            influence_score=50.0,
            direct_relations=5,
            indirect_relations=10,
            centrality_score=2.5,
            key_connections=["李四", "王五"],
        )

        result = agent.format_influence_context(influence)

        assert "张三" in result
        assert "直接关系数: 5" in result
        assert "李四" in result

    def test_format_influence_context_empty(self, agent):
        """测试格式化无影响力数据的上下文."""
        result = agent.format_influence_context(None)

        assert "无影响力数据" in result


class TestComprehensiveMethods:
    """综合查询方法测试."""

    @pytest.fixture
    def agent(self):
        """创建Agent实例."""
        agent = MockAgent()
        agent.set_graph_context("novel-001")
        # 确保图数据库启用
        agent._graph_enabled = True
        return agent

    @pytest.mark.asyncio
    async def test_get_full_character_context_success(self, agent):
        """测试获取完整角色上下文."""
        from backend.services.graph_query_service import (
            CharacterNetwork,
            GraphQueryService,
            InfluenceReport,
        )

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[],
            total_relations=5,
        )

        mock_influence = InfluenceReport(
            character_id="char-001",
            character_name="张三",
            influence_score=50.0,
            direct_relations=5,
            indirect_relations=10,
            centrality_score=2.5,
            key_connections=[],
        )

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService, "get_character_network", AsyncMock(return_value=mock_network)
            ),
            patch.object(
                GraphQueryService,
                "find_character_influence",
                AsyncMock(return_value=mock_influence),
            ),
            patch.object(
                GraphQueryService, "check_consistency_conflicts", AsyncMock(return_value=[])
            ),
        ):
            result = await agent.get_full_character_context("张三")

            assert "张三" in result

    @pytest.mark.asyncio
    async def test_get_full_character_context_with_conflicts(self, agent):
        """测试获取包含冲突的完整角色上下文."""
        from backend.services.graph_query_service import (
            CharacterNetwork,
            ConflictReport,
            GraphQueryService,
        )

        mock_client = MagicMock()
        mock_client.is_connected = True

        mock_network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[],
            total_relations=5,
        )

        mock_conflicts = [
            ConflictReport(
                conflict_type="test",
                description="测试冲突",
                severity="high",
                characters=["张三"],
            )
        ]

        with (
            patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client),
            patch.object(
                GraphQueryService, "get_character_network", AsyncMock(return_value=mock_network)
            ),
            patch.object(
                GraphQueryService, "find_character_influence", AsyncMock(return_value=None)
            ),
            patch.object(
                GraphQueryService,
                "check_consistency_conflicts",
                AsyncMock(return_value=mock_conflicts),
            ),
        ):
            result = await agent.get_full_character_context("张三", include_conflicts=True)

            assert "测试冲突" in result

    @pytest.mark.asyncio
    async def test_get_novel_graph_summary_success(self, agent):
        """测试获取小说图数据摘要成功."""
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.execute_query = AsyncMock(
            return_value=[
                {"label": "Character", "count": 10},
                {"label": "Location", "count": 5},
            ]
        )

        with patch("agents.graph_query_mixin.get_neo4j_client", return_value=mock_client):
            result = await agent.get_novel_graph_summary()

            assert "图数据库概览" in result
            assert "角色" in result
            assert "地点" in result

    @pytest.mark.asyncio
    async def test_get_novel_graph_summary_disabled(self):
        """测试图数据库禁用时的摘要."""
        agent = MockAgent()
        agent._graph_enabled = False

        result = await agent.get_novel_graph_summary()

        assert "未启用" in result


class TestConvenienceFunctions:
    """便捷函数测试."""

    @pytest.mark.asyncio
    async def test_quick_query_network(self):
        """测试快速查询角色网络."""
        from backend.services.graph_query_service import CharacterNetwork

        mock_network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[],
            total_relations=5,
        )

        with patch(
            "agents.graph_query_mixin.GraphQueryMixin.query_character_network",
            AsyncMock(return_value=mock_network),
        ):
            from agents.graph_query_mixin import quick_query_network

            result = await quick_query_network("novel-001", "张三")

            assert "张三" in result

    @pytest.mark.asyncio
    async def test_quick_check_conflicts(self):
        """测试快速检测冲突."""
        from backend.services.graph_query_service import ConflictReport

        mock_conflicts = [
            ConflictReport(
                conflict_type="test",
                description="测试",
                severity="high",
                characters=[],
            )
        ]

        with patch(
            "agents.graph_query_mixin.GraphQueryMixin.check_conflicts",
            AsyncMock(return_value=mock_conflicts),
        ):
            from agents.graph_query_mixin import quick_check_conflicts

            result = await quick_check_conflicts("novel-001")

            assert "测试" in result

    @pytest.mark.asyncio
    async def test_quick_query_pending_foreshadowings(self):
        """测试快速查询待回收伏笔."""
        with patch(
            "agents.graph_query_mixin.GraphQueryMixin.query_pending_foreshadowings",
            AsyncMock(return_value=[{"content": "伏笔"}]),
        ):
            from agents.graph_query_mixin import quick_query_pending_foreshadowings

            result = await quick_query_pending_foreshadowings("novel-001", 10)

            assert "伏笔" in result
