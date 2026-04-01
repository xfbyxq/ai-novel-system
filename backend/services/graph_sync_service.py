"""图数据同步服务.

负责将PostgreSQL中的实体数据同步到Neo4j，
包括增量同步、全量同步、关系抽取。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.graph.graph_models import (
    CharacterNode,
    EventNode,
    FactionNode,
    ForeshadowingNode,
    LocationNode,
    NodeType,
    RelationType,
)
from core.graph.neo4j_client import Neo4jClient
from core.graph.relationship_mapper import RelationshipMapper
from core.logging_config import logger
from core.models.character import Character


@dataclass
class SyncResult:
    """同步结果."""

    success: bool
    novel_id: str
    sync_type: str  # full/chapter/character
    entities_created: int = 0
    entities_updated: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "success": self.success,
            "novel_id": self.novel_id,
            "sync_type": self.sync_type,
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "relationships_created": self.relationships_created,
            "relationships_updated": self.relationships_updated,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class GraphSyncService:
    """图数据同步服务.

    负责将PostgreSQL中的实体数据同步到Neo4j。
    支持全量同步和增量同步。
    """

    def __init__(self, neo4j_client: Neo4jClient, db: AsyncSession):
        """初始化同步服务.

        Args:
            neo4j_client: Neo4j客户端
            db: 数据库会话
        """
        self.client = neo4j_client
        self.db = db

    async def sync_novel_full(self, novel_id: UUID) -> SyncResult:
        """全量同步小说的所有实体.

        同步内容包括：
        1. 所有角色节点和关系
        2. 世界观中的地点和势力
        3. 大纲中的事件

        Args:
            novel_id: 小说ID

        Returns:
            SyncResult
        """
        result = SyncResult(
            success=True,
            novel_id=str(novel_id),
            sync_type="full",
        )

        try:
            logger.info(f"开始全量同步小说 {novel_id}")

            # 1. 同步角色
            char_result = await self._sync_characters(novel_id)
            result.entities_created += char_result.get("created", 0)
            result.entities_updated += char_result.get("updated", 0)
            result.relationships_created += char_result.get("relations_created", 0)

            # 2. 同步世界观（地点、势力）
            world_result = await self._sync_world_setting(novel_id)
            result.entities_created += world_result.get("created", 0)

            # 3. 同步大纲事件
            outline_result = await self._sync_plot_outline(novel_id)
            result.entities_created += outline_result.get("created", 0)

            logger.info(f"全量同步完成: {result.to_dict()}")

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"全量同步失败: {e}")

        finally:
            result.completed_at = datetime.now()

        return result

    async def sync_characters(
        self, novel_id: UUID, characters: List[Character]
    ) -> SyncResult:
        """同步角色节点和关系.

        Args:
            novel_id: 小说ID
            characters: 角色列表

        Returns:
            SyncResult
        """
        result = SyncResult(
            success=True,
            novel_id=str(novel_id),
            sync_type="character",
        )

        try:
            # 构建名称到ID的映射
            name_to_id = {c.name: str(c.id) for c in characters}

            for char in characters:
                # 创建角色节点
                node = CharacterNode(
                    id=str(char.id),
                    novel_id=str(novel_id),
                    name=char.name,
                    role_type=char.role_type or "minor",
                    gender=char.gender,
                    age=char.age,
                    status=char.status or "alive",
                    first_appearance_chapter=char.first_appearance_chapter,
                )

                created = await self.client.create_node(
                    node.label, node.to_neo4j_properties()
                )
                if created:
                    result.entities_created += 1
                else:
                    result.entities_updated += 1

                # 创建角色关系
                if char.relationships:
                    edges = RelationshipMapper.relationships_to_edges(
                        str(char.id), char.relationships, name_to_id
                    )
                    for from_id, to_id, rel_type, props in edges:
                        success = await self.client.create_relationship(
                            NodeType.CHARACTER.value,
                            from_id,
                            NodeType.CHARACTER.value,
                            to_id,
                            RelationType.CHARACTER_RELATION.value,
                            props,
                        )
                        if success:
                            result.relationships_created += 1

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        finally:
            result.completed_at = datetime.now()

        return result

    async def sync_chapter_entities(
        self, novel_id: UUID, chapter_number: int, chapter_content: str
    ) -> SyncResult:
        """章节生成后，同步新出现的实体.

        Args:
            novel_id: 小说ID
            chapter_number: 章节号
            chapter_content: 章节内容

        Returns:
            SyncResult
        """
        result = SyncResult(
            success=True,
            novel_id=str(novel_id),
            sync_type="chapter",
        )

        try:
            # 1. 调用实体抽取服务
            from backend.services.entity_extractor_service import EntityExtractorService

            extractor = EntityExtractorService()

            # 获取已知角色列表
            stmt = select(Character.name).where(Character.novel_id == novel_id)
            db_result = await self.db.execute(stmt)
            known_characters = [row[0] for row in db_result.fetchall()]

            # 执行实体抽取
            extraction_result = await extractor.extract_from_chapter(
                chapter_number=chapter_number,
                chapter_content=chapter_content,
                known_characters=known_characters,
            )

            # 2. 同步角色节点
            for char in extraction_result.characters:
                try:
                    char_node = CharacterNode(
                        id=str(uuid4()),
                        novel_id=str(novel_id),
                        name=char.name,
                        role_type=char.role_type,
                        gender=char.gender or "unknown",
                        first_appearance_chapter=chapter_number,
                    )
                    await self.client.create_node(
                        char_node.label, char_node.to_neo4j_properties()
                    )
                    result.entities_created += 1
                except Exception as e:
                    logger.warning(f"创建角色节点失败 {char.name}: {e}")

            # 3. 同步地点节点
            for loc in extraction_result.locations:
                try:
                    loc_node = LocationNode(
                        id=str(uuid4()),
                        novel_id=str(novel_id),
                        name=loc.name,
                        location_type=loc.location_type,
                        description=loc.description or "",
                    )
                    await self.client.create_node(
                        loc_node.label, loc_node.to_neo4j_properties()
                    )
                    result.entities_created += 1
                except Exception as e:
                    logger.warning(f"创建地点节点失败 {loc.name}: {e}")

            # 4. 同步事件节点
            for event in extraction_result.events:
                try:
                    event_node = EventNode(
                        id=str(uuid4()),
                        novel_id=str(novel_id),
                        name=event.name,
                        chapter_number=chapter_number,
                        event_type=event.event_type,
                        description=event.description or "",
                        importance=event.significance,
                    )
                    await self.client.create_node(
                        event_node.label, event_node.to_neo4j_properties()
                    )
                    result.entities_created += 1
                except Exception as e:
                    logger.warning(f"创建事件节点失败 {event.name}: {e}")

            # 5. 同步关系
            for rel in extraction_result.relationships:
                try:
                    # 查找角色节点ID
                    from_result = await self.client.execute_query(
                        f"MATCH (c:Character {{novel_id: $novel_id, name: $name}}) RETURN c.id",
                        {"novel_id": str(novel_id), "name": rel.from_character},
                    )
                    to_result = await self.client.execute_query(
                        f"MATCH (c:Character {{novel_id: $novel_id, name: $name}}) RETURN c.id",
                        {"novel_id": str(novel_id), "name": rel.to_character},
                    )

                    if from_result and to_result:
                        from_id = from_result[0]["c.id"] if from_result else None
                        to_id = to_result[0]["c.id"] if to_result else None

                        if from_id and to_id:
                            await self.client.create_relationship(
                                "Character", from_id,
                                "Character", to_id,
                                rel.relation_type.upper(),
                                {"strength": rel.strength},
                            )
                            result.relationships_created += 1
                except Exception as e:
                    logger.debug(f"创建关系失败 {rel.from_character}->{rel.to_character}: {e}")

            logger.info(
                f"[GraphSync] 第{chapter_number}章同步完成: "
                f"实体{result.entities_created}个, 关系{result.relationships_created}条"
            )

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"[GraphSync] 第{chapter_number}章同步失败: {e}")

        finally:
            result.completed_at = datetime.now()

        return result

    async def sync_character_relationships(
        self, novel_id: UUID, character: Character
    ) -> SyncResult:
        """同步单个角色的关系.

        Args:
            novel_id: 小说ID
            character: 角色对象

        Returns:
            SyncResult
        """
        result = SyncResult(
            success=True,
            novel_id=str(novel_id),
            sync_type="character_relations",
        )

        try:
            if not character.relationships:
                return result

            # 获取同小说所有角色，构建名称-ID映射
            stmt = select(Character).where(Character.novel_id == novel_id)
            db_result = await self.db.execute(stmt)
            all_chars = db_result.scalars().all()
            name_to_id = {c.name: str(c.id) for c in all_chars}

            # 创建关系
            edges = RelationshipMapper.relationships_to_edges(
                str(character.id), character.relationships, name_to_id
            )

            for from_id, to_id, rel_type, props in edges:
                success = await self.client.create_relationship(
                    NodeType.CHARACTER.value,
                    from_id,
                    NodeType.CHARACTER.value,
                    to_id,
                    RelationType.CHARACTER_RELATION.value,
                    props,
                )
                if success:
                    result.relationships_created += 1

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        finally:
            result.completed_at = datetime.now()

        return result

    async def sync_foreshadowing(
        self,
        novel_id: UUID,
        foreshadowing_id: str,
        content: str,
        planted_chapter: int,
        ftype: str,
        status: str,
        related_characters: List[str],
    ) -> bool:
        """同步伏笔节点.

        Args:
            novel_id: 小说ID
            foreshadowing_id: 伏笔ID
            content: 伏笔内容
            planted_chapter: 埋设章节
            ftype: 伏笔类型
            status: 状态
            related_characters: 关联角色

        Returns:
            是否成功
        """
        node = ForeshadowingNode(
            id=foreshadowing_id,
            novel_id=str(novel_id),
            name=content[:50] if content else f"伏笔-{foreshadowing_id[:8]}",
            content=content,
            planted_chapter=planted_chapter,
            ftype=ftype,
            status=status,
            related_characters=related_characters,
        )

        try:
            await self.client.create_node(node.label, node.to_neo4j_properties())
            return True
        except Exception as e:
            logger.error(f"同步伏笔失败: {e}")
            return False

    async def delete_novel_graph(self, novel_id: UUID) -> int:
        """删除小说的所有图数据.

        Args:
            novel_id: 小说ID

        Returns:
            删除的节点数量
        """
        try:
            return await self.client.delete_novel_graph(str(novel_id))
        except Exception as e:
            logger.error(f"删除图数据失败: {e}")
            return 0

    # 私有方法

    async def _sync_characters(self, novel_id: UUID) -> Dict[str, int]:
        """同步所有角色（内部方法）."""
        result = {"created": 0, "updated": 0, "relations_created": 0}

        stmt = select(Character).where(Character.novel_id == novel_id)
        db_result = await self.db.execute(stmt)
        characters = db_result.scalars().all()

        # 构建名称-ID映射
        name_to_id = {c.name: str(c.id) for c in characters}

        for char in characters:
            node = CharacterNode(
                id=str(char.id),
                novel_id=str(novel_id),
                name=char.name,
                role_type=char.role_type or "minor",
                gender=char.gender,
                age=char.age,
                status=char.status or "alive",
                first_appearance_chapter=char.first_appearance_chapter,
            )

            created = await self.client.create_node(
                node.label, node.to_neo4j_properties()
            )
            if created:
                result["created"] += 1
            else:
                result["updated"] += 1

            # 创建关系
            if char.relationships:
                edges = RelationshipMapper.relationships_to_edges(
                    str(char.id), char.relationships, name_to_id
                )
                for from_id, to_id, rel_type, props in edges:
                    success = await self.client.create_relationship(
                        NodeType.CHARACTER.value,
                        from_id,
                        NodeType.CHARACTER.value,
                        to_id,
                        RelationType.CHARACTER_RELATION.value,
                        props,
                    )
                    if success:
                        result["relations_created"] += 1

        return result

    async def _sync_world_setting(self, novel_id: UUID) -> Dict[str, int]:
        """同步世界观中的地点和势力（内部方法）."""
        result = {"created": 0}

        # 获取世界观设定
        from core.models.world_setting import WorldSetting

        stmt = select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        db_result = await self.db.execute(stmt)
        world_setting = db_result.scalar_one_or_none()

        if not world_setting or not world_setting.setting_data:
            return result

        setting_data = world_setting.setting_data

        # 同步地点
        geography = setting_data.get("geography", {})
        regions = geography.get("major_regions", [])
        for region in regions:
            if isinstance(region, dict):
                node = LocationNode(
                    id=str(uuid4()),
                    novel_id=str(novel_id),
                    name=region.get("name", "未知地点"),
                    location_type="region",
                    description=region.get("description", ""),
                    significance=region.get("importance_level", 5),
                )
                await self.client.create_node(
                    node.label, node.to_neo4j_properties()
                )
                result["created"] += 1

        # 同步势力
        factions = setting_data.get("factions", [])
        for faction in factions:
            if isinstance(faction, dict):
                node = FactionNode(
                    id=str(uuid4()),
                    novel_id=str(novel_id),
                    name=faction.get("name", "未知势力"),
                    faction_type=faction.get("type", "organization"),
                    description=faction.get("description", ""),
                    leader_name=faction.get("leader"),
                )
                await self.client.create_node(
                    node.label, node.to_neo4j_properties()
                )
                result["created"] += 1

        return result

    async def _sync_plot_outline(self, novel_id: UUID) -> Dict[str, int]:
        """同步大纲中的事件（内部方法）."""
        result = {"created": 0}

        from core.models.plot_outline import PlotOutline

        stmt = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
        db_result = await self.db.execute(stmt)
        outline = db_result.scalar_one_or_none()

        if not outline or not outline.outline_data:
            return result

        outline_data = outline.outline_data
        chapters = outline_data.get("chapters", [])

        for chapter in chapters:
            if isinstance(chapter, dict):
                node = EventNode(
                    id=str(uuid4()),
                    novel_id=str(novel_id),
                    name=chapter.get("title", f"第{chapter.get('chapter_number', 0)}章"),
                    chapter_number=chapter.get("chapter_number", 0),
                    event_type="plot",
                    description=chapter.get("summary", ""),
                )
                await self.client.create_node(
                    node.label, node.to_neo4j_properties()
                )
                result["created"] += 1

        return result


# 便捷函数
async def sync_novel_to_graph(novel_id: UUID, db: AsyncSession) -> SyncResult:
    """同步小说到图数据库的便捷函数."""
    from core.graph.neo4j_client import get_neo4j_client

    client = get_neo4j_client()
    if not client or not client.is_connected:
        return SyncResult(
            success=False,
            novel_id=str(novel_id),
            sync_type="full",
            errors=["图数据库未启用或未连接"],
        )

    service = GraphSyncService(client, db)
    return await service.sync_novel_full(novel_id)
