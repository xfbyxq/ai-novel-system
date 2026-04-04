"""图数据同步服务单元测试.

测试 backend/services/graph_sync_service.py 中的同步功能。
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestSyncResult:
    """SyncResult 数据类测试."""

    def test_sync_result_creation(self):
        """测试同步结果创建."""
        from backend.services.graph_sync_service import SyncResult

        result = SyncResult(
            success=True,
            novel_id="novel-001",
            sync_type="full",
            entities_created=10,
            entities_updated=5,
            relationships_created=8,
        )

        assert result.success is True
        assert result.novel_id == "novel-001"
        assert result.sync_type == "full"
        assert result.entities_created == 10
        assert result.entities_updated == 5
        assert result.relationships_created == 8
        assert result.errors == []

    def test_sync_result_to_dict(self):
        """测试同步结果转换为字典."""
        from backend.services.graph_sync_service import SyncResult

        result = SyncResult(
            success=True,
            novel_id="novel-001",
            sync_type="character",
            entities_created=5,
            errors=["警告信息"],
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["novel_id"] == "novel-001"
        assert result_dict["sync_type"] == "character"
        assert result_dict["entities_created"] == 5
        assert "警告信息" in result_dict["errors"]

    def test_sync_result_with_error(self):
        """测试失败的同步结果."""
        from backend.services.graph_sync_service import SyncResult

        result = SyncResult(
            success=False,
            novel_id="novel-001",
            sync_type="full",
            errors=["连接失败", "超时"],
        )

        assert result.success is False
        assert len(result.errors) == 2


class TestGraphSyncServiceInit:
    """GraphSyncService 初始化测试."""

    def test_service_initialization(self):
        """测试服务初始化."""
        from backend.services.graph_sync_service import GraphSyncService

        mock_client = MagicMock()
        mock_db = MagicMock()

        service = GraphSyncService(mock_client, mock_db)

        assert service.client is mock_client
        assert service.db is mock_db


class TestGraphSyncServiceSync:
    """GraphSyncService 同步功能测试."""

    @pytest.fixture
    def mock_neo4j_client(self):
        """创建mock Neo4j客户端."""
        client = MagicMock()
        client.create_node = AsyncMock(return_value="node-001")
        client.create_relationship = AsyncMock(return_value=True)
        client.delete_novel_graph = AsyncMock(return_value=10)
        return client

    @pytest.fixture
    def mock_db_session(self):
        """创建mock数据库会话."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_neo4j_client, mock_db_session):
        """创建服务实例."""
        from backend.services.graph_sync_service import GraphSyncService

        return GraphSyncService(mock_neo4j_client, mock_db_session)

    @pytest.mark.asyncio
    async def test_sync_characters_success(self, service, mock_neo4j_client):
        """测试同步角色成功."""
        from core.models.character import Character

        # 创建mock角色
        char1 = MagicMock(spec=Character)
        char1.id = uuid4()
        char1.name = "张三"
        char1.role_type = "protagonist"
        char1.gender = "male"
        char1.age = 25
        char1.status = "alive"
        char1.first_appearance_chapter = 1
        char1.relationships = []

        char2 = MagicMock(spec=Character)
        char2.id = uuid4()
        char2.name = "李四"
        char2.role_type = "supporting"
        char2.gender = "female"
        char2.age = 22
        char2.status = "alive"
        char2.first_appearance_chapter = 1
        char2.relationships = []

        novel_id = uuid4()
        result = await service.sync_characters(novel_id, [char1, char2])

        assert result.success is True
        assert result.entities_created == 2
        assert result.sync_type == "character"

    @pytest.mark.asyncio
    async def test_sync_characters_with_relationships(self, service, mock_neo4j_client):
        """测试同步带关系的角色."""
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

        novel_id = uuid4()
        result = await service.sync_characters(novel_id, [char1, char2])

        assert result.success is True

    @pytest.mark.asyncio
    async def test_sync_characters_failure(self, service, mock_neo4j_client):
        """测试同步角色失败."""
        mock_neo4j_client.create_node = AsyncMock(side_effect=Exception("连接失败"))

        from core.models.character import Character

        char = MagicMock(spec=Character)
        char.id = uuid4()
        char.name = "测试角色"
        char.role_type = "minor"
        char.gender = None
        char.age = None
        char.status = "alive"
        char.first_appearance_chapter = None
        char.relationships = []

        novel_id = uuid4()
        result = await service.sync_characters(novel_id, [char])

        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_sync_chapter_entities(self, service, mock_neo4j_client):
        """测试同步章节实体."""
        novel_id = uuid4()
        result = await service.sync_chapter_entities(novel_id, 1, "这是第一章的内容...")

        assert result.success is True
        assert result.entities_created == 1
        assert result.sync_type == "chapter"

    @pytest.mark.asyncio
    async def test_sync_character_relationships(self, service, mock_neo4j_client, mock_db_session):
        """测试同步单个角色的关系."""
        from core.models.character import Character

        char_id = uuid4()
        char = MagicMock(spec=Character)
        char.id = char_id
        char.name = "张三"
        # relationships应该是字典格式: {角色名: 关系类型}
        char.relationships = {"李四": "friend"}

        # Mock数据库查询返回角色列表
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        # 返回角色列表用于构建名称-ID映射
        mock_char1 = MagicMock()
        mock_char1.id = char_id
        mock_char1.name = "张三"
        mock_char2 = MagicMock()
        mock_char2.id = uuid4()
        mock_char2.name = "李四"
        mock_scalars.all.return_value = [mock_char1, mock_char2]
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_result

        novel_id = uuid4()
        result = await service.sync_character_relationships(novel_id, char)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_sync_character_relationships_empty(self, service, mock_neo4j_client):
        """测试同步无关系的角色."""
        from core.models.character import Character

        char = MagicMock(spec=Character)
        char.id = uuid4()
        char.name = "孤独角色"
        char.relationships = None

        novel_id = uuid4()
        result = await service.sync_character_relationships(novel_id, char)

        assert result.success is True
        assert result.relationships_created == 0

    @pytest.mark.asyncio
    async def test_sync_foreshadowing(self, service, mock_neo4j_client):
        """测试同步伏笔."""
        novel_id = uuid4()
        success = await service.sync_foreshadowing(
            novel_id,
            "fore-001",
            "神秘的玉佩",
            5,
            "item",
            "pending",
            ["张三", "李四"],
        )

        assert success is True
        mock_neo4j_client.create_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_foreshadowing_failure(self, service, mock_neo4j_client):
        """测试同步伏笔失败."""
        mock_neo4j_client.create_node = AsyncMock(side_effect=Exception("错误"))

        novel_id = uuid4()
        success = await service.sync_foreshadowing(
            novel_id,
            "fore-001",
            "测试伏笔",
            1,
            "plot",
            "pending",
            [],
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_delete_novel_graph(self, service, mock_neo4j_client):
        """测试删除小说图数据."""
        novel_id = uuid4()
        count = await service.delete_novel_graph(novel_id)

        assert count == 10
        mock_neo4j_client.delete_novel_graph.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_novel_graph_failure(self, service, mock_neo4j_client):
        """测试删除小说图数据失败."""
        mock_neo4j_client.delete_novel_graph = AsyncMock(side_effect=Exception("错误"))

        novel_id = uuid4()
        count = await service.delete_novel_graph(novel_id)

        assert count == 0


class TestGraphSyncServiceFullSync:
    """GraphSyncService 全量同步测试."""

    @pytest.fixture
    def mock_neo4j_client(self):
        """创建mock Neo4j客户端."""
        client = MagicMock()
        client.create_node = AsyncMock(return_value="node-001")
        client.create_relationship = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def mock_db_session(self):
        """创建mock数据库会话."""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_neo4j_client, mock_db_session):
        """创建服务实例."""
        from backend.services.graph_sync_service import GraphSyncService

        return GraphSyncService(mock_neo4j_client, mock_db_session)

    @pytest.mark.asyncio
    async def test_sync_novel_full_success(self, service, mock_db_session):
        """测试全量同步成功."""
        # Mock角色查询
        mock_char_result = MagicMock()
        mock_char_scalars = MagicMock()
        mock_char_scalars.all.return_value = []
        mock_char_result.scalars.return_value = mock_char_scalars

        # Mock世界观查询
        mock_world_result = MagicMock()
        mock_world_result.scalar_one_or_none.return_value = None

        # Mock大纲查询
        mock_outline_result = MagicMock()
        mock_outline_result.scalar_one_or_none.return_value = None

        mock_db_session.execute.side_effect = [
            mock_char_result,
            mock_world_result,
            mock_outline_result,
        ]

        novel_id = uuid4()
        result = await service.sync_novel_full(novel_id)

        assert result.success is True
        assert result.sync_type == "full"

    @pytest.mark.asyncio
    async def test_sync_novel_full_with_exception(self, service, mock_db_session):
        """测试全量同步异常."""
        mock_db_session.execute.side_effect = Exception("数据库错误")

        novel_id = uuid4()
        result = await service.sync_novel_full(novel_id)

        assert result.success is False
        assert len(result.errors) > 0


class TestConvenienceFunctions:
    """便捷函数测试."""

    @pytest.mark.asyncio
    async def test_sync_novel_to_graph_disabled(self):
        """测试图数据库禁用时同步."""
        with patch("core.graph.neo4j_client.get_neo4j_client", return_value=None):
            from backend.services.graph_sync_service import sync_novel_to_graph

            novel_id = uuid4()
            mock_db = MagicMock()

            result = await sync_novel_to_graph(novel_id, mock_db)

            assert result.success is False
            assert "未启用" in result.errors[0]

    @pytest.mark.asyncio
    async def test_sync_novel_to_graph_not_connected(self):
        """测试客户端未连接时同步."""
        mock_client = MagicMock()
        mock_client.is_connected = False

        with patch("core.graph.neo4j_client.get_neo4j_client", return_value=mock_client):
            from backend.services.graph_sync_service import sync_novel_to_graph

            novel_id = uuid4()
            mock_db = MagicMock()

            result = await sync_novel_to_graph(novel_id, mock_db)

            assert result.success is False
