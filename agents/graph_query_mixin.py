"""图查询混入类.

为Agent提供图数据库查询能力，包括角色关系网络、
路径分析、一致性检测等功能。

使用方式：
    class MyAgent(GraphQueryMixin):
        async def some_method(self):
            network = await self.query_character_network("张三")
"""

from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.services.graph_query_service import (
    CharacterNetwork,
    CharacterPath,
    ConflictReport,
    GraphQueryService,
    InfluenceReport,
)
from core.graph.neo4j_client import get_neo4j_client
from core.logging_config import logger


class GraphQueryMixin:
    """图查询能力混入类.

    为Agent提供便捷的图数据库查询接口。
    可被混入到任何需要图查询能力的Agent类中。
    """

    # 图数据库是否可用
    _graph_enabled: bool = False
    _novel_id: Optional[str] = None

    def set_graph_context(self, novel_id: str) -> None:
        """设置图查询上下文.

        Args:
            novel_id: 小说ID
        """
        self._novel_id = novel_id
        self._graph_enabled = settings.ENABLE_GRAPH_DATABASE

    async def query_character_network(
        self, character_name: str, depth: int = 2
    ) -> Optional[CharacterNetwork]:
        """查询角色的关系网络.

        Args:
            character_name: 角色名称
            depth: 查询深度（1-5）

        Returns:
            CharacterNetwork实例，查询失败返回None
        """
        if not self._graph_enabled or not self._novel_id:
            reason = "图数据库未启用" if not self._graph_enabled else "小说ID未设置"
            logger.debug(f"[GraphQueryMixin] 跳过图查询: {reason}")
            return None

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return None

        try:
            service = GraphQueryService(client)
            network = await service.get_character_network(
                self._novel_id, character_name, depth
            )
            return network
        except Exception as e:
            logger.error(f"查询角色网络失败: {e}")
            return None

    async def query_character_path(
        self, from_character: str, to_character: str
    ) -> Optional[CharacterPath]:
        """查询两个角色之间的关系路径.

        Args:
            from_character: 起始角色
            to_character: 目标角色

        Returns:
            CharacterPath实例
        """
        if not self._graph_enabled or not self._novel_id:
            return None

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return None

        try:
            service = GraphQueryService(client)
            path = await service.find_shortest_path(
                self._novel_id, from_character, to_character
            )
            return path
        except Exception as e:
            logger.error(f"查询角色路径失败: {e}")
            return None

    async def query_influence(
        self, character_name: str
    ) -> Optional[InfluenceReport]:
        """查询角色影响力.

        Args:
            character_name: 角色名称

        Returns:
            InfluenceReport实例
        """
        if not self._graph_enabled or not self._novel_id:
            return None

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return None

        try:
            service = GraphQueryService(client)
            influence = await service.find_character_influence(
                self._novel_id, character_name
            )
            return influence
        except Exception as e:
            logger.error(f"查询角色影响力失败: {e}")
            return None

    async def check_conflicts(self) -> List[ConflictReport]:
        """检测一致性冲突.

        Returns:
            冲突报告列表
        """
        if not self._graph_enabled or not self._novel_id:
            return []

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return []

        try:
            service = GraphQueryService(client)
            conflicts = await service.check_consistency_conflicts(self._novel_id)
            return conflicts
        except Exception as e:
            logger.error(f"检测冲突失败: {e}")
            return []

    async def query_pending_foreshadowings(
        self, current_chapter: int
    ) -> List[Dict[str, Any]]:
        """查询待回收的伏笔.

        Args:
            current_chapter: 当前章节号

        Returns:
            待回收伏笔列表
        """
        if not self._graph_enabled or not self._novel_id:
            return []

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return []

        try:
            service = GraphQueryService(client)
            foreshadowings = await service.find_pending_foreshadowings(
                self._novel_id, current_chapter
            )
            return foreshadowings
        except Exception as e:
            logger.error(f"查询伏笔失败: {e}")
            return []

    async def query_event_timeline(
        self, character_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询事件时间线.

        Args:
            character_name: 可选的角色名过滤

        Returns:
            事件列表
        """
        if not self._graph_enabled or not self._novel_id:
            return []

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return []

        try:
            service = GraphQueryService(client)
            timeline = await service.get_event_timeline(
                self._novel_id, character_name
            )
            return timeline
        except Exception as e:
            logger.error(f"查询时间线失败: {e}")
            return []

    async def query_all_relationships(
        self, relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询所有角色关系.

        Args:
            relationship_type: 可选的关系类型过滤

        Returns:
            关系列表
        """
        if not self._graph_enabled or not self._novel_id:
            return []

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return []

        try:
            service = GraphQueryService(client)
            relationships = await service.get_all_relationships(
                self._novel_id, relationship_type
            )
            return relationships
        except Exception as e:
            logger.error(f"查询关系失败: {e}")
            return []

    async def query_foreshadowings_by_characters(
        self,
        character_names: List[str],
        current_chapter: Optional[int] = None,
        include_resolved: bool = False,
    ) -> List[Dict[str, Any]]:
        """查询与指定角色相关的伏笔.

        Args:
            character_names: 角色名称列表
            current_chapter: 当前章节号（可选，用于筛选相关伏笔）
            include_resolved: 是否包含已回收的伏笔

        Returns:
            相关伏笔列表
        """
        if not self._graph_enabled or not self._novel_id:
            return []

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return []

        try:
            service = GraphQueryService(client)
            foreshadowings = await service.find_foreshadowings_by_characters(
                self._novel_id, character_names, current_chapter, include_resolved
            )
            return foreshadowings
        except Exception as e:
            logger.error(f"查询角色相关伏笔失败: {e}")
            return []

    async def analyze_character_relationships_in_chapter(
        self, character_names: List[str]
    ) -> Dict[str, Any]:
        """分析章节内角色之间的关系网络.

        识别直接关联、间接关联和潜在关系冲突。

        Args:
            character_names: 本章出场角色名称列表

        Returns:
            关系分析结果，包含：
            - direct_relations: 直接关联的角色对
            - indirect_relations: 通过中间人连接的间接关系
            - potential_conflicts: 潜在的关系冲突
        """
        if not self._graph_enabled or not self._novel_id:
            return {"direct_relations": [], "indirect_relations": [], "potential_conflicts": []}

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return {"direct_relations": [], "indirect_relations": [], "potential_conflicts": []}

        try:
            service = GraphQueryService(client)
            analysis = await service.analyze_character_relationships(
                self._novel_id, character_names
            )
            return analysis
        except Exception as e:
            logger.error(f"分析角色关系失败: {e}")
            return {"direct_relations": [], "indirect_relations": [], "potential_conflicts": []}

    # ============ 上下文格式化方法 ============

    def format_network_context(
        self, network: Optional[CharacterNetwork]
    ) -> str:
        """将角色网络转换为上下文格式.

        Args:
            network: 角色网络对象

        Returns:
            可插入到提示词的上下文文本
        """
        if not network:
            return "（无角色关系数据）"

        return network.to_prompt()

    def format_path_context(
        self, path: Optional[CharacterPath]
    ) -> str:
        """将角色路径转换为上下文格式.

        Args:
            path: 角色路径对象

        Returns:
            可插入到提示词的上下文文本
        """
        if not path:
            return "（无路径数据）"

        return path.to_prompt()

    def format_conflicts_context(
        self, conflicts: List[ConflictReport]
    ) -> str:
        """将冲突报告转换为上下文格式.

        Args:
            conflicts: 冲突报告列表

        Returns:
            可插入到提示词的警告文本
        """
        if not conflicts:
            return "（无一致性冲突）"

        lines = ["## 发现以下一致性问题需要注意："]
        for c in conflicts:
            severity_label = {
                "critical": "严重",
                "high": "高",
                "medium": "中",
                "low": "低",
            }.get(c.severity, "未知")
            lines.append(f"- [{severity_label}] {c.description}")
            if c.details:
                lines.append(f"  详情: {c.details}")

        return "\n".join(lines)

    def format_foreshadowings_context(
        self, foreshadowings: List[Dict[str, Any]]
    ) -> str:
        """将伏笔列表转换为上下文格式.

        Args:
            foreshadowings: 伏笔列表

        Returns:
            可插入到提示词的伏笔提示
        """
        if not foreshadowings:
            return "（无待回收伏笔）"

        lines = ["## 以下伏笔待回收，请考虑在本章或后续章节处理："]
        for f in foreshadowings:
            content = f.get("content", "")
            planted = f.get("planted_chapter", 0)
            expected = f.get("expected_chapter")
            chars = f.get("related_characters", [])
            importance = f.get("importance", 5)

            lines.append(f"- 伏笔: {content[:100]}...")
            lines.append(f"  埋设章节: 第{planted}章")
            if expected:
                lines.append(f"  预计回收: 第{expected}章")
            if chars:
                lines.append(f"  相关角色: {', '.join(chars)}")
            lines.append(f"  重要程度: {importance}/10")

        return "\n".join(lines)

    def format_influence_context(
        self, influence: Optional[InfluenceReport]
    ) -> str:
        """将影响力报告转换为上下文格式.

        Args:
            influence: 影力报告对象

        Returns:
            影力摘要文本
        """
        if not influence:
            return "（无影响力数据）"

        lines = [
            f"角色 {influence.character_name} 的影响力分析：",
            f"- 直接关系数: {influence.direct_relations}",
            f"- 间接关系数: {influence.indirect_relations}",
            f"- 中心性分数: {influence.centrality_score:.2f}",
            f"- 影力总分: {influence.influence_score}",
        ]

        if influence.key_connections:
            lines.append(f"- 关键连接: {', '.join(influence.key_connections)}")

        return "\n".join(lines)

    # ============ 综合查询方法 ============

    async def get_full_character_context(
        self, character_name: str, include_conflicts: bool = True
    ) -> str:
        """获取角色的完整图上下文.

        包含关系网络、影响力、路径等信息。

        Args:
            character_name: 角色名称
            include_conflicts: 是否包含冲突检测

        Returns:
            综合上下文文本
        """
        sections = []

        # 查询关系网络
        network = await self.query_character_network(character_name)
        if network:
            sections.append(self.format_network_context(network))

        # 查询影响力
        influence = await self.query_influence(character_name)
        if influence:
            sections.append(self.format_influence_context(influence))

        # 检测冲突（可选）
        if include_conflicts:
            conflicts = await self.check_conflicts()
            char_conflicts = [
                c
                for c in conflicts
                if character_name in c.characters
            ]
            if char_conflicts:
                sections.append(self.format_conflicts_context(char_conflicts))

        if not sections:
            return f"角色 '{character_name}' 无图数据库信息。"

        return "\n\n".join(sections)

    async def get_novel_graph_summary(self) -> str:
        """获取小说的图数据摘要.

        Returns:
            小说图数据概览
        """
        if not self._graph_enabled or not self._novel_id:
            return "（图数据库未启用）"

        client = get_neo4j_client()
        if not client or not client.is_connected:
            return "（图数据库未连接）"

        try:
            # 获取节点统计
            query = """
            MATCH (n {novel_id: $novel_id})
            RETURN labels(n)[0] as label, count(n) as count
            """
            stats = await client.execute_query(
                query, {"novel_id": self._novel_id}
            )

            lines = ["## 小说图数据库概览"]
            for row in stats:
                label = row.get("label", "unknown")
                count = row.get("count", 0)
                label_cn = {
                    "Character": "角色",
                    "Location": "地点",
                    "Event": "事件",
                    "Faction": "势力",
                    "Foreshadowing": "伏笔",
                }.get(label, label)
                lines.append(f"- {label_cn}: {count}个")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"获取图摘要失败: {e}")
            return f"（获取图摘要失败: {e}）"


# 便捷函数供Agent直接使用
async def quick_query_network(
    novel_id: str, character_name: str, depth: int = 2
) -> str:
    """快速查询角色网络并返回上下文文本.

    Args:
        novel_id: 小说ID
        character_name: 角色名称
        depth: 查询深度

    Returns:
        格式化的上下文文本
    """
    mixin = GraphQueryMixin()
    mixin.set_graph_context(novel_id)
    network = await mixin.query_character_network(character_name, depth)
    return mixin.format_network_context(network)


async def quick_check_conflicts(novel_id: str) -> str:
    """快速检测冲突并返回警告文本.

    Args:
        novel_id: 小说ID

    Returns:
        格式化的冲突警告文本
    """
    mixin = GraphQueryMixin()
    mixin.set_graph_context(novel_id)
    conflicts = await mixin.check_conflicts()
    return mixin.format_conflicts_context(conflicts)


async def quick_query_pending_foreshadowings(
    novel_id: str, current_chapter: int
) -> str:
    """快速查询待回收伏笔并返回提示文本.

    Args:
        novel_id: 小说ID
        current_chapter: 当前章节

    Returns:
        格式化的伏笔提示文本
    """
    mixin = GraphQueryMixin()
    mixin.set_graph_context(novel_id)
    foreshadowings = await mixin.query_pending_foreshadowings(current_chapter)
    return mixin.format_foreshadowings_context(foreshadowings)
