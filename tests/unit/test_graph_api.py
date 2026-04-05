"""图数据库API端点单元测试.

测试 backend/api/v1/graph.py 中的API端点。
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestGraphHealthEndpoint:
    """健康检查端点测试."""

    @pytest.mark.asyncio
    async def test_health_disabled(self):
        """测试图数据库禁用的健康检查."""
        with patch("backend.config.settings.ENABLE_GRAPH_DATABASE", False):
            from backend.api.v1.graph import get_graph_health

            result = await get_graph_health()

            assert result["enabled"] is False
            assert "未启用" in result["message"]

    @pytest.mark.asyncio
    async def test_health_not_connected(self):
        """测试未连接的健康检查."""
        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=None),
        ):
            from backend.api.v1.graph import get_graph_health

            result = await get_graph_health()

            assert result["enabled"] is True
            assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_health_connected(self):
        """测试已连接的健康检查."""
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.health_check = AsyncMock(return_value={"healthy": True})

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
        ):
            from backend.api.v1.graph import get_graph_health

            result = await get_graph_health()

            assert result["enabled"] is True
            assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """测试健康检查异常."""
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.health_check = AsyncMock(side_effect=Exception("错误"))

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
        ):
            from backend.api.v1.graph import get_graph_health

            result = await get_graph_health()

            assert result["connected"] is False


class TestGraphInitEndpoint:
    """初始化连接端点测试."""

    @pytest.mark.asyncio
    async def test_init_disabled(self):
        """测试图数据库禁用的初始化."""
        with patch("backend.config.settings.ENABLE_GRAPH_DATABASE", False):
            from fastapi import HTTPException

            from backend.api.v1.graph import initialize_graph_connection

            with pytest.raises(HTTPException) as exc_info:
                await initialize_graph_connection()

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_init_success(self):
        """测试初始化成功."""
        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.init_neo4j_client"),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
        ):
            from backend.api.v1.graph import initialize_graph_connection

            result = await initialize_graph_connection()

            assert result["success"] is True


class TestSyncEndpoints:
    """同步端点测试."""

    @pytest.fixture
    def mock_db(self):
        """创建mock数据库会话."""
        db = MagicMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def mock_novel(self):
        """创建mock小说对象."""
        novel = MagicMock()
        novel.id = uuid4()
        novel.title = "测试小说"
        return novel

    @pytest.mark.asyncio
    async def test_sync_disabled(self, mock_db):
        """测试图数据库禁用的同步."""
        with patch("backend.config.settings.ENABLE_GRAPH_DATABASE", False):
            from fastapi import HTTPException

            from backend.api.v1.graph import sync_novel_to_graph_db

            with pytest.raises(HTTPException) as exc_info:
                await sync_novel_to_graph_db(
                    novel_id=uuid4(),
                    background_tasks=MagicMock(),
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_sync_novel_not_found(self, mock_db):
        """测试同步不存在的小说."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=MagicMock()),
        ):
            from fastapi import HTTPException

            from backend.api.v1.graph import sync_novel_to_graph_db

            with pytest.raises(HTTPException) as exc_info:
                await sync_novel_to_graph_db(
                    novel_id=uuid4(),
                    background_tasks=MagicMock(),
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_sync_success(self, mock_db, mock_novel):
        """测试同步成功."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_novel
        mock_db.execute.return_value = mock_result

        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
        ):
            from backend.api.v1.graph import sync_novel_to_graph_db

            result = await sync_novel_to_graph_db(
                novel_id=mock_novel.id,
                background_tasks=MagicMock(),
                db=mock_db,
            )

            assert result["success"] is True
            assert "同步任务已启动" in result["message"]

    @pytest.mark.asyncio
    async def test_get_sync_status(self, mock_db):
        """测试获取同步状态."""
        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.execute_query = AsyncMock(
            return_value=[
                {"label": "Character", "count": 10},
            ]
        )

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
        ):
            from backend.api.v1.graph import get_sync_status

            result = await get_sync_status(novel_id=uuid4(), db=mock_db)

            assert result["enabled"] is True
            assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_clear_graph_data(self, mock_db):
        """测试清除图数据."""
        mock_client = MagicMock()
        mock_client.is_connected = True

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch("backend.api.v1.graph.GraphSyncService") as mock_service,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.delete_novel_graph = AsyncMock(return_value=10)
            mock_service.return_value = mock_service_instance

            from backend.api.v1.graph import clear_graph_data

            result = await clear_graph_data(novel_id=uuid4(), db=mock_db)

            assert result["success"] is True
            assert result["deleted_nodes"] == 10


class TestQueryEndpoints:
    """查询端点测试."""

    @pytest.fixture
    def mock_client(self):
        """创建mock Neo4j客户端."""
        client = MagicMock()
        client.is_connected = True
        client.execute_query = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_character_network_success(self, mock_client):
        """测试获取角色网络成功."""
        from backend.services.graph_query_service import CharacterNetwork

        mock_network = CharacterNetwork(
            character_id="char-001",
            character_name="张三",
            depth=2,
            nodes=[],
            edges=[],
            total_relations=5,
        )

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch(
                "backend.api.v1.graph.get_character_network_async",
                AsyncMock(return_value=mock_network),
            ),
        ):
            from backend.api.v1.graph import get_character_network

            result = await get_character_network(
                novel_id=uuid4(),
                character_name="张三",
                depth=2,
            )

            assert result["success"] is True
            assert result["character_name"] == "张三"

    @pytest.mark.asyncio
    async def test_get_character_network_not_found(self):
        """测试获取不存在的角色网络."""
        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_character_network_async", AsyncMock(return_value=None)),
        ):
            from fastapi import HTTPException

            from backend.api.v1.graph import get_character_network

            with pytest.raises(HTTPException) as exc_info:
                await get_character_network(
                    novel_id=uuid4(),
                    character_name="不存在的角色",
                    depth=2,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_find_character_path_success(self, mock_client):
        """测试查找角色路径成功."""
        from backend.services.graph_query_service import CharacterPath, PathEdge, PathNode

        mock_path = CharacterPath(
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

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch("backend.api.v1.graph.GraphQueryService") as mock_service,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.find_shortest_path = AsyncMock(return_value=mock_path)
            mock_service.return_value = mock_service_instance

            from backend.api.v1.graph import find_character_path

            result = await find_character_path(
                novel_id=uuid4(),
                from_character="张三",
                to_character="李四",
            )

            assert result["success"] is True
            assert result["from_character"] == "张三"

    @pytest.mark.asyncio
    async def test_get_relationships_success(self, mock_client):
        """测试获取关系列表成功."""
        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch("backend.api.v1.graph.GraphQueryService") as mock_service,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.get_all_relationships = AsyncMock(
                return_value=[
                    {"from_name": "张三", "to_name": "李四", "relation_type": "friend"},
                ]
            )
            mock_service.return_value = mock_service_instance

            from backend.api.v1.graph import get_all_relationships

            result = await get_all_relationships(novel_id=uuid4())

            assert result["success"] is True
            assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_check_conflicts_success(self, mock_client):
        """测试检测冲突成功."""
        from backend.services.graph_query_service import ConflictReport

        mock_conflicts = [
            ConflictReport(
                conflict_type="dead_character_appearance",
                description="测试冲突",
                severity="high",
                characters=["张三"],
            )
        ]

        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch("backend.api.v1.graph.GraphQueryService") as mock_service,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.check_consistency_conflicts = AsyncMock(
                return_value=mock_conflicts
            )
            mock_service.return_value = mock_service_instance

            from backend.api.v1.graph import check_consistency_conflicts

            result = await check_consistency_conflicts(novel_id=uuid4())

            assert result["success"] is True
            assert result["total_conflicts"] == 1
            assert result["severity_summary"]["high"] == 1

    @pytest.mark.asyncio
    async def test_get_influence_success(self, mock_client):
        """测试获取影响力成功."""
        from backend.services.graph_query_service import InfluenceReport

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
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch("backend.api.v1.graph.GraphQueryService") as mock_service,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.find_character_influence = AsyncMock(return_value=mock_influence)
            mock_service.return_value = mock_service_instance

            from backend.api.v1.graph import get_character_influence

            result = await get_character_influence(
                novel_id=uuid4(),
                character_name="张三",
            )

            assert result["success"] is True
            assert result["influence"]["character_name"] == "张三"

    @pytest.mark.asyncio
    async def test_get_timeline_success(self, mock_client):
        """测试获取时间线成功."""
        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch("backend.api.v1.graph.GraphQueryService") as mock_service,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.get_event_timeline = AsyncMock(
                return_value=[
                    {"id": "evt-001", "name": "事件1", "chapter": 1},
                ]
            )
            mock_service.return_value = mock_service_instance

            from backend.api.v1.graph import get_event_timeline

            result = await get_event_timeline(novel_id=uuid4())

            assert result["success"] is True
            assert result["total_events"] == 1

    @pytest.mark.asyncio
    async def test_get_pending_foreshadowings_success(self, mock_client):
        """测试获取待回收伏笔成功."""
        with (
            patch("backend.config.settings.ENABLE_GRAPH_DATABASE", True),
            patch("backend.api.v1.graph.get_neo4j_client", return_value=mock_client),
            patch("backend.api.v1.graph.GraphQueryService") as mock_service,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.find_pending_foreshadowings = AsyncMock(
                return_value=[
                    {"id": "fore-001", "content": "玉佩"},
                ]
            )
            mock_service.return_value = mock_service_instance

            from backend.api.v1.graph import get_pending_foreshadowings

            result = await get_pending_foreshadowings(
                novel_id=uuid4(),
                current_chapter=10,
            )

            assert result["success"] is True
            assert result["total"] == 1


class TestExtractEndpoints:
    """实体抽取端点测试."""

    @pytest.fixture
    def mock_db(self):
        """创建mock数据库会话."""
        db = MagicMock()
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_extract_entities_disabled(self, mock_db):
        """测试实体抽取功能禁用."""
        with patch("backend.config.settings.ENABLE_ENTITY_EXTRACTION", False):
            from fastapi import HTTPException

            from backend.api.v1.graph import extract_entities_from_chapter

            with pytest.raises(HTTPException) as exc_info:
                await extract_entities_from_chapter(
                    novel_id=uuid4(),
                    chapter_number=1,
                    chapter_content="内容",
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_extract_entities_success(self, mock_db):
        """测试实体抽取成功."""
        from backend.services.entity_extractor_service import ExtractionResult

        mock_result = ExtractionResult(chapter_number=1)

        # Mock数据库查询返回空角色列表
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result_db = MagicMock()
        mock_result_db.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result_db

        with (
            patch("backend.config.settings.ENABLE_ENTITY_EXTRACTION", True),
            patch(
                "backend.api.v1.graph.extract_chapter_entities", AsyncMock(return_value=mock_result)
            ),
        ):
            from backend.api.v1.graph import extract_entities_from_chapter

            result = await extract_entities_from_chapter(
                novel_id=uuid4(),
                chapter_number=1,
                chapter_content="章节内容",
                db=mock_db,
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_extract_batch_success(self, mock_db):
        """测试批量抽取成功."""
        from backend.services.entity_extractor_service import ExtractionResult

        # Mock数据库查询
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result_db = MagicMock()
        mock_result_db.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result_db

        mock_results = [
            ExtractionResult(chapter_number=1),
            ExtractionResult(chapter_number=2),
        ]

        with (
            patch("backend.config.settings.ENABLE_ENTITY_EXTRACTION", True),
            patch("backend.api.v1.graph.EntityExtractorService") as mock_service,
        ):
            mock_instance = MagicMock()
            mock_instance.extract_entities_batch = AsyncMock(return_value=mock_results)
            mock_service.return_value = mock_instance

            from backend.api.v1.graph import extract_entities_batch

            result = await extract_entities_batch(
                novel_id=uuid4(),
                chapters=[{"chapter_number": 1, "content": "第一章"}],
                db=mock_db,
            )

            assert result["success"] is True
            assert result["total_chapters"] == 2
