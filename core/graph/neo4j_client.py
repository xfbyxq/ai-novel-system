"""Neo4j数据库连接客户端.

提供异步的Neo4j数据库连接管理和查询执行能力。
支持连接池、事务管理和健康检查。
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from core.graph.graph_exceptions import GraphConnectionError, GraphQueryError
from core.logging_config import logger

# Neo4j Python Driver (同步驱动，在异步上下文中使用线程池)
try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError, ServiceUnavailable

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j package not installed. Graph database features will be disabled.")


# 允许的节点标签白名单（防止Cypher注入）
ALLOWED_LABELS = {
    "Character", "Location", "Event", "Faction", "Foreshadowing", "Item"
}

# 允许的关系类型白名单
ALLOWED_RELATION_TYPES = {
    "CHARACTER_RELATION", "LOCATED_AT", "PARTICIPATED_IN",
    "MEMBER_OF", "FORESHADOWING_LINKED", "RELATED_TO"
}


def _validate_label(label: str) -> str:
    """验证节点标签是否在允许列表中.

    Args:
        label: 节点标签

    Returns:
        验证通过的标签

    Raises:
        GraphQueryError: 标签不在白名单中
    """
    if label not in ALLOWED_LABELS:
        from core.graph.graph_exceptions import GraphQueryError
        raise GraphQueryError(
            query="validate_label",
            message=f"无效的节点标签: {label}",
            details=f"允许的标签: {ALLOWED_LABELS}"
        )
    return label


def _validate_rel_type(rel_type: str) -> str:
    """验证关系类型是否在允许列表中.

    Args:
        rel_type: 关系类型

    Returns:
        验证通过的关系类型

    Raises:
        GraphQueryError: 关系类型不在白名单中
    """
    if rel_type not in ALLOWED_RELATION_TYPES:
        from core.graph.graph_exceptions import GraphQueryError
        raise GraphQueryError(
            query="validate_rel_type",
            message=f"无效的关系类型: {rel_type}",
            details=f"允许的关系类型: {ALLOWED_RELATION_TYPES}"
        )
    return rel_type


class Neo4jClient:
    """Neo4j数据库连接客户端.

    负责连接管理、事务控制、基础查询执行。
    支持异步操作和连接池管理。

    Usage:
        client = Neo4jClient(uri, user, password)
        await client.connect()
        result = await client.execute_query("MATCH (n) RETURN n LIMIT 10")
        await client.close()
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
    ):
        """初始化Neo4j客户端.

        Args:
            uri: Neo4j连接URI (如 bolt://localhost:7687)
            user: 用户名
            password: 密码
            database: 数据库名称
            max_connection_pool_size: 最大连接池大小
            connection_timeout: 连接超时时间（秒）
        """
        if not NEO4J_AVAILABLE:
            raise ImportError(
                "neo4j package is required. Install with: pip install neo4j"
            )

        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_timeout = connection_timeout

        self._driver = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """检查是否已连接."""
        return self._connected and self._driver is not None

    def connect(self) -> None:
        """建立数据库连接.

        Raises:
            GraphConnectionError: 连接失败时抛出
        """
        if self._driver is not None:
            return

        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout,
            )
            # 验证连接
            self._driver.verify_connectivity()
            self._connected = True
            logger.info(f"Neo4j连接成功: {self.uri}, 数据库: {self.database}")

        except AuthError as e:
            self._driver = None
            self._connected = False
            raise GraphConnectionError(
                "Neo4j认证失败", f"用户: {self.user}, 错误: {str(e)}"
            )
        except ServiceUnavailable as e:
            self._driver = None
            self._connected = False
            raise GraphConnectionError(
                "Neo4j服务不可用", f"URI: {self.uri}, 错误: {str(e)}"
            )
        except Exception as e:
            self._driver = None
            self._connected = False
            raise GraphConnectionError(
                "Neo4j连接失败", str(e)
            )

    def close(self) -> None:
        """关闭数据库连接."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            self._connected = False
            logger.info("Neo4j连接已关闭")

    def _execute_query_sync(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """同步执行Cypher查询（内部方法）.

        Args:
            query: Cypher查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        if not self.is_connected:
            raise GraphConnectionError("未连接到Neo4j数据库")

        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(query, parameters or {})
                # 将结果转换为字典列表
                records = [record.data() for record in result]
                return records

        except Exception as e:
            logger.error(f"Cypher查询失败: {query[:100]}... 错误: {e}")
            raise GraphQueryError(query=query, details=str(e))

    async def execute_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """异步执行Cypher查询.

        使用线程池执行同步查询，提供异步接口。

        Args:
            query: Cypher查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        # 使用 asyncio.get_running_loop() 避免 "no running event loop" 错误
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._execute_query_sync, query, parameters
        )

    async def execute_transaction(
        self, operations: List[Dict[str, Any]]
    ) -> bool:
        """执行事务（多个操作原子执行）.

        Args:
            operations: 操作列表，每个操作包含 query 和 parameters

        Returns:
            是否执行成功
        """
        if not self.is_connected:
            raise GraphConnectionError("未连接到Neo4j数据库")

        def _execute_transaction_sync():
            with self._driver.session(database=self.database) as session:
                with session.begin_transaction() as tx:
                    try:
                        for op in operations:
                            query = op.get("query", "")
                            parameters = op.get("parameters", {})
                            tx.run(query, parameters)
                        tx.commit()
                        return True
                    except Exception as e:
                        tx.rollback()
                        logger.error(f"事务执行失败: {e}")
                        raise GraphQueryError(
                            query="transaction", message="事务执行失败", details=str(e)
                        )

        # 使用 asyncio.get_running_loop() 避免 "no running event loop" 错误
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _execute_transaction_sync)

    async def create_node(
        self, label: str, properties: Dict[str, Any]
    ) -> str:
        """创建节点.

        Args:
            label: 节点标签
            properties: 节点属性

        Returns:
            创建的节点ID
        """
        # 验证标签防止Cypher注入
        _validate_label(label)
        query = f"""
        CREATE (n:{label} $properties)
        RETURN n.id as id
        """
        result = await self.execute_query(query, {"properties": properties})
        return result[0]["id"] if result else ""

    async def create_relationship(
        self,
        from_label: str,
        from_id: str,
        to_label: str,
        to_id: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """创建关系.

        Args:
            from_label: 源节点标签
            from_id: 源节点ID
            to_label: 目标节点标签
            to_id: 目标节点ID
            rel_type: 关系类型
            properties: 关系属性

        Returns:
            是否创建成功
        """
        # 验证标签和关系类型防止Cypher注入
        _validate_label(from_label)
        _validate_label(to_label)
        _validate_rel_type(rel_type)
        query = f"""
        MATCH (a:{from_label} {{id: $from_id}})
        MATCH (b:{to_label} {{id: $to_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $properties
        RETURN r
        """
        try:
            result = await self.execute_query(
                query,
                {
                    "from_id": from_id,
                    "to_id": to_id,
                    "properties": properties or {},
                },
            )
            return len(result) > 0
        except GraphQueryError:
            return False

    async def update_node(
        self, label: str, node_id: str, properties: Dict[str, Any]
    ) -> bool:
        """更新节点属性.

        Args:
            label: 节点标签
            node_id: 节点ID
            properties: 要更新的属性

        Returns:
            是否更新成功
        """
        _validate_label(label)
        query = f"""
        MATCH (n:{label} {{id: $node_id}})
        SET n += $properties
        SET n.updated_at = datetime()
        RETURN n
        """
        try:
            result = await self.execute_query(
                query, {"node_id": node_id, "properties": properties}
            )
            return len(result) > 0
        except GraphQueryError:
            return False

    async def delete_node(self, label: str, node_id: str) -> bool:
        """删除节点及其关系.

        Args:
            label: 节点标签
            node_id: 节点ID

        Returns:
            是否删除成功
        """
        _validate_label(label)
        query = f"""
        MATCH (n:{label} {{id: $node_id}})
        DETACH DELETE n
        RETURN count(n) as deleted
        """
        try:
            result = await self.execute_query(query, {"node_id": node_id})
            return len(result) > 0
        except GraphQueryError:
            return False

    async def find_node(
        self, label: str, node_id: str
    ) -> Optional[Dict[str, Any]]:
        """查找节点.

        Args:
            label: 节点标签
            node_id: 节点ID

        Returns:
            节点属性字典，不存在则返回None
        """
        _validate_label(label)
        query = f"""
        MATCH (n:{label} {{id: $node_id}})
        RETURN n
        """
        result = await self.execute_query(query, {"node_id": node_id})
        if result:
            return result[0].get("n", {})
        return None

    async def find_nodes_by_novel(
        self, novel_id: str, label: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """查找小说的所有节点.

        Args:
            novel_id: 小说ID
            label: 可选的节点标签过滤
            limit: 返回数量限制

        Returns:
            节点列表
        """
        if label:
            _validate_label(label)
            query = f"""
            MATCH (n:{label} {{novel_id: $novel_id}})
            RETURN n
            LIMIT $limit
            """
        else:
            query = """
            MATCH (n {novel_id: $novel_id})
            RETURN n
            LIMIT $limit
            """
        result = await self.execute_query(
            query, {"novel_id": novel_id, "limit": limit}
        )
        return [r.get("n", {}) for r in result]

    async def delete_novel_graph(self, novel_id: str) -> int:
        """删除小说的所有图数据.

        Args:
            novel_id: 小说ID

        Returns:
            删除的节点数量
        """
        query = """
        MATCH (n {novel_id: $novel_id})
        WITH n, count(n) as cnt
        DETACH DELETE n
        RETURN cnt
        """
        result = await self.execute_query(query, {"novel_id": novel_id})
        return result[0].get("cnt", 0) if result else 0

    async def health_check(self) -> Dict[str, Any]:
        """健康检查.

        Returns:
            健康状态字典
        """
        if not self.is_connected:
            return {
                "healthy": False,
                "message": "未连接到Neo4j数据库",
                "uri": self.uri,
            }

        try:
            await self.execute_query("RETURN 1 as test")
            return {
                "healthy": True,
                "message": "Neo4j连接正常",
                "uri": self.uri,
                "database": self.database,
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": str(e),
                "uri": self.uri,
            }

    @asynccontextmanager
    async def session(self):
        """异步会话上下文管理器.

        Usage:
            async with client.session() as session:
                result = await session.execute_query(...)
        """
        if not self.is_connected:
            self.connect()
        try:
            yield self
        finally:
            # 不自动关闭，保持连接池
            pass


# 全局客户端实例（延迟初始化）
_neo4j_client: Optional[Neo4jClient] = None


def get_neo4j_client() -> Optional[Neo4jClient]:
    """获取全局Neo4j客户端实例.

    Returns:
        Neo4jClient实例，如果图数据库未启用或neo4j包未安装则返回None
    """
    global _neo4j_client

    # 检查neo4j包是否可用
    if not NEO4J_AVAILABLE:
        return None

    from backend.config import settings

    if not settings.ENABLE_GRAPH_DATABASE:
        return None

    if _neo4j_client is None:
        _neo4j_client = Neo4jClient(
            uri=settings.NEO4J_EFFECTIVE_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD or "",
            database=settings.NEO4J_DATABASE,
            max_connection_pool_size=settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
            connection_timeout=settings.NEO4J_CONNECTION_TIMEOUT,
        )

    return _neo4j_client


def init_neo4j_client() -> Optional[Neo4jClient]:
    """初始化并连接Neo4j客户端.

    Returns:
        已连接的Neo4jClient实例，如果图数据库未启用则返回None
    """
    client = get_neo4j_client()
    if client and not client.is_connected:
        try:
            client.connect()
            logger.info("Neo4j客户端初始化成功")
        except GraphConnectionError as e:
            logger.warning(f"Neo4j连接失败，图数据库功能将被禁用: {e}")
            return None
    return client


def close_neo4j_client() -> None:
    """关闭全局Neo4j客户端."""
    global _neo4j_client
    if _neo4j_client is not None:
        _neo4j_client.close()
        _neo4j_client = None
