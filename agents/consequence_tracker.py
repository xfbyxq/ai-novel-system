"""
ConsequenceTracker - 事件后果追踪系统.

用于追踪小说中重要事件的预期后果，确保情节连贯性。
核心功能：
1. 注册重要事件并记录预期后果
2. 追踪后果状态（待发生/已发生/部分发生/被忽略）
3. 提醒未闭合的事件后果
4. 验证事件与后果的逻辑关系
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.logging_config import logger


class ConsequenceStatus(str, Enum):
    """后果状态."""

    PENDING = "pending"  # 待发生后果
    HAPPENED = "happened"  # 已发生后果
    PARTIAL = "partial"  # 部分发生
    IGNORED = "ignored"  # 被忽略（合理理由）
    DEFERRED = "deferred"  # 延迟处理（等待合适时机）


class ConsequenceType(str, Enum):
    """后果类型."""

    DIRECT = "direct"  # 直接后果（立即发生）
    INDIRECT = "indirect"  # 间接后果（通过中介发生）
    CHAIN = "chain"  # 连锁后果（引发一系列事件）
    LONG_TERM = "long_term"  # 长期后果（逐渐显现）
    CONDITIONAL = "conditional"  # 条件后果（特定条件下发生）


class ConsequenceImportance(str, Enum):
    """后果重要程度."""

    CRITICAL = "critical"  # 关键后果（必须处理）
    HIGH = "high"  # 高重要后果（建议处理）
    MEDIUM = "medium"  # 中等重要后果（可考虑）
    LOW = "low"  # 低重要后果（可忽略）

    @property
    def level(self) -> int:
        """返回用于排序的数值级别."""
        levels = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return levels[self.value]


@dataclass
class EventConsequence:
    """事件后果实体.

    记录重要事件的预期后果，用于追踪情节连贯性。
    """

    source_event: str  # 源事件描述
    source_chapter: int  # 源事件章节
    expected_consequence: str  # 预期后果描述
    consequence_type: ConsequenceType = ConsequenceType.DIRECT
    importance: ConsequenceImportance = ConsequenceImportance.MEDIUM
    
    # 预期发生范围
    expected_chapter_range: Optional[Tuple[int, int]] = None  # (最小章节, 最大章节)
    
    # 实际发生信息
    actual_chapter: Optional[int] = None
    actual_description: str = ""
    
    # 状态和备注
    status: ConsequenceStatus = ConsequenceStatus.PENDING
    ignore_reason: str = ""  # 如果被忽略，记录原因
    
    # 相关角色
    related_characters: List[str] = field(default_factory=list)
    
    # 元数据
    id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        """初始化默认值."""
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()

    def mark_happened(self, chapter: int, description: str = ""):
        """标记后果已发生."""
        self.status = ConsequenceStatus.HAPPENED
        self.actual_chapter = chapter
        self.actual_description = description
        self.updated_at = datetime.now().isoformat()

    def mark_partial(self, chapter: int, description: str = ""):
        """标记后果部分发生."""
        self.status = ConsequenceStatus.PARTIAL
        self.actual_chapter = chapter
        self.actual_description = description
        self.updated_at = datetime.now().isoformat()

    def mark_ignored(self, reason: str):
        """标记后果被忽略."""
        self.status = ConsequenceStatus.IGNORED
        self.ignore_reason = reason
        self.updated_at = datetime.now().isoformat()

    def mark_deferred(self, reason: str = "", new_range: Optional[Tuple[int, int]] = None):
        """标记后果延迟处理."""
        self.status = ConsequenceStatus.DEFERRED
        self.ignore_reason = reason
        if new_range:
            self.expected_chapter_range = new_range
        self.updated_at = datetime.now().isoformat()

    def is_overdue(self, current_chapter: int) -> bool:
        """检查是否超期."""
        if self.status != ConsequenceStatus.PENDING:
            return False
        if self.expected_chapter_range:
            return current_chapter > self.expected_chapter_range[1]
        return False

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "id": self.id,
            "source_event": self.source_event,
            "source_chapter": self.source_chapter,
            "expected_consequence": self.expected_consequence,
            "consequence_type": self.consequence_type.value,
            "importance": self.importance.value,
            "expected_chapter_range": self.expected_chapter_range,
            "actual_chapter": self.actual_chapter,
            "actual_description": self.actual_description,
            "status": self.status.value,
            "ignore_reason": self.ignore_reason,
            "related_characters": self.related_characters,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventConsequence":
        """从字典创建."""
        # 处理 expected_chapter_range 类型转换（JSON序列化后是列表，需要转为元组）
        expected_chapter_range = data.get("expected_chapter_range")
        if expected_chapter_range is not None and isinstance(expected_chapter_range, list):
            expected_chapter_range = tuple(expected_chapter_range)

        return cls(
            id=data.get("id", ""),
            source_event=data.get("source_event", ""),
            source_chapter=data.get("source_chapter", 0),
            expected_consequence=data.get("expected_consequence", ""),
            consequence_type=ConsequenceType(data.get("consequence_type", "direct")),
            importance=ConsequenceImportance(data.get("importance", "medium")),
            expected_chapter_range=expected_chapter_range,
            actual_chapter=data.get("actual_chapter"),
            actual_description=data.get("actual_description", ""),
            status=ConsequenceStatus(data.get("status", "pending")),
            ignore_reason=data.get("ignore_reason", ""),
            related_characters=data.get("related_characters", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        status_str = {
            ConsequenceStatus.PENDING: "⏳待处理",
            ConsequenceStatus.HAPPENED: "✅已发生",
            ConsequenceStatus.PARTIAL: "🔶部分发生",
            ConsequenceStatus.IGNORED: "⚪已忽略",
            ConsequenceStatus.DEFERRED: "📅延迟处理",
        }.get(self.status, "待处理")

        importance_str = {
            ConsequenceImportance.CRITICAL: "🔴关键",
            ConsequenceImportance.HIGH: "🟠高",
            ConsequenceImportance.MEDIUM: "🟡中",
            ConsequenceImportance.LOW: "🟢低",
        }.get(self.importance, "中")

        range_str = ""
        if self.expected_chapter_range:
            range_str = f"（预期第{self.expected_chapter_range[0]}-{self.expected_chapter_range[1]}章）"

        return (
            f"第{self.source_chapter}章事件「{self.source_event[:30]}」\n"
            f"  → 预期后果：「{self.expected_consequence[:50]}」{range_str}\n"
            f"  → 状态：{status_str}，重要度：{importance_str}"
        )


class ConsequenceReport:
    """后果追踪报告."""

    def __init__(self, current_chapter: int):
        self.current_chapter = current_chapter
        self.pending_consequences: List[EventConsequence] = []
        self.overdue_consequences: List[EventConsequence] = []
        self.recently_happened: List[EventConsequence] = []
        self.recommendations: List[str] = []
        self.warnings: List[str] = []

    def add_pending(self, consequence: EventConsequence):
        """添加待处理后果."""
        self.pending_consequences.append(consequence)

    def add_overdue(self, consequence: EventConsequence):
        """添加超期后果."""
        self.overdue_consequences.append(consequence)

    def add_happened(self, consequence: EventConsequence):
        """添加已发生后果."""
        self.recently_happened.append(consequence)

    def add_recommendation(self, text: str):
        """添加建议."""
        self.recommendations.append(text)

    def add_warning(self, text: str):
        """添加警告."""
        self.warnings.append(text)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "current_chapter": self.current_chapter,
            "pending_count": len(self.pending_consequences),
            "overdue_count": len(self.overdue_consequences),
            "happened_count": len(self.recently_happened),
            "pending": [c.to_dict() for c in self.pending_consequences],
            "overdue": [c.to_dict() for c in self.overdue_consequences],
            "recently_happened": [c.to_dict() for c in self.recently_happened],
            "recommendations": self.recommendations,
            "warnings": self.warnings,
        }

    def format_for_prompt(self) -> str:
        """格式化为提示词."""
        parts = [f"## 事件后果追踪报告（第{self.current_chapter}章）"]

        if self.overdue_consequences:
            parts.append("\n**⚠️ 超期后果（急需处理）**:")
            for c in self.overdue_consequences[:5]:
                parts.append(f"- {c.to_prompt()}")

        if self.pending_consequences:
            parts.append("\n**⏳ 待处理后果**:")
            for c in self.pending_consequences[:5]:
                parts.append(f"- {c.to_prompt()}")

        if self.warnings:
            parts.append("\n**警告**:")
            for w in self.warnings:
                parts.append(f"- ⚠️ {w}")

        if self.recommendations:
            parts.append("\n**建议**:")
            for r in self.recommendations:
                parts.append(f"- 💡 {r}")

        if not self.pending_consequences and not self.overdue_consequences:
            parts.append("\n（当前无待处理的事件后果）")

        return "\n".join(parts)


class ConsequenceTracker:
    """
    事件后果追踪器.

    功能：
    1. 注册重要事件并记录预期后果
    2. 追踪后果状态变化
    3. 检查未闭合事件
    4. 生成提醒提示词
    """

    # 后果提取提示词模板
    CONSEQUENCE_EXTRACT_PROMPT = """请分析以下章节中的关键事件，提取其预期后果。

## 章节内容摘要
{chapter_summary}

## 关键事件列表
{key_events}

## 分析任务
对于每个关键事件，请判断：
1. 该事件是否会产生后续影响？（有些事件是闭合的，不会有后续）
2. 如果会产生后续影响，请描述预期的后果
3. 预估后果发生的章节范围（如"3-5章内"、"长期"）
4. 后果的重要程度（关键/高/中/低）
5. 后果类型（直接/间接/连锁/长期/条件）

## 输出格式
请以JSON格式输出：
{
    "events_with_consequences": [
        {
            "event": "事件描述",
            "consequence": "预期后果描述",
            "expected_range": [起始章, 结束章],
            "importance": "critical/high/medium/low",
            "type": "direct/indirect/chain/long_term/conditional",
            "related_characters": ["相关角色"]
        }
    ],
    "closed_events": ["不会有后续的事件列表"]
}
"""

    # 优先级排序映射
    PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}

    def __init__(self, novel_id: str):
        """初始化方法."""
        self.novel_id = novel_id
        self.consequences: Dict[str, EventConsequence] = {}
        self._event_registry: Dict[int, List[str]] = {}  # 章节号 -> 事件ID列表
        logger.info(f"ConsequenceTracker initialized for novel: {novel_id}")

    def register_event(
        self,
        event: str,
        chapter: int,
        expected_consequences: List[Dict[str, Any]],
    ) -> List[str]:
        """
        注册事件及其预期后果.

        Args:
            event: 事件描述
            chapter: 源事件章节
            expected_consequences: 预期后果列表，每项包含：
                - consequence: 后果描述
                - type: 后果类型（可选）
                - importance: 重要程度（可选）
                - expected_range: 预期章节范围（可选）
                - related_characters: 相关角色（可选）

        Returns:
            注册的后果ID列表
        """
        consequence_ids = []

        for cons_data in expected_consequences:
            consequence = EventConsequence(
                source_event=event,
                source_chapter=chapter,
                expected_consequence=cons_data.get("consequence", ""),
                consequence_type=ConsequenceType(
                    cons_data.get("type", "direct")
                ),
                importance=ConsequenceImportance(
                    cons_data.get("importance", "medium")
                ),
                expected_chapter_range=cons_data.get("expected_range"),
                related_characters=cons_data.get("related_characters", []),
            )

            self.consequences[consequence.id] = consequence
            consequence_ids.append(consequence.id)

            # 注册到章节事件索引
            if chapter not in self._event_registry:
                self._event_registry[chapter] = []
            self._event_registry[chapter].append(consequence.id)

        logger.info(
            f"Event registered at chapter {chapter}: '{event[:30]}...' "
            f"with {len(consequence_ids)} expected consequences"
        )
        return consequence_ids

    def register_single_consequence(
        self,
        source_event: str,
        source_chapter: int,
        expected_consequence: str,
        consequence_type: ConsequenceType = ConsequenceType.DIRECT,
        importance: ConsequenceImportance = ConsequenceImportance.MEDIUM,
        expected_chapter_range: Optional[Tuple[int, int]] = None,
        related_characters: Optional[List[str]] = None,
    ) -> str:
        """
        注册单个事件后果（便捷方法）.

        Returns:
            后果ID
        """
        consequence = EventConsequence(
            source_event=source_event,
            source_chapter=source_chapter,
            expected_consequence=expected_consequence,
            consequence_type=consequence_type,
            importance=importance,
            expected_chapter_range=expected_chapter_range,
            related_characters=related_characters or [],
        )

        self.consequences[consequence.id] = consequence

        if source_chapter not in self._event_registry:
            self._event_registry[source_chapter] = []
        self._event_registry[source_chapter].append(consequence.id)

        logger.info(
            f"Consequence registered: '{source_event[:30]}...' -> '{expected_consequence[:30]}...' "
            f"at chapter {source_chapter}"
        )
        return consequence.id

    def check_pending(self, current_chapter: int) -> List[EventConsequence]:
        """
        检查待处理后果.

        Args:
            current_chapter: 当前章节

        Returns:
            待处理后果列表
        """
        pending = [
            c
            for c in self.consequences.values()
            if c.status == ConsequenceStatus.PENDING
        ]
        # 按重要程度和超期状态排序
        pending.sort(
            key=lambda x: (
                x.is_overdue(current_chapter),
                x.importance.level,  # 使用数值级别排序
                -x.source_chapter,
            ),
            reverse=True,
        )
        return pending

    def check_overdue(self, current_chapter: int) -> List[EventConsequence]:
        """
        检查超期后果.

        Args:
            current_chapter: 当前章节

        Returns:
            趋期后果列表
        """
        overdue = [
            c
            for c in self.consequences.values()
            if c.is_overdue(current_chapter)
        ]
        overdue.sort(key=lambda x: x.importance.level, reverse=True)
        return overdue

    def mark_happened(
        self, consequence_id: str, chapter: int, description: str = ""
    ) -> bool:
        """
        标记后果已发生.

        Args:
            consequence_id: 后果ID
            chapter: 发生章节
            description: 发生描述

        Returns:
            是否成功标记
        """
        if consequence_id not in self.consequences:
            logger.warning(f"Consequence not found: {consequence_id}")
            return False

        self.consequences[consequence_id].mark_happened(chapter, description)
        logger.info(
            f"Consequence {consequence_id} marked as happened at chapter {chapter}"
        )
        return True

    def mark_partial(
        self, consequence_id: str, chapter: int, description: str = ""
    ) -> bool:
        """标记后果部分发生."""
        if consequence_id not in self.consequences:
            return False

        self.consequences[consequence_id].mark_partial(chapter, description)
        logger.info(
            f"Consequence {consequence_id} marked as partial at chapter {chapter}"
        )
        return True

    def mark_ignored(self, consequence_id: str, reason: str) -> bool:
        """标记后果被忽略."""
        if consequence_id not in self.consequences:
            return False

        self.consequences[consequence_id].mark_ignored(reason)
        logger.info(f"Consequence {consequence_id} marked as ignored: {reason}")
        return True

    def mark_deferred(
        self,
        consequence_id: str,
        reason: str = "",
        new_range: Optional[Tuple[int, int]] = None,
    ) -> bool:
        """标记后果延迟处理."""
        if consequence_id not in self.consequences:
            return False

        self.consequences[consequence_id].mark_deferred(reason, new_range)
        logger.info(f"Consequence {consequence_id} marked as deferred")
        return True

    def get_reminder_prompt(self, current_chapter: int) -> str:
        """
        获取后果提醒提示词.

        用于在章节生成前提醒 Writer 处理未闭合事件。

        Args:
            current_chapter: 当前章节

        Returns:
            格式化的提醒字符串
        """
        report = self.generate_report(current_chapter)
        return report.format_for_prompt()

    def generate_report(self, current_chapter: int) -> ConsequenceReport:
        """
        生成后果追踪报告.

        Args:
            current_chapter: 当前章节

        Returns:
            ConsequenceReport
        """
        report = ConsequenceReport(current_chapter)

        # 检查超期后果
        overdue = self.check_overdue(current_chapter)
        for c in overdue:
            report.add_overdue(c)
            if c.importance == ConsequenceImportance.CRITICAL:
                report.add_warning(
                    f"关键后果「{c.expected_consequence[:30]}」已超期 "
                    f"（源事件在第{c.source_chapter}章）"
                )

        # 检查待处理后果
        pending = self.check_pending(current_chapter)
        for c in pending:
            if not c.is_overdue(current_chapter):
                report.add_pending(c)

        # 检查最近发生的后果
        for c in self.consequences.values():
            if c.actual_chapter and abs(c.actual_chapter - current_chapter) <= 2:
                report.add_happened(c)

        # 生成建议
        if overdue:
            report.add_recommendation(
                f"本章建议处理 {len(overdue)} 个超期后果，尤其是关键后果"
            )

        pending_critical = [
            c
            for c in pending
            if c.importance == ConsequenceImportance.CRITICAL
        ]
        if pending_critical:
            report.add_recommendation(
                f"近期需关注 {len(pending_critical)} 个关键后果的发生"
            )

        return report

    def get_consequences_for_chapter(
        self, chapter_number: int
    ) -> Dict[str, List[EventConsequence]]:
        """
        获取与某章节相关的后果.

        Returns:
            {
                "originated": 本章产生的事件后果,
                "expected": 预期本章发生的后果,
                "happened": 本章已发生的后果
            }
        """
        result = {
            "originated": [],
            "expected": [],
            "happened": [],
        }

        for c in self.consequences.values():
            # 本章产生的事件
            if c.source_chapter == chapter_number:
                result["originated"].append(c)

            # 预期本章发生的后果
            if c.expected_chapter_range:
                start, end = c.expected_chapter_range
                if start <= chapter_number <= end and c.status == ConsequenceStatus.PENDING:
                    result["expected"].append(c)

            # 本章已发生的后果
            if c.actual_chapter == chapter_number:
                result["happened"].append(c)

        return result

    def suggest_for_current_chapter(
        self, current_chapter: int, look_ahead: int = 3
    ) -> List[Dict[str, Any]]:
        """
        建议本章应处理的后果.

        Args:
            current_chapter: 当前章节
            look_ahead: 向前看多少章

        Returns:
            建议处理的后果列表
        """
        suggestions = []

        for c in self.consequences.values():
            if c.status != ConsequenceStatus.PENDING:
                continue

            # 超期后果
            if c.is_overdue(current_chapter):
                suggestions.append(
                    {
                        **c.to_dict(),
                        "reason": "后果已超期，建议尽快处理",
                        "priority": "high",
                    }
                )

            # 预期本章发生的后果
            elif c.expected_chapter_range:
                start, end = c.expected_chapter_range
                if current_chapter <= end <= current_chapter + look_ahead:
                    suggestions.append(
                        {
                            **c.to_dict(),
                            "reason": f"预期在第{start}-{end}章发生",
                            "priority": "medium",
                        }
                    )

        suggestions.sort(
            key=lambda x: self.PRIORITY_ORDER.get(x.get("priority", "medium"), 2),
            reverse=True,
        )
        return suggestions

    def validate_consequence_logic(
        self,
        proposed_consequence: Dict[str, Any],
        current_chapter: int,
    ) -> Dict[str, Any]:
        """
        验证后果逻辑合理性.

        检查后果是否与源事件逻辑关联。

        Args:
            proposed_consequence: 提议的后果
            current_chapter: 当前章节

        Returns:
            验证结果
        """
        result = {
            "is_valid": True,
            "warnings": [],
            "suggestions": [],
        }

        source_chapter = proposed_consequence.get("source_chapter", 0)
        consequence_type = proposed_consequence.get("type", "direct")
        expected_range = proposed_consequence.get("expected_range")

        # 检查章节距离
        chapter_distance = current_chapter - source_chapter

        if consequence_type == "direct" and chapter_distance > 5:
            result["warnings"].append(
                f"直接后果距离源事件{chapter_distance}章，可能不够直接"
            )
            result["suggestions"].append(
                "直接后果建议在源事件后1-3章内发生"
            )

        if expected_range:
            start, end = expected_range
            if start < source_chapter:
                result["warnings"].append(
                    f"预期发生章节{start}早于源事件章节{source_chapter}"
                )

        if result["warnings"]:
            result["is_valid"] = False

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息."""
        total = len(self.consequences)
        if total == 0:
            return {
                "total": 0,
                "pending": 0,
                "happened": 0,
                "partial": 0,
                "ignored": 0,
                "deferred": 0,
                "completion_rate": 0,
            }

        pending = len(
            [c for c in self.consequences.values() if c.status == ConsequenceStatus.PENDING]
        )
        happened = len(
            [c for c in self.consequences.values() if c.status == ConsequenceStatus.HAPPENED]
        )
        partial = len(
            [c for c in self.consequences.values() if c.status == ConsequenceStatus.PARTIAL]
        )
        ignored = len(
            [c for c in self.consequences.values() if c.status == ConsequenceStatus.IGNORED]
        )
        deferred = len(
            [c for c in self.consequences.values() if c.status == ConsequenceStatus.DEFERRED]
        )

        return {
            "total": total,
            "pending": pending,
            "happened": happened,
            "partial": partial,
            "ignored": ignored,
            "deferred": deferred,
            "completion_rate": (happened + partial) / total,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "novel_id": self.novel_id,
            "consequences": {
                cid: c.to_dict() for cid, c in self.consequences.items()
            },
            "event_registry": self._event_registry,
            "statistics": self.get_statistics(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsequenceTracker":
        """从字典反序列化."""
        tracker = cls(data.get("novel_id", ""))
        for cid, cdata in data.get("consequences", {}).items():
            tracker.consequences[cid] = EventConsequence.from_dict(cdata)
        tracker._event_registry = data.get("event_registry", {})
        return tracker

    def export_to_json(self) -> str:
        """导出为JSON字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def import_from_json(cls, json_str: str) -> "ConsequenceTracker":
        """从JSON字符串导入."""
        data = json.loads(json_str)
        return cls.from_dict(data)


# ══════════════════════════════════════════════════════════════════════════
# 便捷函数
# ══════════════════════════════════════════════════════════════════════════


def create_consequence_tracker(novel_id: str) -> ConsequenceTracker:
    """便捷函数：创建后果追踪器."""
    return ConsequenceTracker(novel_id)


def register_event_consequence(
    tracker: ConsequenceTracker,
    source_event: str,
    source_chapter: int,
    expected_consequence: str,
    importance: str = "medium",
    expected_range: Optional[Tuple[int, int]] = None,
) -> str:
    """便捷函数：注册单个事件后果."""
    return tracker.register_single_consequence(
        source_event=source_event,
        source_chapter=source_chapter,
        expected_consequence=expected_consequence,
        importance=ConsequenceImportance(importance),
        expected_chapter_range=expected_range,
    )


def get_pending_consequences_prompt(tracker: ConsequenceTracker, current_chapter: int) -> str:
    """便捷函数：获取待处理后果的提醒提示词."""
    return tracker.get_reminder_prompt(current_chapter)


