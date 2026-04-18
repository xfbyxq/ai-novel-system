"""Neo4j客户端单元测试.

测试 core/graph/neo4j_client.py 中的Neo4j客户端功能。
重点测试安全验证逻辑和基本的客户端行为。
"""

from unittest.mock import MagicMock, patch

import pytest


class TestValidateLabel:
    """_validate_label 安全验证测试."""

    def test_validate_label_allowed(self):
        """测试允许的标签通过验证."""
        from core.graph.neo4j_client import ALLOWED_LABELS, _validate_label

        for label in ALLOWED_LABELS:
            result = _validate_label(label)
            assert result == label

    def test_validate_label_blocked(self):
        """测试不允许的标签被拒绝."""
        from core.graph.graph_exceptions import GraphQueryError
        from core.graph.neo4j_client import _validate_label

        with pytest.raises(GraphQueryError) as exc_info:
            _validate_label("MaliciousLabel")

        assert "无效的节点标签" in str(exc_info.value)

    def test_validate_label_injection_attempt(self):
        """测试Cypher注入尝试被阻止."""
        from core.graph.graph_exceptions import GraphQueryError
        from core.graph.neo4j_client import _validate_label

        # 尝试通过标签进行Cypher注入
        malicious_labels = [
            "Character` DELETE ALL `",
            "Character; DROP DATABASE",
            "Character} RETURN password",
            "Character-(a)-[r]->(b)",
        ]

        for label in malicious_labels:
            with pytest.raises(GraphQueryError):
                _validate_label(label)

    def test_allowed_labels_set(self):
        """测试允许的标签集合内容."""
        from core.graph.neo4j_client import ALLOWED_LABELS

        expected_labels = {"Character", "Location", "Event", "Faction", "Foreshadowing", "Item"}
        assert ALLOWED_LABELS == expected_labels


class TestValidateRelType:
    """_validate_rel_type 安全验证测试."""

    def test_validate_rel_type_allowed(self):
        """测试允许的关系类型通过验证."""
        from core.graph.neo4j_client import ALLOWED_RELATION_TYPES, _validate_rel_type

        for rel_type in ALLOWED_RELATION_TYPES:
            result = _validate_rel_type(rel_type)
            assert result == rel_type

    def test_validate_rel_type_blocked(self):
        """测试不允许的关系类型被拒绝."""
        from core.graph.graph_exceptions import GraphQueryError
        from core.graph.neo4j_client import _validate_rel_type

        with pytest.raises(GraphQueryError) as exc_info:
            _validate_rel_type("MALICIOUS_REL")

        assert "无效的关系类型" in str(exc_info.value)

    def test_validate_rel_type_injection_attempt(self):
        """测试关系类型注入尝试被阻止."""
        from core.graph.graph_exceptions import GraphQueryError
        from core.graph.neo4j_client import _validate_rel_type

        malicious_rel_types = [
            "CHARACTER_RELATION` DELETE `",
            "CHARACTER_RELATION; MATCH (n) DELETE n",
        ]

        for rel_type in malicious_rel_types:
            with pytest.raises(GraphQueryError):
                _validate_rel_type(rel_type)


class TestNeo4jClientInit:
    """Neo4jClient 初始化测试."""

    def test_client_initialization(self):
        """测试客户端初始化."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
                database="neo4j",
            )

            assert client.uri == "bolt://localhost:7687"
            assert client.user == "neo4j"
            assert client.password == "password"
            assert client.database == "neo4j"
            assert client.max_connection_pool_size == 50
            assert client.connection_timeout == 30

    def test_client_initialization_with_custom_params(self):
        """测试自定义参数初始化."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://custom:7687",
                user="admin",
                password="secret",
                database="test_db",
                max_connection_pool_size=100,
                connection_timeout=60,
            )

            assert client.uri == "bolt://custom:7687"
            assert client.user == "admin"
            assert client.database == "test_db"
            assert client.max_connection_pool_size == 100
            assert client.connection_timeout == 60

    def test_client_not_connected_initially(self):
        """测试客户端初始状态未连接."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            assert client.is_connected is False
            assert client._driver is None

    def test_client_init_without_neo4j_package(self):
        """测试缺少neo4j包时初始化失败."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", False):
            from core.graph.neo4j_client import Neo4jClient

            with pytest.raises(ImportError) as exc_info:
                Neo4jClient(
                    uri="bolt://localhost:7687",
                    user="neo4j",
                    password="password",
                )

            assert "neo4j package is required" in str(exc_info.value)


class TestNeo4jClientProperties:
    """Neo4jClient 属性测试."""

    def test_is_connected_property(self):
        """测试 is_connected 属性."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            # 初始状态未连接
            assert client.is_connected is False

            # 模拟连接后
            client._connected = True
            client._driver = MagicMock()
            assert client.is_connected is True

            # 驱动为None时
            client._driver = None
            assert client.is_connected is False


class TestNeo4jClientConnection:
    """Neo4jClient 连接管理测试."""

    def test_close_without_connection(self):
        """测试未连接时关闭."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            # 未连接时关闭不应报错
            client.close()
            assert client.is_connected is False
            assert client._driver is None

    def test_close_with_mock_driver(self):
        """测试关闭mock驱动."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            # 模拟已连接状态
            mock_driver = MagicMock()
            client._driver = mock_driver
            client._connected = True

            client.close()

            mock_driver.close.assert_called_once()
            assert client._driver is None
            assert client._connected is False


class TestNeo4jClientQuery:
    """Neo4jClient 查询执行测试."""

    @pytest.mark.asyncio
    async def test_execute_query_not_connected(self):
        """测试未连接时执行查询失败."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.graph_exceptions import GraphConnectionError
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            with pytest.raises(GraphConnectionError):
                await client.execute_query("MATCH (n) RETURN n")

    @pytest.mark.asyncio
    async def test_create_node_invalid_label(self):
        """测试创建节点使用无效标签."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.graph_exceptions import GraphQueryError
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )
            client._connected = True
            client._driver = MagicMock()

            with pytest.raises(GraphQueryError):
                await client.create_node("InvalidLabel", {"name": "test"})

    @pytest.mark.asyncio
    async def test_create_relationship_invalid_label(self):
        """测试创建关系使用无效标签."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.graph_exceptions import GraphQueryError
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )
            client._connected = True
            client._driver = MagicMock()

            with pytest.raises(GraphQueryError):
                await client.create_relationship(
                    "InvalidLabel",
                    "id1",
                    "Character",
                    "id2",
                    "CHARACTER_RELATION",
                )


class TestNeo4jClientHealthCheck:
    """Neo4jClient 健康检查测试."""

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """测试未连接时的健康检查."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            result = await client.health_check()

            assert result["healthy"] is False
            assert "未连接" in result["message"]
            assert result["uri"] == "bolt://localhost:7687"


class TestGlobalClientFunctions:
    """全局客户端函数测试."""

    def test_get_neo4j_client_disabled(self):
        """测试图数据库禁用时获取客户端."""
        with patch("backend.config.settings.ENABLE_GRAPH_DATABASE", False):
            import core.graph.neo4j_client as module

            module._neo4j_client = None

            client = module.get_neo4j_client()

            assert client is None

    def test_close_neo4j_client(self):
        """测试关闭全局客户端."""
        import core.graph.neo4j_client as module

        mock_client = MagicMock()
        module._neo4j_client = mock_client

        module.close_neo4j_client()

        mock_client.close.assert_called_once()
        assert module._neo4j_client is None

    def test_close_neo4j_client_none(self):
        """测试关闭空的全局客户端."""
        import core.graph.neo4j_client as module

        module._neo4j_client = None

        # 不应该抛出异常
        module.close_neo4j_client()
        assert module._neo4j_client is None


class TestNeo4jClientSession:
    """Neo4jClient 会话上下文管理测试."""

    @pytest.mark.asyncio
    async def test_session_context_manager_not_connected(self):
        """测试会话上下文管理器自动连接."""
        with (
            patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True),
            patch("core.graph.neo4j_client.Neo4jClient.connect"),
        ):
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            async with client.session() as session:
                assert session is client


class TestNeo4jClientTransaction:
    """Neo4jClient 事务测试."""

    @pytest.mark.asyncio
    async def test_execute_transaction_not_connected(self):
        """测试未连接时执行事务失败."""
        with patch("core.graph.neo4j_client.NEO4J_AVAILABLE", True):
            from core.graph.graph_exceptions import GraphConnectionError
            from core.graph.neo4j_client import Neo4jClient

            client = Neo4jClient(
                uri="bolt://localhost:7687",
                user="neo4j",
                password="password",
            )

            with pytest.raises(GraphConnectionError):
                await client.execute_transaction([{"query": "CREATE (n)"}])


class TestSecurityValidation:
    """安全验证综合测试."""

    def test_all_validation_functions_raise_correct_exception(self):
        """测试所有验证函数抛出正确的异常类型."""
        from core.graph.graph_exceptions import GraphQueryError
        from core.graph.neo4j_client import _validate_label, _validate_rel_type

        # 验证标签
        with pytest.raises(GraphQueryError):
            _validate_label("InvalidLabel")

        # 验证关系类型
        with pytest.raises(GraphQueryError):
            _validate_rel_type("InvalidRelType")

    def test_validation_error_messages_contain_helpful_info(self):
        """测试验证错误消息包含有用信息."""
        from core.graph.graph_exceptions import GraphQueryError
        from core.graph.neo4j_client import _validate_label, _validate_rel_type

        # 标签验证错误
        try:
            _validate_label("HackerLabel")
        except GraphQueryError as e:
            assert "HackerLabel" in str(e)
            assert "允许的标签" in str(e)

        # 关系类型验证错误
        try:
            _validate_rel_type("HackerRel")
        except GraphQueryError as e:
            assert "HackerRel" in str(e)
            assert "允许的关系类型" in str(e)
