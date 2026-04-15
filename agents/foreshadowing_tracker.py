"""伏笔追踪器 - 管理伏笔的生命周期.

追踪伏笔从计划、埋下、回收到解决的全过程，
确保伏笔不被遗忘，并在 Writer prompt 中强制提醒。
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from core.logging_config import logger


class ForeshadowingStatus(str, Enum):
    """伏笔状态枚举."""

    PLANNED = "planned"  # 在章节计划中提出
    PLANTED = "planted"  # 已在章节内容中埋下
    RECALLED = "recalled"  # 已被提及/呼应
    RESOLVED = "resolved"  # 已回收/解决
    ABANDONED = "abandoned"  # 超过阈值未回收，标记放弃


@dataclass
class ForeshadowingItem:
    """伏笔条目."""

    id: str
    content: str  # 伏笔内容描述
    type: str = "plot"  # 伏笔类型：plot/character/world
    status: ForeshadowingStatus = ForeshadowingStatus.PLANNED
    planted_chapter: Optional[int] = None  # 埋下伏笔的章节
    recalled_chapters: List[int] = field(default_factory=list)  # 被呼应的章节
    resolved_chapter: Optional[int] = None  # 回收的章节
    related_characters: List[str] = field(default_factory=list)
    importance: int = 3  # 重要性 1-5
    created_at: datetime = field(default_factory=datetime.now)
    last_checked_chapter: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式."""
        return {
            "id": self.id,
            "content": self.content,
            "type": self.type,
            "status": self.status.value,
            "planted_chapter": self.planted_chapter,
            "recalled_chapters": self.recalled_chapters,
            "resolved_chapter": self.resolved_chapter,
            "related_characters": self.related_characters,
            "importance": self.importance,
            "age_days": (datetime.now() - self.created_at).days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ForeshadowingItem":
        """从字典加载伏笔."""
        item = cls(
            id=data["id"],
            content=data["content"],
            type=data.get("type", "plot"),
            status=ForeshadowingStatus(data.get("status", "planned")),
            planted_chapter=data.get("planted_chapter"),
            recalled_chapters=data.get("recalled_chapters", []),
            resolved_chapter=data.get("resolved_chapter"),
            related_characters=data.get("related_characters", []),
            importance=data.get("importance", 3),
        )
        return item


class ForeshadowingTracker:
    """伏笔生命周期追踪器.

    核心功能：
    1. 从章节计划中注册伏笔
    2. 检测章节内容中是否埋下伏笔
    3. 检查后续章节是否回收伏笔
    4. 老化评估：超期未回收则警告或标记放弃
    5. 格式化为 Writer prompt 中的提醒
    """

    MAX_UNRECALLED_CHAPTERS = 5  # 超过 5 章未回收则标记警告
    MAX_TOTAL_CHAPTERS = 10  # 超过 10 章未回收则标记放弃

    def __init__(self):
        """初始化方法."""
        self.foreshadowings: Dict[str, ForeshadowingItem] = {}

    def register_from_plan(
        self,
        chapter_number: int,
        foreshadowing_list: List[str],
        related_characters: Optional[List[str]] = None,
    ) -> List[str]:
        """从章节计划中注册伏笔.

        Args:
            chapter_number: 当前章节号
            foreshadowing_list: 伏笔列表（从 chapter_plan.foreshadowing 获取）
            related_characters: 相关角色列表

        Returns:
            已注册的伏笔 ID 列表
        """
        registered_ids = []
        for f in foreshadowing_list:
            if not f or not f.strip():
                continue

            # 检查是否已存在相同内容的伏笔
            existing = self._find_by_content(f)
            if existing:
                logger.debug(f"伏笔已存在，跳过: {f[:30]}")
                continue

            item_id = str(uuid.uuid4())[:8]
            item = ForeshadowingItem(
                id=item_id,
                content=f.strip(),
                type="plot",
                status=ForeshadowingStatus.PLANNED,
                related_characters=related_characters or [],
            )
            self.foreshadowings[item_id] = item
            registered_ids.append(item_id)
            logger.info(f"[Foreshadowing] 注册伏笔 (ch{chapter_number}): {f[:50]}")

        return registered_ids

    def mark_planted(
        self,
        chapter_number: int,
        content_snippets: List[str],
    ) -> None:
        """标记伏笔已在章节内容中埋下.

        Args:
            chapter_number: 当前章节号
            content_snippets: 内容片段列表
        """
        for snippet in content_snippets:
            matching = self._find_by_content(snippet)
            if matching:
                matching.status = ForeshadowingStatus.PLANTED
                matching.planted_chapter = chapter_number
                matching.last_checked_chapter = chapter_number

    def check_recalls(
        self,
        chapter_number: int,
        chapter_content: str,
    ) -> List[str]:
        """检查当前章节是否回收了旧伏笔.

        Args:
            chapter_number: 当前章节号
            chapter_content: 章节内容

        Returns:
            被回收的伏笔 ID 列表
        """
        recalled_ids = []
        for f_id, item in self.foreshadowings.items():
            if item.status in (ForeshadowingStatus.RESOLVED, ForeshadowingStatus.ABANDONED):
                continue
            if item.planted_chapter and chapter_number <= item.planted_chapter:
                continue  # 跳过还没埋下的伏笔

            # 检查伏笔关键词是否出现在内容中
            keywords = self._extract_keywords(item.content)
            match_count = sum(1 for kw in keywords if kw in chapter_content)

            if match_count >= 2 or item.content[:20] in chapter_content:
                if item.status != ForeshadowingStatus.RECALLED:
                    item.status = ForeshadowingStatus.RECALLED
                    item.recalled_chapters.append(chapter_number)
                    item.last_checked_chapter = chapter_number
                    recalled_ids.append(f_id)
                    logger.info(
                        f"[Foreshadowing] 伏笔被回收 (ch{chapter_number}): {item.content[:50]}"
                    )

        return recalled_ids

    def get_pending_foreshadowings(
        self,
        current_chapter: int,
        max_count: int = 5,
    ) -> List[ForeshadowingItem]:
        """获取待回收的伏笔（用于注入 Writer prompt）.

        Args:
            current_chapter: 当前章节号
            max_count: 最大返回数量

        Returns:
            待回收的伏笔列表
        """
        pending = []
        for item in self.foreshadowings.values():
            if item.status in (ForeshadowingStatus.RESOLVED, ForeshadowingStatus.ABANDONED):
                continue
            if item.status == ForeshadowingStatus.PLANNED and not item.planted_chapter:
                continue  # 还没埋下的不提醒

            # 计算未回收的章节数
            chapters_unrecalled = current_chapter - (item.planted_chapter or 0)

            # 老化评估
            if chapters_unrecalled > self.MAX_TOTAL_CHAPTERS:
                if item.status != ForeshadowingStatus.ABANDONED:
                    item.status = ForeshadowingStatus.ABANDONED
                    logger.warning(
                        f"[Foreshadowing] 伏笔超{self.MAX_TOTAL_CHAPTERS}章未回收，标记放弃: "
                        f"{item.content[:50]}"
                    )
                continue

            pending.append(item)

        # 按重要性排序，取前 N 个
        pending.sort(key=lambda x: (-x.importance, x.planted_chapter or 0))
        return pending[:max_count]

    def format_for_prompt(self, current_chapter: int) -> str:
        """格式化为 Writer prompt 中的伏笔提醒.

        Args:
            current_chapter: 当前章节号

        Returns:
            格式化的伏笔提醒文本
        """
        pending = self.get_pending_foreshadowings(current_chapter)
        if not pending:
            return "（当前无待回收的伏笔）"

        lines = ["【待回收伏笔提醒】（请在写作时注意呼应以下内容）："]
        for item in pending:
            chapters_wait = current_chapter - (item.planted_chapter or 0)
            urgency = (
                "🔴 紧急"
                if chapters_wait > 3
                else "🟡 注意"
                if chapters_wait > 1
                else "⚪ 普通"
            )
            chars = ", ".join(item.related_characters[:2]) or "无"
            lines.append(
                f"- {urgency} {item.content} "
                f"(埋于第{item.planted_chapter}章, 已等待{chapters_wait}章, 关联角色: {chars})"
            )
        return "\n".join(lines)

    def _find_by_content(self, content: str) -> Optional[ForeshadowingItem]:
        """根据内容查找伏笔."""
        target = content.strip()[:50]  # 取前 50 字比较
        for item in self.foreshadowings.values():
            if (
                item.content == target
                or target[:30] in item.content
                or item.content[:30] in target
            ):
                return item
        return None

    def _extract_keywords(self, content: str) -> List[str]:
        """从伏笔内容中提取关键词（简单实现）."""
        # 匹配中文词汇（2-4字词）
        words = re.findall(r"[\u4e00-\u9fff]{2,4}", content)
        # 过滤常见停用词
        stop_words = {
            "一个",
            "这个",
            "那个",
            "自己",
            "我们",
            "他们",
            "什么",
            "怎么",
            "如何",
            "可以",
            "已经",
        }
        return [w for w in words if w not in stop_words]

    def to_dict(self) -> Dict[str, Any]:
        """序列化所有伏笔."""
        return {f_id: item.to_dict() for f_id, item in self.foreshadowings.items()}

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典加载伏笔."""
        for f_id, item_data in data.items():
            item = ForeshadowingItem.from_dict(item_data)
            self.foreshadowings[f_id] = item

    def get_stats(self) -> Dict[str, int]:
        """获取伏笔统计信息."""
        stats = {
            "total": len(self.foreshadowings),
            "planned": 0,
            "planted": 0,
            "recalled": 0,
            "resolved": 0,
            "abandoned": 0,
        }
        for item in self.foreshadowings.values():
            stats[item.status.value] += 1
        return stats
