"""图数据库异常定义.

定义图数据库操作中可能出现的异常类型。
"""


class GraphError(Exception):
    """图数据库操作的基础异常类."""

    def __init__(self, message: str, details: str = ""):
        """初始化异常.

        Args:
            message: 异常消息
            details: 详细错误信息
        """
        self.message = message
        self.details = details
        super().__init__(f"{message}: {details}" if details else message)


class GraphConnectionError(GraphError):
    """图数据库连接异常.

    当无法连接到Neo4j数据库时抛出。
    """

    def __init__(self, message: str = "无法连接到图数据库", details: str = ""):
        """初始化连接异常."""
        super().__init__(message, details)


class GraphQueryError(GraphError):
    """图数据库查询异常.

    当Cypher查询执行失败时抛出。
    """

    def __init__(self, query: str = "", message: str = "图查询执行失败", details: str = ""):
        """初始化查询异常.

        Args:
            query: 失败的Cypher查询语句
            message: 异常消息
            details: 详细错误信息
        """
        self.query = query
        full_details = f"查询: {query[:100]}...; {details}" if query else details
        super().__init__(message, full_details)


class GraphSyncError(GraphError):
    """图数据同步异常.

    当数据同步到图数据库失败时抛出。
    """

    def __init__(
        self,
        novel_id: str = "",
        message: str = "图数据同步失败",
        details: str = "",
    ):
        """初始化同步异常.

        Args:
            novel_id: 相关的小说ID
            message: 异常消息
            details: 详细错误信息
        """
        self.novel_id = novel_id
        full_details = f"小说ID: {novel_id}; {details}" if novel_id else details
        super().__init__(message, full_details)


class NodeNotFoundError(GraphError):
    """节点未找到异常.

    当查询的节点不存在时抛出。
    """

    def __init__(
        self,
        node_label: str = "",
        node_id: str = "",
        message: str = "节点未找到",
    ):
        """初始化节点未找到异常.

        Args:
            node_label: 节点标签
            node_id: 节点ID
            message: 异常消息
        """
        self.node_label = node_label
        self.node_id = node_id
        details = f"标签: {node_label}, ID: {node_id}" if node_label or node_id else ""
        super().__init__(message, details)


class RelationshipError(GraphError):
    """关系操作异常.

    当关系创建、更新或删除失败时抛出。
    """

    def __init__(
        self,
        from_node: str = "",
        to_node: str = "",
        rel_type: str = "",
        message: str = "关系操作失败",
        details: str = "",
    ):
        """初始化关系异常.

        Args:
            from_node: 源节点ID
            to_node: 目标节点ID
            rel_type: 关系类型
            message: 异常消息
            details: 详细错误信息
        """
        self.from_node = from_node
        self.to_node = to_node
        self.rel_type = rel_type
        rel_info = f"{from_node}-[{rel_type}]->{to_node}"
        full_details = f"关系: {rel_info}; {details}"
        super().__init__(message, full_details)
