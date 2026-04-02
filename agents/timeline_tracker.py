"""时间线追踪器 - 记录和管理小说时间线.

核心功能：
1. 记录每章的时间锚点（故事时间、绝对时间、相对时间）
2. 检测时间线矛盾和不一致
3. 为审查任务提供时间线上下文

解决的根本问题：
- 时间线不一致（如"三天后"变成"次日"）
- 时间推进不合理（如连续多章没有时间标记）
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.logging_config import logger


class TimeAnchorType(str, Enum):
    """时间锚点类型."""

    ABSOLUTE = "absolute"  # 绝对时间（如"2024年3月15日"）
    RELATIVE = "relative"  # 相对时间（如"三天后"、"次日清晨"）
    MARKER = "marker"  # 时间标记（如"黎明"、"深夜"、"黄昏"）


@dataclass
class TimeAnchor:
    """时间锚点 - 记录章节中的时间信息.

    Attributes:
        chapter_number: 章节号
        story_day: 故事时间天数（从故事开始计算的天数）
        absolute_time: 绝对时间（如"2024年3月15日"）
        relative_time: 相对时间（如"三天后"、"次日清晨"）
        time_markers: 时间标记词列表（如"黎明"、"深夜"）
        duration: 本章时长描述（如"两小时"、"半天"）
        confidence: 提取置信度（0-1）
        source_text: 来源文本片段（用于验证）
    """

    chapter_number: int
    story_day: int = 0
    absolute_time: str = ""
    relative_time: str = ""
    time_markers: List[str] = field(default_factory=list)
    duration: str = ""
    confidence: float = 0.0
    source_text: str = ""

    # 元数据
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "id": self.id,
            "chapter_number": self.chapter_number,
            "story_day": self.story_day,
            "absolute_time": self.absolute_time,
            "relative_time": self.relative_time,
            "time_markers": self.time_markers,
            "duration": self.duration,
            "confidence": self.confidence,
            "source_text": self.source_text[:100] if self.source_text else "",
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeAnchor":
        """从字典创建."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            chapter_number=data.get("chapter_number", 0),
            story_day=data.get("story_day", 0),
            absolute_time=data.get("absolute_time", ""),
            relative_time=data.get("relative_time", ""),
            time_markers=data.get("time_markers", []),
            duration=data.get("duration", ""),
            confidence=data.get("confidence", 0.0),
            source_text=data.get("source_text", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        parts = [f"第{self.chapter_number}章"]

        if self.story_day > 0:
            parts.append(f"故事第{self.story_day}天")

        if self.absolute_time:
            parts.append(f"时间：{self.absolute_time}")
        elif self.relative_time:
            parts.append(f"时间：{self.relative_time}")

        if self.time_markers:
            parts.append(f"时段：{', '.join(self.time_markers[:3])}")

        if self.duration:
            parts.append(f"时长：{self.duration}")

        return " | ".join(parts)


@dataclass
class TimelineInconsistency:
    """时间线不一致问题."""

    chapter_number: int
    issue_type: str  # "time_jump", "contradiction", "missing_marker", "duration_issue"
    description: str
    previous_anchor: Optional[TimeAnchor] = None
    current_anchor: Optional[TimeAnchor] = None
    severity: str = "medium"  # "high", "medium", "low"
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "chapter_number": self.chapter_number,
            "issue_type": self.issue_type,
            "description": self.description,
            "previous_anchor": (
                self.previous_anchor.to_dict() if self.previous_anchor else None
            ),
            "current_anchor": (
                self.current_anchor.to_dict() if self.current_anchor else None
            ),
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


@dataclass
class TimelineValidationReport:
    """时间线验证报告."""

    is_valid: bool = True
    inconsistencies: List[TimelineInconsistency] = field(default_factory=list)
    current_story_day: int = 0
    total_chapters_tracked: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "is_valid": self.is_valid,
            "inconsistencies": [i.to_dict() for i in self.inconsistencies],
            "current_story_day": self.current_story_day,
            "total_chapters_tracked": self.total_chapters_tracked,
        }


class TimelineTracker:
    """时间线追踪器.

    功能：
    1. 记录章节时间锚点
    2. 检测时间线矛盾
    3. 生成时间线摘要用于提示词
    """

    # 时间标记词词典
    TIME_MARKERS = {
        # 时段标记
        "黎明": "黎明",
        "清晨": "清晨",
        "早晨": "早晨",
        "上午": "上午",
        "中午": "中午",
        "正午": "正午",
        "下午": "下午",
        "傍晚": "傍晚",
        "黄昏": "黄昏",
        "夜晚": "夜晚",
        "深夜": "深夜",
        "午夜": "午夜",
        "凌晨": "凌晨",
        # 季节标记
        "春天": "春天",
        "夏天": "夏天",
        "秋天": "秋天",
        "冬天": "冬天",
    }

    # 相对时间关键词模式
    RELATIVE_TIME_PATTERNS = [
        r"(\d+)天后",
        r"(\d+)天后",
        r"次日",
        r"第二天",
        r"翌日",
        r"三天后",
        r"一周后",
        r"半月后",
        r"一个月后",
        r"半年后",
        r"一年后",
        r"数日后",
        r"数天后",
        r"片刻后",
        r"半个时辰后",
        r"一个时辰后",
        r"两个时辰后",
    ]

    # 时长关键词模式
    DURATION_PATTERNS = [
        r"持续了?(\d+)天",
        r"经历了?(\d+)天",
        r"经过(\d+)个时辰",
        r"过了?半天",
        r"过了?两个时辰",
        r"持续半日",
    ]

    def __init__(self, novel_id: str):
        """初始化时间线追踪器.

        Args:
            novel_id: 小说ID
        """
        self.novel_id = novel_id
        self.anchors: Dict[int, TimeAnchor] = {}  # {章节号: 时间锚点}
        self.current_story_day: int = 0
        self.logger = logger

        self.logger.info(f"TimelineTracker initialized for novel: {novel_id}")

    def record_anchor(self, anchor: TimeAnchor) -> None:
        """记录时间锚点.

        Args:
            anchor: 时间锚点
        """
        self.anchors[anchor.chapter_number] = anchor

        # 更新当前故事时间
        if anchor.story_day > self.current_story_day:
            self.current_story_day = anchor.story_day

        self.logger.info(
            f"Timeline anchor recorded: chapter {anchor.chapter_number}, "
            f"story_day={anchor.story_day}, relative={anchor.relative_time}"
        )

    def extract_anchor_from_text(
        self,
        chapter_number: int,
        content: str,
    ) -> TimeAnchor:
        """从章节内容中提取时间锚点.

        使用关键词匹配提取时间信息。

        Args:
            chapter_number: 章节号
            content: 章节内容

        Returns:
            提取的时间锚点
        """
        anchor = TimeAnchor(chapter_number=chapter_number)

        # 提取时间标记
        found_markers = []
        for marker, _ in self.TIME_MARKERS.items():
            if marker in content:
                found_markers.append(marker)
        anchor.time_markers = found_markers[:5]  # 最多记录5个

        # 提取相对时间
        for pattern in self.RELATIVE_TIME_PATTERNS:
            match = re.search(pattern, content)
            if match:
                anchor.relative_time = match.group(0)
                break

        # 提取时长
        for pattern in self.DURATION_PATTERNS:
            match = re.search(pattern, content)
            if match:
                anchor.duration = match.group(0)
                break

        # 计算置信度
        confidence = 0.0
        if anchor.relative_time:
            confidence += 0.4
        if anchor.time_markers:
            confidence += 0.2 * min(len(anchor.time_markers), 3)
        if anchor.duration:
            confidence += 0.2
        anchor.confidence = min(confidence, 1.0)

        # 计算故事天数
        anchor.story_day = self._estimate_story_day(chapter_number, anchor)

        # 提取来源文本（用于验证）
        if anchor.relative_time or anchor.time_markers:
            # 找到包含时间信息的句子
            sentences = re.split(r"[。！？\n]", content)
            for sentence in sentences:
                if any(m in sentence for m in anchor.time_markers) or (
                    anchor.relative_time and anchor.relative_time in sentence
                ):
                    anchor.source_text = sentence[:100]
                    break

        return anchor

    def _estimate_story_day(self, chapter_number: int, anchor: TimeAnchor) -> int:
        """估算故事天数.

        Args:
            chapter_number: 章节号
            anchor: 时间锚点

        Returns:
            估算的故事天数
        """
        # 如果有上一章的锚点，基于相对时间计算
        prev_chapter = chapter_number - 1
        if prev_chapter in self.anchors:
            prev_day = self.anchors[prev_chapter].story_day

            # 根据相对时间估算天数增量
            if anchor.relative_time:
                # 提取数字
                day_match = re.search(r"(\d+)天", anchor.relative_time)
                if day_match:
                    return prev_day + int(day_match.group(1))

                # 固定相对时间
                if anchor.relative_time in ["次日", "第二天", "翌日"]:
                    return prev_day + 1
                elif "三天后" in anchor.relative_time:
                    return prev_day + 3
                elif "一周后" in anchor.relative_time:
                    return prev_day + 7
                elif "半月后" in anchor.relative_time:
                    return prev_day + 15
                elif "一个月后" in anchor.relative_time:
                    return prev_day + 30

            # 如果没有相对时间，假设同一天或+1天
            return prev_day + 1

        # 第一章默认从第1天开始
        return 1

    def validate_consistency(
        self,
        current_chapter: int,
    ) -> TimelineValidationReport:
        """验证时间线一致性.

        Args:
            current_chapter: 当前章节号

        Returns:
            验证报告
        """
        report = TimelineValidationReport(
            current_story_day=self.current_story_day,
            total_chapters_tracked=len(self.anchors),
        )

        # 检查相邻章节的时间连续性
        sorted_chapters = sorted(self.anchors.keys())

        for i, ch in enumerate(sorted_chapters):
            if i == 0:
                continue

            prev_ch = sorted_chapters[i - 1]
            prev_anchor = self.anchors[prev_ch]
            curr_anchor = self.anchors[ch]

            # 检查时间跳跃
            day_diff = curr_anchor.story_day - prev_anchor.story_day
            if day_diff < 0:
                # 时间倒流
                report.inconsistencies.append(
                    TimelineInconsistency(
                        chapter_number=ch,
                        issue_type="time_jump",
                        description=f"时间倒流：第{prev_ch}章是第{prev_anchor.story_day}天，"
                        f"第{ch}章变为第{curr_anchor.story_day}天",
                        previous_anchor=prev_anchor,
                        current_anchor=curr_anchor,
                        severity="high",
                        suggestion=f"请检查第{ch}章的时间描述是否与第{prev_ch}章矛盾",
                    )
                )
                report.is_valid = False
            elif day_diff > 30 and not curr_anchor.relative_time:
                # 大幅跳跃但没有说明
                report.inconsistencies.append(
                    TimelineInconsistency(
                        chapter_number=ch,
                        issue_type="time_jump",
                        description=f"时间大幅跳跃：从第{prev_anchor.story_day}天跳到"
                        f"第{curr_anchor.story_day}天（跳过了{day_diff}天），"
                        f"但第{ch}章没有明确的时间说明",
                        previous_anchor=prev_anchor,
                        current_anchor=curr_anchor,
                        severity="medium",
                        suggestion=f"建议在第{ch}章开头添加时间说明，如'过了{day_diff}天'",
                    )
                )

            # 检查时间标记矛盾
            if prev_anchor.time_markers and curr_anchor.time_markers:
                # 例如：上一章是"深夜"，这一章是"清晨"但没有"次日"说明
                prev_markers = set(prev_anchor.time_markers)
                curr_markers = set(curr_anchor.time_markers)

                # 检查是否在同一天但时间顺序矛盾
                if day_diff == 0:
                    # 时段顺序
                    time_order = [
                        "黎明",
                        "清晨",
                        "早晨",
                        "上午",
                        "中午",
                        "正午",
                        "下午",
                        "傍晚",
                        "黄昏",
                        "夜晚",
                        "深夜",
                        "午夜",
                        "凌晨",
                    ]
                    for pm in prev_markers:
                        for cm in curr_markers:
                            if pm in time_order and cm in time_order:
                                prev_idx = time_order.index(pm)
                                curr_idx = time_order.index(cm)
                                # 特殊情况：凌晨可以是一天中最后的时段
                                if curr_idx < prev_idx and cm != "凌晨":
                                    report.inconsistencies.append(
                                        TimelineInconsistency(
                                            chapter_number=ch,
                                            issue_type="contradiction",
                                            description=f"时间顺序矛盾：第{prev_ch}章是'{pm}'，"
                                            f"第{ch}章变为'{cm}'，但故事还在同一天",
                                            previous_anchor=prev_anchor,
                                            current_anchor=curr_anchor,
                                            severity="medium",
                                            suggestion=f"请检查时间推进是否合理，或添加'次日'等说明",
                                        )
                                    )

        return report

    def format_for_prompt(self, current_chapter: int, max_chapters: int = 5) -> str:
        """格式化时间线信息用于提示词.

        Args:
            current_chapter: 当前章节号
            max_chapters: 最多显示的章节数

        Returns:
            格式化的时间线字符串
        """
        # 获取最近的章节
        recent_chapters = [
            ch
            for ch in sorted(self.anchors.keys(), reverse=True)
            if ch < current_chapter
        ][:max_chapters]

        if not recent_chapters:
            return "（暂无时间线记录）"

        lines = [f"当前故事时间：第 {self.current_story_day} 天"]
        lines.append("")
        lines.append("近期时间线：")

        for ch in sorted(recent_chapters):
            anchor = self.anchors[ch]
            lines.append(f"- {anchor.to_prompt()}")

        return "\n".join(lines)

    def get_time_anchor_for_chapter(self, chapter_number: int) -> Optional[TimeAnchor]:
        """获取指定章节的时间锚点.

        Args:
            chapter_number: 章节号

        Returns:
            时间锚点，如果不存在则返回None
        """
        return self.anchors.get(chapter_number)

    def get_statistics(self) -> Dict[str, Any]:
        """获取时间线统计信息."""
        return {
            "total_anchors": len(self.anchors),
            "current_story_day": self.current_story_day,
            "chapters_tracked": list(self.anchors.keys()),
            "average_confidence": (
                sum(a.confidence for a in self.anchors.values()) / len(self.anchors)
                if self.anchors
                else 0
            ),
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "novel_id": self.novel_id,
            "anchors": {str(ch): a.to_dict() for ch, a in self.anchors.items()},
            "current_story_day": self.current_story_day,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineTracker":
        """从字典反序列化."""
        tracker = cls(data.get("novel_id", ""))
        tracker.current_story_day = data.get("current_story_day", 0)

        for ch_str, anchor_data in data.get("anchors", {}).items():
            tracker.anchors[int(ch_str)] = TimeAnchor.from_dict(anchor_data)

        return tracker

    def export_to_json(self) -> str:
        """导出为JSON字符串."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def import_from_json(cls, json_str: str) -> "TimelineTracker":
        """从JSON字符串导入."""
        data = json.loads(json_str)
        return cls.from_dict(data)


# 便捷函数
def extract_timeline_anchor(chapter_number: int, content: str) -> TimeAnchor:
    """便捷函数：从章节内容提取时间锚点."""
    tracker = TimelineTracker("temp")
    return tracker.extract_anchor_from_text(chapter_number, content)


def validate_timeline(tracker: TimelineTracker, current_chapter: int) -> TimelineValidationReport:
    """便捷函数：验证时间线一致性."""
    return tracker.validate_consistency(current_chapter)