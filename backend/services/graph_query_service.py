"""图查询服务.

提供各种图分析查询能力，供Agent和API使用。
包括角色网络查询、路径分析、影响力计算等功能。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.graph.neo4j_client import Neo4jClient
from core.logging_config import logger


@dataclass
class PathNode:
    """路径节点."""

    id: str
    name: str
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PathEdge:
    """路径边."""

    from_id: str
    to_id: str
    relation_type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CharacterPath:
    """角色间路径."""

    from_character: str
    to_character: str
    nodes: List[PathNode]
    edges: List[PathEdge]
    length: int

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        if not self.nodes:
            return f"从{self.from_character}到{self.to_character}没有发现关联路径"

        path_str = " -> ".join(n.name for n in self.nodes)
        relations = []
        for e in self.edges:
            relations.append(f"{e.relation_type}")
        relation_str = " -> ".join(relations)

        return f"路径({self.length}跳): {path_str}\n关系: {relation_str}"


@dataclass
class CharacterNetwork:
    """角色关系网络."""

    character_id: str
    character_name: str
    depth: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    total_relations: int

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        lines = [f"## {self.character_name}的关系网络 ({self.depth}层深度)"]
        lines.append(f"总关系数: {self.total_relations}")

        # 按关系类型分组
        relations_by_type: Dict[str, List[str]] = {}
        for edge in self.edges:
            rel_type = edge.get("properties", {}).get("type", "unknown")
            target_name = edge.get("target_name", "未知")
            if rel_type not in relations_by_type:
                relations_by_type[rel_type] = []
            relations_by_type[rel_type].append(target_name)

        for rel_type, targets in relations_by_type.items():
            lines.append(f"- {rel_type}: {', '.join(targets)}")

        return "\n".join(lines)


@dataclass
class ConflictReport:
    """一致性冲突报告."""

    conflict_type: str
    description: str
    severity: str  # critical/high/medium/low
    characters: List[str]
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "conflict_type": self.conflict_type,
            "description": self.description,
            "severity": self.severity,
            "characters": self.characters,
            "details": self.details,
        }


@dataclass
class InfluenceReport:
    """角色影响力报告."""

    character_id: str
    character_name: str
    influence_score: float
    direct_relations: int
    indirect_relations: int
    centrality_score: float
    key_connections: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "influence_score": self.influence_score,
            "direct_relations": self.direct_relations,
            "indirect_relations": self.indirect_relations,
            "centrality_score": self.centrality_score,
            "key_connections": self.key_connections,
        }


class GraphQueryService:
    """图查询服务.

    提供各种图分析查询能力，供Agent和API使用。
    """

    def __init__(self, neo4j_client: Neo4jClient):
        """初始化图查询服务.

        Args:
            neo4j_client: Neo4j客户端实例
        """
        self.client = neo4j_client

    async def get_character_network(
        self, novel_id: str, character_name: str, depth: int = 2
    ) -> Optional[CharacterNetwork]:
        """获取角色的关系网络.

        Args:
            novel_id: 小说ID
            character_name: 角色名称
            depth: 查询深度（1-5）

        Returns:
            CharacterNetwork实例，角色不存在则返回None
        """
        depth = min(max(1, depth), 5)  # 限制深度范围

        query = f"""
        MATCH (c:Character {{novel_id: $novel_id, name: $name}})
        CALL apoc.path.subgraphAll(c, {{
            maxLevel: {depth},
            relationshipFilter: 'CHARACTER_RELATION'
        }})
        YIELD nodes, relationships
        RETURN c, nodes, relationships
        """

        try:
            result = await self.client.execute_query(
                query, {"novel_id": novel_id, "name": character_name}
            )

            if not result:
                return None

            row = result[0]
            character = row.get("c", {})
            nodes = row.get("nodes", [])
            relationships = row.get("relationships", [])

            # 构建节点列表
            node_list = []
            for n in nodes:
                node_list.append({
                    "id": n.get("id"),
                    "name": n.get("name"),
                    "role_type": n.get("role_type"),
                    "label": "Character",
                })

            # 构建边列表
            edge_list = []
            for r in relationships:
                edge_list.append({
                    "from_id": r.get("from_id") or r.get("source"),
                    "to_id": r.get("to_id") or r.get("target"),
                    "relation_type": "CHARACTER_RELATION",
                    "properties": r.get("properties", {}),
                })

            return CharacterNetwork(
                character_id=character.get("id", ""),
                character_name=character_name,
                depth=depth,
                nodes=node_list,
                edges=edge_list,
                total_relations=len(edge_list),
            )

        except Exception as e:
            logger.error(f"获取角色网络失败: {e}")
            return None

    async def find_shortest_path(
        self, novel_id: str, from_char: str, to_char: str
    ) -> Optional[CharacterPath]:
        """查找两个角色间的最短关系路径.

        Args:
            novel_id: 小说ID
            from_char: 起始角色名称
            to_char: 目标角色名称

        Returns:
            CharacterPath实例，无路径则返回None
        """
        query = """
        MATCH (a:Character {novel_id: $novel_id, name: $from_name})
        MATCH (b:Character {novel_id: $novel_id, name: $to_name})
        MATCH p = shortestPath((a)-[:CHARACTER_RELATION*]-(b))
        RETURN p
        """

        try:
            result = await self.client.execute_query(
                query,
                {
                    "novel_id": novel_id,
                    "from_name": from_char,
                    "to_name": to_char,
                },
            )

            if not result:
                return CharacterPath(
                    from_character=from_char,
                    to_character=to_char,
                    nodes=[],
                    edges=[],
                    length=0,
                )

            # 解析路径（简化处理）
            # path_data = result[0].get("p", {})
            # Neo4j返回的路径需要进一步解析，这里返回简化版本
            return CharacterPath(
                from_character=from_char,
                to_character=to_char,
                nodes=[
                    PathNode(id="", name=from_char, label="Character"),
                    PathNode(id="", name=to_char, label="Character"),
                ],
                edges=[
                    PathEdge(
                        from_id="",
                        to_id="",
                        relation_type="connected",
                    )
                ],
                length=1,
            )

        except Exception as e:
            logger.error(f"查找最短路径失败: {e}")
            return None

    async def get_all_relationships(
        self, novel_id: str, relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取小说中的所有关系边.

        Args:
            novel_id: 小说ID
            relationship_type: 可选的关系类型过滤

        Returns:
            关系边列表
        """
        if relationship_type:
            query = """
            MATCH (a:Character {novel_id: $novel_id})-[r:CHARACTER_RELATION]->(b:Character)
            WHERE r.type = $rel_type
            RETURN a.name as from_name, a.id as from_id,
                   b.name as to_name, b.id as to_id,
                   r.type as relation_type, r.strength as strength
            """
            params = {"novel_id": novel_id, "rel_type": relationship_type}
        else:
            query = """
            MATCH (a:Character {novel_id: $novel_id})-[r:CHARACTER_RELATION]->(b:Character)
            RETURN a.name as from_name, a.id as from_id,
                   b.name as to_name, b.id as to_id,
                   r.type as relation_type, r.strength as strength
            """
            params = {"novel_id": novel_id}

        try:
            result = await self.client.execute_query(query, params)
            return result
        except Exception as e:
            logger.error(f"获取所有关系失败: {e}")
            return []

    async def check_consistency_conflicts(self, novel_id: str) -> List[ConflictReport]:
        """检测关系一致性冲突.

        检测以下类型的问题：
        1. 死亡角色出现在后续章节
        2. 角色同时出现在多个地点
        3. 矛盾的关系（如同时是敌人和朋友）

        Args:
            novel_id: 小说ID

        Returns:
            冲突报告列表
        """
        conflicts = []

        # 检测死亡角色出现
        query_dead = """
        MATCH (c:Character {novel_id: $novel_id, status: 'dead'})
        WHERE c.first_appearance_chapter IS NOT NULL
        MATCH (e:Event {novel_id: $novel_id})
        WHERE e.chapter_number > c.first_appearance_chapter
        AND c.name IN e.participants
        RETURN c.name as character_name, c.first_appearance_chapter as death_chapter,
               e.name as event_name, e.chapter_number as event_chapter
        """

        try:
            result = await self.client.execute_query(
                query_dead, {"novel_id": novel_id}
            )
            for row in result:
                char_name = row.get('character_name', '')
                event_ch = row.get('event_chapter', 0)
                death_ch = row.get('death_chapter', 0)
                conflicts.append(ConflictReport(
                    conflict_type="dead_character_appearance",
                    description=f"已死亡角色{char_name}出现在第{event_ch}章",
                    severity="high",
                    characters=[char_name],
                    details=f"角色在第{death_ch}章后出现",
                ))
        except Exception as e:
            logger.warning(f"检测死亡角色冲突失败: {e}")

        # 检测矛盾关系（敌人和朋友）
        query_conflict_rel = """
        MATCH (a:Character {novel_id: $novel_id})-[r1:CHARACTER_RELATION]->(b:Character)
        WHERE r1.type IN ['enemy', 'rival']
        MATCH (a)-[r2:CHARACTER_RELATION]->(b)
        WHERE r2.type IN ['friend', 'best_friend', 'ally']
        RETURN a.name as char_a, b.name as char_b, r1.type as rel1, r2.type as rel2
        """

        try:
            result = await self.client.execute_query(
                query_conflict_rel, {"novel_id": novel_id}
            )
            for row in result:
                char_a = row.get('char_a', '')
                char_b = row.get('char_b', '')
                rel1 = row.get('rel1', '')
                rel2 = row.get('rel2', '')
                conflicts.append(ConflictReport(
                    conflict_type="contradictory_relationship",
                    description=f"{char_a}与{char_b}同时有敌对和友好关系",
                    severity="medium",
                    characters=[char_a, char_b],
                    details=f"关系: {rel1}和{rel2}",
                ))
        except Exception as e:
            logger.warning(f"检测矛盾关系失败: {e}")

        return conflicts

    async def find_character_influence(
        self, novel_id: str, character_name: str
    ) -> Optional[InfluenceReport]:
        """计算角色影响力.

        基于以下指标：
        1. 直接关系数量
        2. 二度关系数量
        3. 度中心性

        Args:
            novel_id: 小说ID
            character_name: 角色名称

        Returns:
            InfluenceReport实例
        """
        query = """
        MATCH (c:Character {novel_id: $novel_id, name: $name})
        OPTIONAL MATCH (c)-[r1:CHARACTER_RELATION]-(:Character)
        WITH c, count(r1) as direct_relations
        OPTIONAL MATCH (c)-[:CHARACTER_RELATION*1..2]-(:Character)
        WITH c, direct_relations, count(DISTINCT) as total_reachable
        RETURN c.id as id, c.name as name, direct_relations,
               total_reachable - 1 as indirect_relations,
               direct_relations * 1.0 as centrality_score
        """

        try:
            result = await self.client.execute_query(
                query, {"novel_id": novel_id, "name": character_name}
            )

            if not result:
                return None

            row = result[0]
            direct = row.get("direct_relations", 0)
            indirect = row.get("indirect_relations", 0)
            centrality = row.get("centrality_score", 0.0)

            # 计算影响力分数（简化公式）
            influence_score = direct * 10 + indirect * 2

            return InfluenceReport(
                character_id=row.get("id", ""),
                character_name=character_name,
                influence_score=influence_score,
                direct_relations=direct,
                indirect_relations=indirect,
                centrality_score=centrality,
                key_connections=[],  # 可以扩展获取关键连接
            )

        except Exception as e:
            logger.error(f"计算角色影响力失败: {e}")
            return None

    async def get_event_timeline(
        self, novel_id: str, character_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取事件时间线.

        Args:
            novel_id: 小说ID
            character_name: 可选的角色名过滤

        Returns:
            事件列表（按章节排序）
        """
        if character_name:
            query = """
            MATCH (e:Event {novel_id: $novel_id})
            WHERE $char_name IN e.participants
            RETURN e.id as id, e.name as name, e.chapter_number as chapter,
                   e.event_type as type, e.description as description,
                   e.participants as participants
            ORDER BY e.chapter_number
            """
            params = {"novel_id": novel_id, "char_name": character_name}
        else:
            query = """
            MATCH (e:Event {novel_id: $novel_id})
            RETURN e.id as id, e.name as name, e.chapter_number as chapter,
                   e.event_type as type, e.description as description,
                   e.participants as participants
            ORDER BY e.chapter_number
            """
            params = {"novel_id": novel_id}

        try:
            result = await self.client.execute_query(query, params)
            return result
        except Exception as e:
            logger.error(f"获取事件时间线失败: {e}")
            return []

    async def find_pending_foreshadowings(
        self, novel_id: str, current_chapter: int
    ) -> List[Dict[str, Any]]:
        """查找待回收的伏笔.

        Args:
            novel_id: 小说ID
            current_chapter: 当前章节号

        Returns:
            待回收伏笔列表
        """
        query = """
        MATCH (f:Foreshadowing {novel_id: $novel_id, status: 'pending'})
        WHERE f.expected_resolve_chapter <= $current_chapter + 5
        OR f.expected_resolve_chapter IS NULL
        RETURN f.id as id, f.content as content, f.planted_chapter as planted_chapter,
               f.expected_resolve_chapter as expected_chapter, f.importance as importance,
               f.related_characters as related_characters
        ORDER BY f.importance DESC, f.planted_chapter ASC
        """

        try:
            result = await self.client.execute_query(
                query, {"novel_id": novel_id, "current_chapter": current_chapter}
            )
            return result
        except Exception as e:
            logger.error(f"查找待回收伏笔失败: {e}")
            return []

    async def find_foreshadowings_by_characters(
        self,
        novel_id: str,
        character_names: List[str],
        current_chapter: Optional[int] = None,
        include_resolved: bool = False,
    ) -> List[Dict[str, Any]]:
        """查找与指定角色相关的伏笔.

        Args:
            novel_id: 小说ID
            character_names: 角色名称列表
            current_chapter: 当前章节号（可选）
            include_resolved: 是否包含已回收的伏笔

        Returns:
            相关伏笔列表
        """
        status_filter = "" if include_resolved else "status: 'pending'"
        status_match = f"{{{status_filter}}}" if status_filter else ""

        query = f"""
        MATCH (f:Foreshadowing {{novel_id: $novel_id{status_match}}})
        WHERE any(name IN $character_names WHERE name IN f.related_characters)
        RETURN f.id as id, f.content as content, f.planted_chapter as planted_chapter,
               f.expected_resolve_chapter as expected_chapter, f.importance as importance,
               f.related_characters as related_characters, f.status as status
        ORDER BY f.importance DESC, f.planted_chapter ASC
        """

        try:
            result = await self.client.execute_query(
                query, {"novel_id": novel_id, "character_names": character_names}
            )
            return result
        except Exception as e:
            logger.error(f"查找角色相关伏笔失败: {e}")
            return []

    async def analyze_character_relationships(
        self, novel_id: str, character_names: List[str]
    ) -> Dict[str, Any]:
        """分析角色之间的关系网络.

        识别直接关联、间接关联和潜在关系冲突。

        Args:
            novel_id: 小说ID
            character_names: 角色名称列表

        Returns:
            关系分析结果
        """
        result = {
            "direct_relations": [],
            "indirect_relations": [],
            "potential_conflicts": [],
        }

        try:
            # 1. 查询直接关联（这些角色之间的关系）
            direct_query = """
            MATCH (a:Character {novel_id: $novel_id})-[r:CHARACTER_RELATION]->(b:Character)
            WHERE a.name IN $character_names AND b.name IN $character_names
            RETURN a.name as from_char, b.name as to_char, r.type as rel_type,
                   r.strength as strength
            """
            direct_result = await self.client.execute_query(
                direct_query, {"novel_id": novel_id, "character_names": character_names}
            )
            result["direct_relations"] = direct_result

            # 2. 查询间接关联（通过中间人连接）
            indirect_query = """
            MATCH (a:Character {novel_id: $novel_id, name: $char_name})
                      -[:CHARACTER_RELATION*2]->(c:Character)
            WHERE c.name IN $character_names AND a.name <> c.name
            RETURN a.name as from_char, c.name as to_char, 'indirect' as rel_type
            """
            for char_name in character_names:
                indirect_result = await self.client.execute_query(
                    indirect_query,
                    {"novel_id": novel_id, "char_name": char_name, "character_names": character_names},
                )
                for rel in indirect_result:
                    # 避免重复
                    pair = tuple(sorted([rel["from_char"], rel["to_char"]]))
                    if not any(
                        tuple(sorted([r["from_char"], r["to_char"]])) == pair
                        for r in result["direct_relations"]
                    ):
                        result["indirect_relations"].append(rel)

            # 3. 检测潜在冲突（如A是B的敌人，B是C的朋友，A与C的关系张力）
            conflict_query = """
            MATCH (a:Character {novel_id: $novel_id})-[r1:CHARACTER_RELATION]->(b:Character)
            MATCH (b)-[r2:CHARACTER_RELATION]->(c:Character)
            WHERE a.name IN $character_names AND c.name IN $character_names
            AND a.name <> c.name
            AND (
                (r1.type IN ['enemy', 'rival'] AND r2.type IN ['friend', 'ally'])
                OR (r1.type IN ['friend', 'ally'] AND r2.type IN ['enemy', 'rival'])
            )
            RETURN a.name as char_a, b.name as char_b, c.name as char_c,
                   r1.type as rel_ab, r2.type as rel_bc,
                   'potential_conflict' as conflict_type
            """
            conflict_result = await self.client.execute_query(
                conflict_query, {"novel_id": novel_id, "character_names": character_names}
            )
            result["potential_conflicts"] = conflict_result

        except Exception as e:
            logger.error(f"分析角色关系失败: {e}")

        return result

    async def validate_chapter_against_graph(
        self,
        novel_id: str,
        chapter_content: str,
        chapter_characters: List[str],
    ) -> List[ConflictReport]:
        """验证章节内容是否与图数据库一致.

        检查项：
        - 本章建立的新关系是否与已有关系冲突
        - 角色状态变化是否符合图中记录
        - 事件顺序是否与时间线一致

        Args:
            novel_id: 小说ID
            chapter_content: 章节内容
            chapter_characters: 章节出场角色

        Returns:
            冲突报告列表
        """
        conflicts = []

        try:
            # 1. 检查角色状态一致性
            status_query = """
            MATCH (c:Character {novel_id: $novel_id})
            WHERE c.name IN $character_names AND c.status = 'dead'
            RETURN c.name as character_name, c.first_appearance_chapter as chapter
            """
            dead_chars = await self.client.execute_query(
                status_query, {"novel_id": novel_id, "character_names": chapter_characters}
            )

            # 检查死亡角色是否出现在本章
            for char in dead_chars:
                char_name = char.get("character_name", "")
                if char_name and char_name in chapter_content:
                    conflicts.append(
                        ConflictReport(
                            conflict_type="dead_character_appearance",
                            description=f"已死亡角色 '{char_name}' 出现在本章内容中",
                            severity="high",
                            characters=[char_name],
                            details=f"该角色在第 {char.get('chapter', '未知')} 章后已死亡",
                        )
                    )

            # 2. 检查关系冲突
            relation_query = """
            MATCH (a:Character {novel_id: $novel_id})-[r1:CHARACTER_RELATION]->(b:Character)
            WHERE a.name IN $character_names AND b.name IN $character_names
            RETURN a.name as char_a, b.name as char_b, r1.type as rel_type
            """
            existing_relations = await self.client.execute_query(
                relation_query, {"novel_id": novel_id, "character_names": chapter_characters}
            )

            # 检测矛盾关系（如同时是敌人和朋友）
            relation_pairs = {}
            for rel in existing_relations:
                pair = tuple(sorted([rel["char_a"], rel["char_b"]]))
                if pair not in relation_pairs:
                    relation_pairs[pair] = []
                relation_pairs[pair].append(rel["rel_type"])

            for pair, rel_types in relation_pairs.items():
                has_enemy = any(t in ["enemy", "rival"] for t in rel_types)
                has_friend = any(t in ["friend", "ally", "best_friend"] for t in rel_types)
                if has_enemy and has_friend:
                    conflicts.append(
                        ConflictReport(
                            conflict_type="contradictory_relationship",
                            description=f"角色 '{pair[0]}' 与 '{pair[1]}' 同时存在敌对和友好关系",
                            severity="medium",
                            characters=list(pair),
                            details=f"关系类型: {', '.join(rel_types)}",
                        )
                    )

        except Exception as e:
            logger.error(f"验证章节一致性失败: {e}")

        return conflicts


# 便捷函数
async def get_character_network_async(
    novel_id: str, character_name: str, depth: int = 2
) -> Optional[CharacterNetwork]:
    """获取角色网络的便捷函数."""
    from core.graph.neo4j_client import get_neo4j_client

    client = get_neo4j_client()
    if not client or not client.is_connected:
        return None

    service = GraphQueryService(client)
    return await service.get_character_network(novel_id, character_name, depth)
