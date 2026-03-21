"""
ForeshadowingTracker - 伏笔追踪系统

用于追踪小说中的伏笔埋设和回收，确保情节连贯性。
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.logging_config import logger


class ForeshadowingStatus(str, Enum):
    """伏笔状态"""

    PENDING = "pending"  # 待回收
    RESOLVED = "resolved"  # 已回收
    ABANDONED = "abandoned"  # 已放弃（不再回收）
    PARTIAL = "partial"  # 部分回收


class ForeshadowingType(str, Enum):
    """伏笔类型"""

    PLOT = "plot"  # 情节伏笔
    CHARACTER = "character"  # 角色伏笔
    ITEM = "item"  # 物品伏笔
    MYSTERY = "mystery"  # 悬念伏笔
    HINT = "hint"  # 暗示伏笔
    OTHER = "other"  # 其他


class Foreshadowing:
    """伏笔实体"""

    def __init__(
        self,
        content: str,
        planted_chapter: int,
        ftype: ForeshadowingType = ForeshadowingType.PLOT,
        importance: int = 5,  # 1-10, 10最重要
        expected_resolve_chapter: int = None,
        related_characters: List[str] = None,
        notes: str = "",
    ):
        self.id = str(uuid.uuid4())[:8]
        self.content = content
        self.planted_chapter = planted_chapter
        self.ftype = ftype
        self.importance = importance
        self.expected_resolve_chapter = expected_resolve_chapter
        self.related_characters = related_characters or []
        self.notes = notes

        self.status = ForeshadowingStatus.PENDING
        self.resolved_chapter: Optional[int] = None
        self.resolution_content: str = ""

        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def resolve(self, chapter_number: int, resolution_content: str = ""):
        """回收伏笔"""
        self.status = ForeshadowingStatus.RESOLVED
        self.resolved_chapter = chapter_number
        self.resolution_content = resolution_content
        self.updated_at = datetime.now().isoformat()

    def partial_resolve(self, chapter_number: int, resolution_content: str = ""):
        """部分回收伏笔"""
        self.status = ForeshadowingStatus.PARTIAL
        self.resolved_chapter = chapter_number
        self.resolution_content = resolution_content
        self.updated_at = datetime.now().isoformat()

    def abandon(self, reason: str = ""):
        """放弃伏笔"""
        self.status = ForeshadowingStatus.ABANDONED
        self.notes = reason if reason else self.notes
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "planted_chapter": self.planted_chapter,
            "ftype": (
                self.ftype.value if hasattr(self.ftype, "value") else str(self.ftype)
            ),
            "importance": self.importance,
            "expected_resolve_chapter": self.expected_resolve_chapter,
            "related_characters": self.related_characters,
            "notes": self.notes,
            "status": (
                self.status.value if hasattr(self.status, "value") else str(self.status)
            ),
            "resolved_chapter": self.resolved_chapter,
            "resolution_content": self.resolution_content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Foreshadowing":
        """从字典创建伏笔"""
        f = cls(
            content=data.get("content", ""),
            planted_chapter=data.get("planted_chapter", 0),
            ftype=ForeshadowingType(data.get("ftype", "plot")),
            importance=data.get("importance", 5),
            expected_resolve_chapter=data.get("expected_resolve_chapter"),
            related_characters=data.get("related_characters", []),
            notes=data.get("notes", ""),
        )
        f.id = data.get("id", f.id)
        f.status = ForeshadowingStatus(data.get("status", "pending"))
        f.resolved_chapter = data.get("resolved_chapter")
        f.resolution_content = data.get("resolution_content", "")
        f.created_at = data.get("created_at", f.created_at)
        f.updated_at = data.get("updated_at", f.updated_at)
        return f


class ForeshadowingTracker:
    """
    伏笔追踪器

    功能：
    1. 埋设伏笔并记录
    2. 追踪伏笔状态
    3. 提醒待回收的伏笔
    4. 验证伏笔前后一致性
    """

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.foreshadowings: Dict[str, Foreshadowing] = {}
        logger.info(f"ForeshadowingTracker initialized for novel: {novel_id}")

    def plant(
        self,
        content: str,
        chapter_number: int,
        ftype: ForeshadowingType = ForeshadowingType.PLOT,
        importance: int = 5,
        expected_resolve_chapter: int = None,
        related_characters: List[str] = None,
        notes: str = "",
    ) -> str:
        """
        埋下伏笔

        Returns:
            伏笔ID
        """
        foreshadowing = Foreshadowing(
            content=content,
            planted_chapter=chapter_number,
            ftype=ftype,
            importance=importance,
            expected_resolve_chapter=expected_resolve_chapter,
            related_characters=related_characters,
            notes=notes,
        )
        self.foreshadowings[foreshadowing.id] = foreshadowing
        logger.info(
            f"Foreshadowing planted: {foreshadowing.id} at chapter {chapter_number}"
        )
        return foreshadowing.id

    def resolve(
        self, fid: str, chapter_number: int, resolution_content: str = ""
    ) -> bool:
        """
        回收伏笔

        Args:
            fid: 伏笔ID
            chapter_number: 回收章节号
            resolution_content: 回收内容描述

        Returns:
            是否成功回收
        """
        if fid not in self.foreshadowings:
            logger.warning(f"Foreshadowing not found: {fid}")
            return False

        self.foreshadowings[fid].resolve(chapter_number, resolution_content)
        logger.info(f"Foreshadowing resolved: {fid} at chapter {chapter_number}")
        return True

    def partial_resolve(
        self, fid: str, chapter_number: int, resolution_content: str = ""
    ) -> bool:
        """部分回收伏笔"""
        if fid not in self.foreshadowings:
            return False

        self.foreshadowings[fid].partial_resolve(chapter_number, resolution_content)
        logger.info(
            f"Foreshadowing partially resolved: {fid} at chapter {chapter_number}"
        )
        return True

    def abandon(self, fid: str, reason: str = "") -> bool:
        """放弃伏笔"""
        if fid not in self.foreshadowings:
            return False

        self.foreshadowings[fid].abandon(reason)
        logger.info(f"Foreshadowing abandoned: {fid}")
        return True

    def get_foreshadowing(self, fid: str) -> Optional[Foreshadowing]:
        """获取伏笔"""
        return self.foreshadowings.get(fid)

    def get_pending_foreshadowings(self) -> List[Dict[str, Any]]:
        """获取所有待回收的伏笔"""
        pending = [
            f.to_dict()
            for f in self.foreshadowings.values()
            if f.status == ForeshadowingStatus.PENDING
        ]
        # 按重要性和章节排序
        pending.sort(key=lambda x: (-x["importance"], x["planted_chapter"]))
        return pending

    def get_overdue_foreshadowings(self, current_chapter: int) -> List[Dict[str, Any]]:
        """获取超期未回收的伏笔"""
        overdue = []
        for f in self.foreshadowings.values():
            if f.status == ForeshadowingStatus.PENDING:
                if (
                    f.expected_resolve_chapter
                    and current_chapter > f.expected_resolve_chapter
                ):
                    overdue.append(f.to_dict())
        return overdue

    def get_foreshadowings_for_chapter(
        self, chapter_number: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取与某章节相关的伏笔

        Returns:
            {
                "planted": 本章埋下的伏笔,
                "expected_resolve": 预期本章回收的伏笔,
                "resolved": 本章已回收的伏笔
            }
        """
        result = {"planted": [], "expected_resolve": [], "resolved": []}

        for f in self.foreshadowings.values():
            if f.planted_chapter == chapter_number:
                result["planted"].append(f.to_dict())
            if (
                f.expected_resolve_chapter == chapter_number
                and f.status == ForeshadowingStatus.PENDING
            ):
                result["expected_resolve"].append(f.to_dict())
            if f.resolved_chapter == chapter_number:
                result["resolved"].append(f.to_dict())

        return result

    def suggest_resolutions(
        self, current_chapter: int, look_ahead: int = 5
    ) -> List[Dict[str, Any]]:
        """
        建议近期需要回收的伏笔

        Args:
            current_chapter: 当前章节
            look_ahead: 向前看多少章

        Returns:
            建议回收的伏笔列表
        """
        suggestions = []
        for f in self.foreshadowings.values():
            if f.status != ForeshadowingStatus.PENDING:
                continue

            # 高重要性伏笔超过20章未回收
            if f.importance >= 7 and current_chapter - f.planted_chapter > 20:
                suggestions.append(
                    {**f.to_dict(), "reason": "高重要性伏笔已超过20章未回收"}
                )
            # 预期回收时间即将到来
            elif (
                f.expected_resolve_chapter
                and f.expected_resolve_chapter <= current_chapter + look_ahead
            ):
                suggestions.append(
                    {
                        **f.to_dict(),
                        "reason": f"预期在第{f.expected_resolve_chapter}章回收",
                    }
                )
            # 普通伏笔超过50章未回收
            elif current_chapter - f.planted_chapter > 50:
                suggestions.append(
                    {**f.to_dict(), "reason": "伏笔已超过50章未回收，建议处理"}
                )

        suggestions.sort(key=lambda x: -x["importance"])
        return suggestions

    def format_for_prompt(self, current_chapter: int, max_items: int = 10) -> str:
        """
        格式化伏笔信息用于提示词

        Args:
            current_chapter: 当前章节
            max_items: 最大显示数量

        Returns:
            格式化的伏笔信息字符串
        """
        pending = self.get_pending_foreshadowings()[:max_items]
        overdue = self.get_overdue_foreshadowings(current_chapter)
        suggestions = self.suggest_resolutions(current_chapter)[:5]

        parts = []

        if overdue:
            overdue_list = "\n".join(
                [
                    f"  - [第{f['planted_chapter']}章] {f['content']} (预期第{f['expected_resolve_chapter']}章回收)"
                    for f in overdue[:5]
                ]
            )
            parts.append(f"**超期伏笔（急需处理）**:\n{overdue_list}")

        if suggestions:
            suggest_list = "\n".join(
                [
                    f"  - [第{f['planted_chapter']}章] {f['content']} ({f['reason']})"
                    for f in suggestions[:5]
                ]
            )
            parts.append(f"**建议回收的伏笔**:\n{suggest_list}")

        if pending and not suggestions:
            pending_list = "\n".join(
                [
                    f"  - [第{f['planted_chapter']}章] {f['content']} (重要性: {f['importance']})"
                    for f in pending[:5]
                ]
            )
            parts.append(f"**待回收的伏笔**:\n{pending_list}")

        if not parts:
            return "（当前无需特别关注的伏笔）"

        return "\n\n".join(parts)

    def get_statistics(self) -> Dict[str, Any]:
        """获取伏笔统计信息"""
        total = len(self.foreshadowings)
        pending = len(
            [
                f
                for f in self.foreshadowings.values()
                if f.status == ForeshadowingStatus.PENDING
            ]
        )
        resolved = len(
            [
                f
                for f in self.foreshadowings.values()
                if f.status == ForeshadowingStatus.RESOLVED
            ]
        )
        partial = len(
            [
                f
                for f in self.foreshadowings.values()
                if f.status == ForeshadowingStatus.PARTIAL
            ]
        )
        abandoned = len(
            [
                f
                for f in self.foreshadowings.values()
                if f.status == ForeshadowingStatus.ABANDONED
            ]
        )

        return {
            "total": total,
            "pending": pending,
            "resolved": resolved,
            "partial": partial,
            "abandoned": abandoned,
            "resolution_rate": resolved / total if total > 0 else 0,
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "novel_id": self.novel_id,
            "foreshadowings": {
                fid: f.to_dict() for fid, f in self.foreshadowings.items()
            },
            "statistics": self.get_statistics(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForeshadowingTracker":
        """从字典反序列化"""
        tracker = cls(data.get("novel_id", ""))
        for fid, fdata in data.get("foreshadowings", {}).items():
            tracker.foreshadowings[fid] = Foreshadowing.from_dict(fdata)
        return tracker

    def export_to_json(self) -> str:
        """导出为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def import_from_json(cls, json_str: str) -> "ForeshadowingTracker":
        """从JSON字符串导入"""
        data = json.loads(json_str)
        return cls.from_dict(data)
