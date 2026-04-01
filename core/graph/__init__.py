"""图数据库模块 - Neo4j图存储和分析能力.

本模块提供图数据库的连接管理、数据模型、查询服务等功能，
用于存储和分析小说中的实体关系网络。

主要组件:
    - Neo4jClient: Neo4j连接客户端
    - GraphModels: 图节点和关系的Python模型
    - GraphExceptions: 图数据库异常定义
"""

from core.graph.graph_exceptions import (
    GraphConnectionError,
    GraphError,
    GraphQueryError,
    GraphSyncError,
    NodeNotFoundError,
    RelationshipError,
)
from core.graph.graph_models import (
    CharacterNode,
    EventNode,
    FactionNode,
    ForeshadowingNode,
    GraphEdge,
    GraphNode,
    LocationNode,
    NodeType,
    RelationType,
)
from core.graph.neo4j_client import Neo4jClient
from core.graph.relationship_mapper import RelationshipMapper

__all__ = [
    # Client
    "Neo4jClient",
    # Models
    "GraphNode",
    "CharacterNode",
    "LocationNode",
    "EventNode",
    "FactionNode",
    "ForeshadowingNode",
    "GraphEdge",
    "NodeType",
    "RelationType",
    # Exceptions
    "GraphError",
    "GraphConnectionError",
    "GraphQueryError",
    "GraphSyncError",
    "NodeNotFoundError",
    "RelationshipError",
    # Utils
    "RelationshipMapper",
]
