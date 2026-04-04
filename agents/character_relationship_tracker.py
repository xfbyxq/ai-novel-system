"""
CharacterRelationshipTracker - 角色关系追踪器.

追踪角色间关系的动态变化，检测不合理的关系突变。

核心功能：
1. 注册和维护角色关系（双向关系，A-B 和 B-A 是同一关系）
2. 记录关系互动事件，更新信任度/亲密度/冲突度
3. 从章节文本中自动提取关系互动
4. 检测关系一致性问题（突变、缺失触发条件等）
5. 生成关系上下文提示词

解决根本原因：角色关系变化缺乏追踪和验证
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from core.logging_config import logger


class RelationshipType(Enum):
    """角色关系类型."""

    ALLY = "ally"  # 盟友
    ENEMY = "enemy"  # 敌人
    ROMANTIC = "romantic"  # 恋人
    FAMILY = "family"  # 家人
    MENTOR = "mentor"  # 师徒
    NEUTRAL = "neutral"  # 中立
    RIVAL = "rival"  # 竞争对手
    SUBORDINATE = "subordinate"  # 上下级
    STRANGER = "stranger"  # 陌生人


@dataclass
class RelationshipEvent:
    """关系互动事件.

    记录一次影响角色关系的互动事件。

    Attributes:
        event_id: 事件唯一标识
        chapter_number: 发生章节
        event_description: 事件描述
        impact_on_trust: 对信任度的影响 -1 到 +1
        impact_on_intimacy: 对亲密度的影响
        impact_on_conflict: 对冲突度的影响
        triggered_type_change: 是否触发关系类型变更
        new_type: 如果变更了，新的关系类型
        timestamp: 事件时间戳
    """

    event_id: str = field(default_factory=lambda: uuid4().hex[:8])
    chapter_number: int = 0
    event_description: str = ""
    impact_on_trust: float = 0.0
    impact_on_intimacy: float = 0.0
    impact_on_conflict: float = 0.0
    triggered_type_change: bool = False
    new_type: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "event_id": self.event_id,
            "chapter_number": self.chapter_number,
            "event_description": self.event_description,
            "impact_on_trust": self.impact_on_trust,
            "impact_on_intimacy": self.impact_on_intimacy,
            "impact_on_conflict": self.impact_on_conflict,
            "triggered_type_change": self.triggered_type_change,
            "new_type": self.new_type,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipEvent":
        """从字典创建."""
        return cls(
            event_id=data.get("event_id", uuid4().hex[:8]),
            chapter_number=data.get("chapter_number", 0),
            event_description=data.get("event_description", ""),
            impact_on_trust=data.get("impact_on_trust", 0.0),
            impact_on_intimacy=data.get("impact_on_intimacy", 0.0),
            impact_on_conflict=data.get("impact_on_conflict", 0.0),
            triggered_type_change=data.get("triggered_type_change", False),
            new_type=data.get("new_type"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class CharacterRelationship:
    """角色关系.

    表示两个角色之间的关系状态，包含信任度、亲密度、冲突度等维度。

    Attributes:
        relationship_id: 关系唯一标识
        character_a: 角色A名
        character_b: 角色B名
        relationship_type: 关系类型
        trust_level: 信任度 0-1
        intimacy_level: 亲密度 0-1
        conflict_level: 冲突度 0-1
        established_chapter: 建立章节
        last_interaction_chapter: 最后互动章节
        interaction_history: 互动历史记录
        notes: 备注
        created_at: 创建时间
    """

    relationship_id: str = field(default_factory=lambda: uuid4().hex[:8])
    character_a: str = ""
    character_b: str = ""
    relationship_type: RelationshipType = RelationshipType.NEUTRAL
    trust_level: float = 0.5
    intimacy_level: float = 0.0
    conflict_level: float = 0.0
    established_chapter: int = 1
    last_interaction_chapter: int = 0
    interaction_history: List[RelationshipEvent] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def apply_event(self, event: RelationshipEvent) -> None:
        """应用一个互动事件，更新关系数值.

        Args:
            event: 关系互动事件
        """
        # 更新信任度，并 clamp 到 [0, 1]
        self.trust_level = max(0.0, min(1.0, self.trust_level + event.impact_on_trust))

        # 更新亲密度
        self.intimacy_level = max(0.0, min(1.0, self.intimacy_level + event.impact_on_intimacy))

        # 更新冲突度
        self.conflict_level = max(0.0, min(1.0, self.conflict_level + event.impact_on_conflict))

        # 如果触发类型变更，更新关系类型
        if event.triggered_type_change and event.new_type:
            try:
                self.relationship_type = RelationshipType(event.new_type)
            except ValueError:
                logger.warning(f"未知的关系类型: {event.new_type}")

        # 更新最后互动章节
        if event.chapter_number > self.last_interaction_chapter:
            self.last_interaction_chapter = event.chapter_number

        # 添加到历史记录
        self.interaction_history.append(event)

    @property
    def relationship_strength(self) -> float:
        """关系强度（综合信任和亲密度）.

        Returns:
            0-1 之间的关系强度值
        """
        return (self.trust_level + self.intimacy_level) / 2

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "relationship_id": self.relationship_id,
            "character_a": self.character_a,
            "character_b": self.character_b,
            "relationship_type": self.relationship_type.value,
            "trust_level": self.trust_level,
            "intimacy_level": self.intimacy_level,
            "conflict_level": self.conflict_level,
            "established_chapter": self.established_chapter,
            "last_interaction_chapter": self.last_interaction_chapter,
            "interaction_history": [e.to_dict() for e in self.interaction_history],
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterRelationship":
        """从字典创建."""
        rel = cls(
            relationship_id=data.get("relationship_id", uuid4().hex[:8]),
            character_a=data.get("character_a", ""),
            character_b=data.get("character_b", ""),
            relationship_type=RelationshipType(data.get("relationship_type", "neutral")),
            trust_level=data.get("trust_level", 0.5),
            intimacy_level=data.get("intimacy_level", 0.0),
            conflict_level=data.get("conflict_level", 0.0),
            established_chapter=data.get("established_chapter", 1),
            last_interaction_chapter=data.get("last_interaction_chapter", 0),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )

        # 加载互动历史
        history = data.get("interaction_history", [])
        rel.interaction_history = [RelationshipEvent.from_dict(e) for e in history]

        return rel


@dataclass
class RelationshipIssue:
    """关系一致性问题.

    表示检测到的不合理关系变化或矛盾。

    Attributes:
        character_a: 角色A名
        character_b: 角色B名
        issue_type: 问题类型 (sudden_change|missing_trigger|contradiction|disappeared)
        description: 问题描述
        chapter_range: 涉及的章节范围
        severity: 严重程度 (low|medium|high)
        suggested_fix: 建议修复方案
    """

    character_a: str = ""
    character_b: str = ""
    issue_type: str = ""  # sudden_change|missing_trigger|contradiction|disappeared
    description: str = ""
    chapter_range: Tuple[int, int] = (0, 0)
    severity: str = "medium"
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "character_a": self.character_a,
            "character_b": self.character_b,
            "issue_type": self.issue_type,
            "description": self.description,
            "chapter_range": list(self.chapter_range),
            "severity": self.severity,
            "suggested_fix": self.suggested_fix,
        }


class CharacterRelationshipTracker:
    """角色关系追踪器.

    追踪角色间关系的动态变化，检测不合理的关系突变。

    Attributes:
        relationships: 关系字典，rel_id -> relationship
        _pair_index: 角色对索引，(char_a, char_b) -> rel_id
        qwen_client: LLM 客户端（可选）
    """

    def __init__(self, qwen_client: Optional[Any] = None) -> None:
        """初始化追踪器.

        Args:
            qwen_client: 可选的 LLM 客户端，用于自动提取关系事件
        """
        self.relationships: Dict[str, CharacterRelationship] = {}
        self._pair_index: Dict[Tuple[str, str], str] = {}
        self.qwen_client = qwen_client

    def _normalize_pair(self, char_a: str, char_b: str) -> Tuple[str, str]:
        """标准化角色对.

        按字典序排列，确保 A-B 和 B-A 指向同一关系。

        Args:
            char_a: 角色A名
            char_b: 角色B名

        Returns:
            标准化后的角色对元组
        """
        return tuple(sorted([char_a, char_b]))

    def register_relationship(
        self,
        char_a: str,
        char_b: str,
        rel_type: RelationshipType,
        chapter: int,
        trust: float = 0.5,
        intimacy: float = 0.0,
        conflict: float = 0.0,
        notes: str = "",
    ) -> str:
        """注册角色关系.

        如已存在则更新类型。返回 relationship_id。

        Args:
            char_a: 角色A名
            char_b: 角色B名
            rel_type: 关系类型
            chapter: 建立章节
            trust: 初始信任度
            intimacy: 初始亲密度
            conflict: 初始冲突度
            notes: 备注

        Returns:
            关系ID
        """
        pair = self._normalize_pair(char_a, char_b)

        # 检查是否已存在
        if pair in self._pair_index:
            rel_id = self._pair_index[pair]
            rel = self.relationships[rel_id]
            rel.relationship_type = rel_type
            rel.trust_level = trust
            rel.intimacy_level = intimacy
            rel.conflict_level = conflict
            if notes:
                rel.notes = notes
            logger.info(f"更新角色关系: {char_a} ↔ {char_b} -> {rel_type.value}")
            return rel_id

        # 创建新关系
        rel = CharacterRelationship(
            character_a=pair[0],
            character_b=pair[1],
            relationship_type=rel_type,
            trust_level=trust,
            intimacy_level=intimacy,
            conflict_level=conflict,
            established_chapter=chapter,
            notes=notes,
        )

        self.relationships[rel.relationship_id] = rel
        self._pair_index[pair] = rel.relationship_id

        logger.info(f"注册角色关系: {char_a} ↔ {char_b} -> {rel_type.value}")
        return rel.relationship_id

    def record_interaction(
        self,
        char_a: str,
        char_b: str,
        event_description: str,
        chapter: int,
        impact_trust: float = 0.0,
        impact_intimacy: float = 0.0,
        impact_conflict: float = 0.0,
        type_change: Optional[RelationshipType] = None,
    ) -> None:
        """记录一次互动事件.

        如关系不存在则自动注册为 NEUTRAL。

        Args:
            char_a: 角色A名
            char_b: 角色B名
            event_description: 事件描述
            chapter: 章节号
            impact_trust: 对信任度的影响
            impact_intimacy: 对亲密度的影响
            impact_conflict: 对冲突度的影响
            type_change: 关系类型变更（可选）
        """
        pair = self._normalize_pair(char_a, char_b)

        # 如关系不存在，自动注册为 NEUTRAL
        if pair not in self._pair_index:
            self.register_relationship(char_a, char_b, RelationshipType.NEUTRAL, chapter)

        rel_id = self._pair_index[pair]
        rel = self.relationships[rel_id]

        # 创建事件
        event = RelationshipEvent(
            chapter_number=chapter,
            event_description=event_description,
            impact_on_trust=impact_trust,
            impact_on_intimacy=impact_intimacy,
            impact_on_conflict=impact_conflict,
            triggered_type_change=type_change is not None,
            new_type=type_change.value if type_change else None,
        )

        # 应用事件
        rel.apply_event(event)

        logger.debug(f"记录互动: {char_a} ↔ {char_b} 第{chapter}章 - {event_description[:50]}...")

    def get_relationship(self, char_a: str, char_b: str) -> Optional[CharacterRelationship]:
        """获取两个角色之间的关系.

        Args:
            char_a: 角色A名
            char_b: 角色B名

        Returns:
            角色关系对象，如不存在返回 None
        """
        pair = self._normalize_pair(char_a, char_b)
        rel_id = self._pair_index.get(pair)
        if rel_id:
            return self.relationships.get(rel_id)
        return None

    def get_character_relationships(self, character: str) -> List[CharacterRelationship]:
        """获取某角色的所有关系.

        Args:
            character: 角色名

        Returns:
            该角色的所有关系列表
        """
        result = []
        for rel in self.relationships.values():
            if rel.character_a == character or rel.character_b == character:
                result.append(rel)
        return result

    def validate_relationship_change(
        self,
        char_a: str,
        char_b: str,
        proposed_new_type: RelationshipType,
        chapter: int,
    ) -> Optional[RelationshipIssue]:
        """检查关系变化是否有充分的故事支撑.

        规则检查：
        1. STRANGER -> ROMANTIC 需要至少2次正面互动
        2. ALLY -> ENEMY 需要至少1次高冲突事件
        3. 关系类型跨度过大（如 ENEMY -> ROMANTIC）需要中间过渡
        4. 如果缺乏互动记录就变更关系类型，标记为 missing_trigger

        Args:
            char_a: 角色A名
            char_b: 角色B名
            proposed_new_type: 提议的新关系类型
            chapter: 当前章节

        Returns:
            如发现问题返回 RelationshipIssue，否则返回 None
        """
        pair = self._normalize_pair(char_a, char_b)
        rel_id = self._pair_index.get(pair)

        if not rel_id:
            # 关系不存在，新建立关系
            return None

        rel = self.relationships[rel_id]
        current_type = rel.relationship_type

        if current_type == proposed_new_type:
            return None

        history = rel.interaction_history

        # 规则1: STRANGER -> ROMANTIC 需要至少2次正面互动
        if (
            current_type == RelationshipType.STRANGER
            and proposed_new_type == RelationshipType.ROMANTIC
        ):
            positive_events = [
                e for e in history if e.impact_on_trust > 0.2 or e.impact_on_intimacy > 0.2
            ]
            if len(positive_events) < 2:
                return RelationshipIssue(
                    character_a=char_a,
                    character_b=char_b,
                    issue_type="missing_trigger",
                    description=(
                        f"陌生人直接变为恋人缺乏足够铺垫，"
                        f"仅有 {len(positive_events)} 次正面互动"
                    ),
                    chapter_range=(rel.established_chapter, chapter),
                    severity="high",
                    suggested_fix="增加至少2次正面互动事件，逐步建立情感联系",
                )

        # 规则2: ALLY -> ENEMY 需要至少1次高冲突事件
        if current_type == RelationshipType.ALLY and proposed_new_type == RelationshipType.ENEMY:
            high_conflict_events = [
                e for e in history if e.impact_on_conflict > 0.5 or e.impact_on_trust < -0.3
            ]
            if not high_conflict_events:
                return RelationshipIssue(
                    character_a=char_a,
                    character_b=char_b,
                    issue_type="missing_trigger",
                    description="盟友变为敌人缺乏高冲突事件触发",
                    chapter_range=(rel.established_chapter, chapter),
                    severity="high",
                    suggested_fix="添加背叛、利益冲突或理念分歧等高冲突事件",
                )

        # 规则3: 关系类型跨度过大需要中间过渡
        extreme_transitions = {
            (RelationshipType.ENEMY, RelationshipType.ROMANTIC),
            (RelationshipType.ROMANTIC, RelationshipType.ENEMY),
            (RelationshipType.ENEMY, RelationshipType.FAMILY),
            (RelationshipType.STRANGER, RelationshipType.FAMILY),
        }
        if (current_type, proposed_new_type) in extreme_transitions:
            # 检查是否有中间过渡类型的记录
            intermediate_types = {e.new_type for e in history if e.new_type}
            if not intermediate_types:
                return RelationshipIssue(
                    character_a=char_a,
                    character_b=char_b,
                    issue_type="sudden_change",
                    description=(
                        f"关系突变：从 {current_type.value} "
                        f"直接变为 {proposed_new_type.value}，缺乏过渡"
                    ),
                    chapter_range=(rel.established_chapter, chapter),
                    severity="medium",
                    suggested_fix=(
                        f"考虑添加中间过渡，如 {current_type.value} "
                        f"-> neutral -> {proposed_new_type.value}"
                    ),
                )

        # 规则4: 缺乏互动记录就变更关系类型
        recent_chapters = chapter - rel.last_interaction_chapter
        if recent_chapters > 5 and len(history) < 3:
            return RelationshipIssue(
                character_a=char_a,
                character_b=char_b,
                issue_type="missing_trigger",
                description=(
                    f"关系变化缺乏足够互动支撑"
                    f"（仅 {len(history)} 次互动，间隔 {recent_chapters} 章）"
                ),
                chapter_range=(rel.established_chapter, chapter),
                severity="medium",
                suggested_fix="增加更多互动事件来支撑关系变化",
            )

        return None

    async def extract_relationships_from_text(
        self,
        chapter_content: str,
        chapter_number: int,
        known_characters: Optional[List[str]] = None,
    ) -> List[RelationshipEvent]:
        """使用 LLM 从章节文本中自动提取关系互动事件.

        提取后自动更新内部状态。返回提取到的事件列表。

        Args:
            chapter_content: 章节文本内容
            chapter_number: 章节号
            known_characters: 已知角色列表（可选）

        Returns:
            提取到的事件列表
        """
        if self.qwen_client is None:
            logger.warning("未提供 qwen_client，无法自动提取关系事件")
            return []

        try:
            from agents.base.json_extractor import JsonExtractor

            # 构建提示词
            characters_hint = ""
            if known_characters:
                characters_hint = f"已知角色: {', '.join(known_characters)}\n\n"

            prompt = (
                "请分析以下小说章节，提取角色之间的关系互动事件。\n\n"
                f"{characters_hint}章节内容：\n"
                f"{chapter_content[:3000]}\n\n"
                "请提取所有角色间的互动事件，以 JSON 数组格式返回：\n"
                "[\n"
                "  {\n"
                '    "character_a": "角色A名",\n'
                '    "character_b": "角色B名",\n'
                '    "event_description": "事件描述",\n'
                '    "impact_on_trust": 0.1,\n'
                '    "impact_on_intimacy": 0.0,\n'
                '    "impact_on_conflict": 0.0,\n'
                '    "type_change": null\n'
                "  }\n"
                "]\n\n"
                "注意：\n"
                "1. 只提取有实质影响的互动（信任/亲密/冲突有明显变化）\n"
                "2. 如互动未改变关系类型，type_change 设为 null\n"
                "3. 数值范围 -1.0 到 +1.0，0 表示无影响\n"
                "4. type_change 可选值：ally/enemy/romantic/family/mentor/\n"
                "   neutral/rival/subordinate/stranger\n"
                "5. 如无任何互动，返回空数组 []"
            )

            # 调用 LLM
            response = await self.qwen_client.chat(
                prompt=prompt,
                system="你是一个专业的文学分析助手，擅长提取角色关系动态。",
                temperature=0.3,
            )

            content = response.get("content", "")

            # 提取 JSON
            events_data = JsonExtractor.extract_array(content, default=[])

            extracted_events = []
            for event_data in events_data:
                char_a = event_data.get("character_a", "")
                char_b = event_data.get("character_b", "")

                if not char_a or not char_b:
                    continue

                # 解析类型变更
                type_change = None
                type_change_str = event_data.get("type_change")
                if type_change_str:
                    try:
                        type_change = RelationshipType(type_change_str)
                    except ValueError:
                        pass

                # 记录互动
                self.record_interaction(
                    char_a=char_a,
                    char_b=char_b,
                    event_description=event_data.get("event_description", ""),
                    chapter=chapter_number,
                    impact_trust=event_data.get("impact_on_trust", 0.0),
                    impact_intimacy=event_data.get("impact_on_intimacy", 0.0),
                    impact_conflict=event_data.get("impact_on_conflict", 0.0),
                    type_change=type_change,
                )

                # 创建事件对象返回
                event = RelationshipEvent(
                    chapter_number=chapter_number,
                    event_description=event_data.get("event_description", ""),
                    impact_on_trust=event_data.get("impact_on_trust", 0.0),
                    impact_on_intimacy=event_data.get("impact_on_intimacy", 0.0),
                    impact_on_conflict=event_data.get("impact_on_conflict", 0.0),
                    triggered_type_change=type_change is not None,
                    new_type=type_change_str,
                )
                extracted_events.append(event)

            logger.info(f"从第{chapter_number}章提取了 {len(extracted_events)} 个关系事件")
            return extracted_events

        except Exception as e:
            logger.warning(f"提取关系事件失败: {e}")
            return []

    def build_relationship_context(
        self,
        characters: Optional[List[str]] = None,
    ) -> str:
        """生成关系上下文提示词.

        格式：
        【角色关系网络】
        - 张三 ↔ 李四：盟友（信任度:0.8, 亲密度:0.6）— 共同战斗的伙伴
        - 张三 ↔ 王五：敌人（冲突度:0.9）— 因家族仇恨对立
        - 李四 ↔ 王五：中立（信任度:0.3）— 暂无直接冲突

        Args:
            characters: 指定角色列表，如为 None 则包含所有关系

        Returns:
            格式化的关系上下文字符串
        """
        lines = ["【角色关系网络】"]

        for rel in self.relationships.values():
            # 如指定了角色列表，过滤不相关的关系
            if characters:
                if rel.character_a not in characters and rel.character_b not in characters:
                    continue

            # 格式化关系描述
            rel_type_name = {
                RelationshipType.ALLY: "盟友",
                RelationshipType.ENEMY: "敌人",
                RelationshipType.ROMANTIC: "恋人",
                RelationshipType.FAMILY: "家人",
                RelationshipType.MENTOR: "师徒",
                RelationshipType.NEUTRAL: "中立",
                RelationshipType.RIVAL: "竞争对手",
                RelationshipType.SUBORDINATE: "上下级",
                RelationshipType.STRANGER: "陌生人",
            }.get(rel.relationship_type, rel.relationship_type.value)

            # 构建数值描述
            metrics = []
            if rel.trust_level != 0.5:
                metrics.append(f"信任度:{rel.trust_level:.1f}")
            if rel.intimacy_level > 0:
                metrics.append(f"亲密度:{rel.intimacy_level:.1f}")
            if rel.conflict_level > 0:
                metrics.append(f"冲突度:{rel.conflict_level:.1f}")

            metrics_str = f"({', '.join(metrics)})" if metrics else ""

            # 备注截断
            notes = rel.notes[:30] + "..." if len(rel.notes) > 30 else rel.notes
            notes_str = f" — {notes}" if notes else ""

            line = (
                f"- {rel.character_a} ↔ {rel.character_b}："
                f"{rel_type_name}{metrics_str}{notes_str}"
            )
            lines.append(line)

        if len(lines) == 1:
            lines.append("（暂无角色关系记录）")

        return "\n".join(lines)

    def detect_relationship_issues(
        self,
        chapter_number: int,
    ) -> List[RelationshipIssue]:
        """检测所有关系的一致性问题.

        检查：
        1. 长期无互动但突然变化的关系
        2. 信任/亲密/冲突值与关系类型不匹配
        3. 关系类型突变缺乏过渡

        Args:
            chapter_number: 当前章节号

        Returns:
            检测到的问题列表
        """
        issues = []

        for rel in self.relationships.values():
            # 检查1: 长期无互动但数值异常
            chapters_since_last = chapter_number - rel.last_interaction_chapter
            if chapters_since_last > 10:
                # 检查是否有不合理的数值
                if rel.intimacy_level > 0.7 or rel.conflict_level > 0.7:
                    issues.append(
                        RelationshipIssue(
                            character_a=rel.character_a,
                            character_b=rel.character_b,
                            issue_type="disappeared",
                            description=(
                                f"关系长期无互动（{chapters_since_last} 章）" f"但保持高强度情感"
                            ),
                            chapter_range=(rel.last_interaction_chapter, chapter_number),
                            severity="low",
                            suggested_fix="考虑添加互动来维持或调整关系强度",
                        )
                    )

            # 检查2: 数值与关系类型不匹配
            if rel.relationship_type == RelationshipType.ENEMY and rel.trust_level > 0.5:
                issues.append(
                    RelationshipIssue(
                        character_a=rel.character_a,
                        character_b=rel.character_b,
                        issue_type="contradiction",
                        description=f"敌人关系但信任度高达 {rel.trust_level:.1f}",
                        chapter_range=(rel.established_chapter, chapter_number),
                        severity="medium",
                        suggested_fix="降低信任度或重新评估关系类型",
                    )
                )

            if rel.relationship_type == RelationshipType.ROMANTIC and rel.intimacy_level < 0.3:
                issues.append(
                    RelationshipIssue(
                        character_a=rel.character_a,
                        character_b=rel.character_b,
                        issue_type="contradiction",
                        description=f"恋人关系但亲密度仅 {rel.intimacy_level:.1f}",
                        chapter_range=(rel.established_chapter, chapter_number),
                        severity="medium",
                        suggested_fix="增加亲密互动或重新评估关系类型",
                    )
                )

            if rel.relationship_type == RelationshipType.ALLY and rel.conflict_level > 0.6:
                issues.append(
                    RelationshipIssue(
                        character_a=rel.character_a,
                        character_b=rel.character_b,
                        issue_type="contradiction",
                        description=f"盟友关系但冲突度高达 {rel.conflict_level:.1f}",
                        chapter_range=(rel.established_chapter, chapter_number),
                        severity="medium",
                        suggested_fix="解决冲突或考虑将关系变更为 rival/enemy",
                    )
                )

            # 检查3: 关系类型突变（通过历史记录检查）
            if len(rel.interaction_history) >= 2:
                recent_events = rel.interaction_history[-3:]  # 最近3个事件
                type_changes = [e for e in recent_events if e.triggered_type_change]
                if len(type_changes) >= 2:
                    issues.append(
                        RelationshipIssue(
                            character_a=rel.character_a,
                            character_b=rel.character_b,
                            issue_type="sudden_change",
                            description="短期内多次变更关系类型，变化过于频繁",
                            chapter_range=(rel.established_chapter, chapter_number),
                            severity="high",
                            suggested_fix="稳定关系类型，避免频繁变更",
                        )
                    )

        return issues

    def get_relationship_summary(self) -> Dict[str, Any]:
        """获取关系网络概要统计.

        Returns:
            包含统计信息的字典
        """
        total = len(self.relationships)
        type_counts: Dict[str, int] = {}
        avg_trust = 0.0
        avg_intimacy = 0.0
        avg_conflict = 0.0
        total_events = 0

        for rel in self.relationships.values():
            type_name = rel.relationship_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

            avg_trust += rel.trust_level
            avg_intimacy += rel.intimacy_level
            avg_conflict += rel.conflict_level
            total_events += len(rel.interaction_history)

        if total > 0:
            avg_trust /= total
            avg_intimacy /= total
            avg_conflict /= total

        return {
            "total_relationships": total,
            "type_distribution": type_counts,
            "average_trust": round(avg_trust, 2),
            "average_intimacy": round(avg_intimacy, 2),
            "average_conflict": round(avg_conflict, 2),
            "total_interaction_events": total_events,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化追踪器状态."""
        return {
            "relationships": {rid: rel.to_dict() for rid, rel in self.relationships.items()},
            "pair_index": {f"{k[0]}|{k[1]}": v for k, v in self._pair_index.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterRelationshipTracker":
        """从字典恢复追踪器状态."""
        tracker = cls()

        # 恢复关系
        relationships_data = data.get("relationships", {})
        for rel_id, rel_data in relationships_data.items():
            rel = CharacterRelationship.from_dict(rel_data)
            tracker.relationships[rel_id] = rel

        # 恢复索引
        pair_index_data = data.get("pair_index", {})
        for pair_key, rel_id in pair_index_data.items():
            chars = pair_key.split("|")
            if len(chars) == 2:
                tracker._pair_index[(chars[0], chars[1])] = rel_id

        return tracker
