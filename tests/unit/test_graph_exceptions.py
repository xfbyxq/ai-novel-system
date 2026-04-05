"""图数据库异常单元测试.

测试 core/graph/graph_exceptions.py 中的异常类。
"""

import pytest


class TestGraphError:
    """GraphError 基础异常测试."""

    def test_graph_error_basic(self):
        """测试基础图异常."""
        from core.graph.graph_exceptions import GraphError

        error = GraphError("测试错误")

        assert error.message == "测试错误"
        assert str(error) == "测试错误"

    def test_graph_error_with_details(self):
        """测试带详细信息的图异常."""
        from core.graph.graph_exceptions import GraphError

        error = GraphError("测试错误", "详细错误信息")

        assert error.message == "测试错误"
        assert error.details == "详细错误信息"
        assert "详细错误信息" in str(error)


class TestGraphConnectionError:
    """GraphConnectionError 连接异常测试."""

    def test_connection_error_default_message(self):
        """测试连接异常默认消息."""
        from core.graph.graph_exceptions import GraphConnectionError

        error = GraphConnectionError()

        assert error.message == "无法连接到图数据库"
        assert "无法连接到图数据库" in str(error)

    def test_connection_error_with_details(self):
        """测试带详细信息的连接异常."""
        from core.graph.graph_exceptions import GraphConnectionError

        error = GraphConnectionError("连接超时", "URI: bolt://localhost:7687")

        assert error.message == "连接超时"
        assert "URI" in error.details

    def test_connection_error_inheritance(self):
        """测试连接异常继承关系."""
        from core.graph.graph_exceptions import GraphConnectionError, GraphError

        error = GraphConnectionError()
        assert isinstance(error, GraphError)


class TestGraphQueryError:
    """GraphQueryError 查询异常测试."""

    def test_query_error_default_message(self):
        """测试查询异常默认消息."""
        from core.graph.graph_exceptions import GraphQueryError

        error = GraphQueryError()

        assert error.message == "图查询执行失败"

    def test_query_error_with_query(self):
        """测试带查询语句的异常."""
        from core.graph.graph_exceptions import GraphQueryError

        query = "MATCH (n:Character) RETURN n"
        error = GraphQueryError(query=query, details="语法错误")

        assert error.query == query
        assert "查询" in str(error)

    def test_query_error_truncates_long_query(self):
        """测试长查询语句被截断."""
        from core.graph.graph_exceptions import GraphQueryError

        long_query = "MATCH (n) " * 100
        error = GraphQueryError(query=long_query, details="测试")

        # 查询应该被截断到前100个字符
        assert len(error.query) > 100  # 原始查询保存完整
        assert "..." in str(error)  # 但在字符串表示中被截断

    def test_query_error_inheritance(self):
        """测试查询异常继承关系."""
        from core.graph.graph_exceptions import GraphError, GraphQueryError

        error = GraphQueryError()
        assert isinstance(error, GraphError)


class TestGraphSyncError:
    """GraphSyncError 同步异常测试."""

    def test_sync_error_default_message(self):
        """测试同步异常默认消息."""
        from core.graph.graph_exceptions import GraphSyncError

        error = GraphSyncError()

        assert error.message == "图数据同步失败"

    def test_sync_error_with_novel_id(self):
        """测试带小说ID的同步异常."""
        from core.graph.graph_exceptions import GraphSyncError

        error = GraphSyncError(novel_id="novel-001", details="同步失败")

        assert error.novel_id == "novel-001"
        assert "novel-001" in str(error)

    def test_sync_error_inheritance(self):
        """测试同步异常继承关系."""
        from core.graph.graph_exceptions import GraphError, GraphSyncError

        error = GraphSyncError()
        assert isinstance(error, GraphError)


class TestNodeNotFoundError:
    """NodeNotFoundError 节点未找到异常测试."""

    def test_node_not_found_default_message(self):
        """测试节点未找到异常默认消息."""
        from core.graph.graph_exceptions import NodeNotFoundError

        error = NodeNotFoundError()

        assert error.message == "节点未找到"

    def test_node_not_found_with_node_info(self):
        """测试带节点信息的异常."""
        from core.graph.graph_exceptions import NodeNotFoundError

        error = NodeNotFoundError(
            node_label="Character",
            node_id="char-001",
        )

        assert error.node_label == "Character"
        assert error.node_id == "char-001"
        assert "Character" in str(error)
        assert "char-001" in str(error)

    def test_node_not_found_inheritance(self):
        """测试节点未找到异常继承关系."""
        from core.graph.graph_exceptions import GraphError, NodeNotFoundError

        error = NodeNotFoundError()
        assert isinstance(error, GraphError)


class TestRelationshipError:
    """RelationshipError 关系异常测试."""

    def test_relationship_error_default_message(self):
        """测试关系异常默认消息."""
        from core.graph.graph_exceptions import RelationshipError

        error = RelationshipError()

        assert error.message == "关系操作失败"

    def test_relationship_error_with_node_info(self):
        """测试带节点信息的关系异常."""
        from core.graph.graph_exceptions import RelationshipError

        error = RelationshipError(
            from_node="char-001",
            to_node="char-002",
            rel_type="FRIEND",
            details="节点不存在",
        )

        assert error.from_node == "char-001"
        assert error.to_node == "char-002"
        assert error.rel_type == "FRIEND"
        assert "char-001" in str(error)
        assert "char-002" in str(error)
        assert "FRIEND" in str(error)

    def test_relationship_error_inheritance(self):
        """测试关系异常继承关系."""
        from core.graph.graph_exceptions import GraphError, RelationshipError

        error = RelationshipError()
        assert isinstance(error, GraphError)


class TestExceptionRaising:
    """异常抛出测试."""

    def test_raise_graph_error(self):
        """测试抛出图异常."""
        from core.graph.graph_exceptions import GraphError

        with pytest.raises(GraphError) as exc_info:
            raise GraphError("测试异常")

        assert "测试异常" in str(exc_info.value)

    def test_raise_and_catch_connection_error(self):
        """测试抛出和捕获连接异常."""
        from core.graph.graph_exceptions import GraphConnectionError, GraphError

        try:
            raise GraphConnectionError("连接失败", "超时")
        except GraphError as e:
            assert "连接失败" in str(e)

    def test_catch_specific_error(self):
        """测试捕获特定异常类型."""
        from core.graph.graph_exceptions import GraphQueryError

        with pytest.raises(GraphQueryError):
            raise GraphQueryError(query="SELECT 1", details="测试")


class TestExceptionSerialization:
    """异常序列化测试."""

    def test_error_str_representation(self):
        """测试异常字符串表示."""
        from core.graph.graph_exceptions import GraphError

        error = GraphError("错误消息", "详细信息")
        error_str = str(error)

        assert "错误消息" in error_str
        assert "详细信息" in error_str

    def test_error_repr(self):
        """测试异常repr表示."""
        from core.graph.graph_exceptions import GraphConnectionError

        error = GraphConnectionError("连接错误")
        repr_str = repr(error)

        assert "GraphConnectionError" in repr_str
