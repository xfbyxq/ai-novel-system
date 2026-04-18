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

from agents.base.json_extractor import JsonExtractor
from core.logging_config import logger
from llm.qwen_client import QwenClient


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


@dataclass
class ImplicitTimeInfo:
    """隐性时间信息 - 从文本中提取的非直接时间表达.

    用于识别文本中隐晦的时间线索，如季节变化、年龄增长、长期进度等，
    这些线索不直接表达时间，但可以推断出时间跨度。

    Attributes:
        chapter_number: 章节号
        season_indicators: 季节线索（如"雪花纷飞"、"春暖花开"）
        aging_indicators: 年龄变化线索（如"少年长成青年"、"白发渐生"）
        long_term_progress: 长期进度线索（如"修炼已过百日"、"战争持续数月"）
        estimated_time_span: 估算时间跨度描述
        confidence: 提取置信度（0-1）
        source_snippets: 来源文本片段列表
    """

    chapter_number: int = 0
    season_indicators: List[str] = field(default_factory=list)
    aging_indicators: List[str] = field(default_factory=list)
    long_term_progress: List[str] = field(default_factory=list)
    estimated_time_span: str = ""
    confidence: float = 0.0
    source_snippets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典."""
        return {
            "chapter_number": self.chapter_number,
            "season_indicators": self.season_indicators,
            "aging_indicators": self.aging_indicators,
            "long_term_progress": self.long_term_progress,
            "estimated_time_span": self.estimated_time_span,
            "confidence": self.confidence,
            "source_snippets": self.source_snippets,
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

    async def extract_anchor_enhanced(
        self,
        chapter_number: int,
        content: str,
    ) -> TimeAnchor:
        """增强版时间锚点提取（支持LLM辅助）.

        在正则提取基础上，当置信度不足时调用LLM进行补充提取。

        Args:
            chapter_number: 章节号
            content: 章节内容

        Returns:
            提取的时间锚点
        """
        # 先使用正则提取
        anchor = self.extract_anchor_from_text(chapter_number, content)

        # 当正则提取置信度不足时，使用LLM辅助提取
        if anchor.confidence < 0.5:
            try:
                llm_anchor = await self._llm_extract_time_info(content, chapter_number)
                if llm_anchor and llm_anchor.confidence > anchor.confidence:
                    # 合并LLM结果（优先保留正则的精确匹配，补充LLM的额外信息）
                    anchor = self._merge_time_anchors(anchor, llm_anchor)
            except Exception as e:
                logger.warning(f"LLM时间提取失败: {e}")

        return anchor

    async def _llm_extract_time_info(
        self,
        content: str,
        chapter_number: int,
    ) -> Optional[TimeAnchor]:
        """使用LLM提取时间信息作为正则提取的补充.

        Args:
            content: 章节内容
            chapter_number: 章节号

        Returns:
            LLM提取的时间锚点，失败返回None
        """
        # 截取内容前2000字符，避免token过多
        truncated_content = content[:2000]

        system_prompt = """你是时间信息提取专家。从小说章节中提取时间相关信息。
请输出JSON格式：
{
    "absolute_time": "绝对时间（如2024年3月15日），无则留空",
    "relative_time": "相对时间（如三天后、次日清晨），无则留空",
    "time_markers": ["时间标记词列表，如黎明、深夜"],
    "duration": "本章时长描述（如两小时、半天），无则留空",
    "story_day": 故事第几天（数字，无法推断则填0）,
    "confidence": 置信度（0-1之间的小数）
}"""

        user_prompt = f"""请从以下第{chapter_number}章内容中提取时间信息：

{truncated_content}

请只输出JSON，不要其他解释。"""

        try:
            client = QwenClient()
            response = await client.chat(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.3,
            )

            result = JsonExtractor.extract_object(response.get("content", ""))

            if not result:
                return None

            anchor = TimeAnchor(
                chapter_number=chapter_number,
                absolute_time=result.get("absolute_time", ""),
                relative_time=result.get("relative_time", ""),
                time_markers=result.get("time_markers", []),
                duration=result.get("duration", ""),
                story_day=result.get("story_day", 0),
                confidence=result.get("confidence", 0.5),
                source_text=truncated_content[:100],
            )

            return anchor

        except Exception as e:
            logger.warning(f"LLM提取时间信息失败: {e}")
            return None

    def _merge_time_anchors(
        self,
        regex_anchor: TimeAnchor,
        llm_anchor: TimeAnchor,
    ) -> TimeAnchor:
        """合并正则和LLM提取的时间锚点.

        策略：优先保留正则的精确匹配，补充LLM的额外信息。

        Args:
            regex_anchor: 正则提取的时间锚点
            llm_anchor: LLM提取的时间锚点

        Returns:
            合并后的时间锚点
        """
        merged = TimeAnchor(
            chapter_number=regex_anchor.chapter_number,
            id=regex_anchor.id,
            created_at=regex_anchor.created_at,
        )

        # 相对时间：优先使用正则结果（更精确）
        merged.relative_time = regex_anchor.relative_time or llm_anchor.relative_time

        # 绝对时间：优先使用正则结果
        merged.absolute_time = regex_anchor.absolute_time or llm_anchor.absolute_time

        # 时长：优先使用正则结果
        merged.duration = regex_anchor.duration or llm_anchor.duration

        # 时间标记：合并两者，去重
        merged_markers = list(set(regex_anchor.time_markers + llm_anchor.time_markers))
        merged.time_markers = merged_markers[:5]  # 最多保留5个

        # 故事天数：优先使用正则结果（基于已有时间线计算）
        if regex_anchor.story_day > 0:
            merged.story_day = regex_anchor.story_day
        elif llm_anchor.story_day > 0:
            merged.story_day = llm_anchor.story_day

        # 来源文本：优先使用正则的
        merged.source_text = regex_anchor.source_text or llm_anchor.source_text

        # 置信度：取两者较高值，但最高不超过0.9
        merged.confidence = min(max(regex_anchor.confidence, llm_anchor.confidence), 0.9)

        return merged

    async def extract_implicit_time_info(
        self,
        chapter_content: str,
        chapter_number: int,
    ) -> ImplicitTimeInfo:
        """使用LLM提取隐性时间信息.

        识别以下隐性时间表达：
        - 季节变化：雪花纷飞、春暖花开、秋叶飘零等
        - 年龄增长：少年长成青年、白发渐生等
        - 长期进度：修炼已过百日、战争持续数月等
        - 生理变化：伤口已愈合、肚子隆起等

        Args:
            chapter_content: 章节内容
            chapter_number: 章节号

        Returns:
            隐性时间信息对象
        """
        # 截取内容前3000字符
        truncated_content = chapter_content[:3000]

        system_prompt = """你是隐性时间信息提取专家。从小说文本中识别隐晦的时间线索。
这些线索不直接表达时间，但可以推断出时间跨度。

请输出JSON格式：
{
    "season_indicators": ["季节线索，如雪花纷飞、春暖花开、秋叶飘零"],
    "aging_indicators": ["年龄变化线索，如少年长成青年、白发渐生"],
    "long_term_progress": ["长期进度线索，如修炼已过百日、战争持续数月"],
    "estimated_time_span": "估算的时间跨度描述（如约三个月、半年左右）",
    "confidence": 置信度（0-1之间的小数）,
    "source_snippets": ["来源文本片段，每个片段不超过50字"]
}"""

        user_prompt = f"""请从以下第{chapter_number}章内容中提取隐性时间信息：

{truncated_content}

请只输出JSON，不要其他解释。"""

        try:
            client = QwenClient()
            response = await client.chat(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.3,
            )

            result = JsonExtractor.extract_object(response.get("content", ""))

            if not result:
                return ImplicitTimeInfo(chapter_number=chapter_number)

            return ImplicitTimeInfo(
                chapter_number=chapter_number,
                season_indicators=result.get("season_indicators", []),
                aging_indicators=result.get("aging_indicators", []),
                long_term_progress=result.get("long_term_progress", []),
                estimated_time_span=result.get("estimated_time_span", ""),
                confidence=result.get("confidence", 0.0),
                source_snippets=result.get("source_snippets", []),
            )

        except Exception as e:
            logger.warning(f"提取隐性时间信息失败: {e}")
            return ImplicitTimeInfo(chapter_number=chapter_number)

    def validate_npc_timeline(
        self,
        character_name: str,
        character_status: Dict[str, Any],
        chapters_data: List[Dict[str, Any]],
    ) -> List[TimelineInconsistency]:
        """验证特定角色的时间线一致性.

        检查：
        1. 已死亡角色不应在后续章节中活着出现
        2. 角色离开某地后不应在未返回的情况下出现在该地
        3. 角色的伤势/状态应按时间合理变化

        Args:
            character_name: 角色名
            character_status: 角色状态信息，如 {"status": "dead", "death_chapter": 5}
            chapters_data: 各章节的出场信息列表，每项包含
                {"chapter": 1, "location": "长安", "status": "alive", "injuries": []}

        Returns:
            时间线不一致问题列表
        """
        inconsistencies: List[TimelineInconsistency] = []

        if not chapters_data:
            return inconsistencies

        # 按章节号排序
        sorted_chapters = sorted(chapters_data, key=lambda x: x.get("chapter", 0))

        # 检查1：死亡后不应再出现
        death_chapter = character_status.get("death_chapter")
        if death_chapter and character_status.get("status") == "dead":
            for ch_data in sorted_chapters:
                ch_num = ch_data.get("chapter", 0)
                if ch_num > death_chapter and ch_data.get("status") == "alive":
                    inconsistencies.append(
                        TimelineInconsistency(
                            chapter_number=ch_num,
                            issue_type="npc_timeline",
                            description=f"角色'{character_name}'在第{death_chapter}章已死亡，"
                            f"但在第{ch_num}章仍然活着出现",
                            severity="high",
                            suggestion=f"请检查第{ch_num}章中该角色的状态，"
                            f"应改为回忆、幻觉或其他合理解释",
                        )
                    )

        # 检查2：地点一致性
        last_location: Optional[str] = None
        last_chapter: int = 0
        for ch_data in sorted_chapters:
            ch_num = ch_data.get("chapter", 0)
            location = ch_data.get("location")
            travel_method = ch_data.get("travel_method")  # 移动方式

            if location and last_location and location == last_location:
                # 同一地点连续出现，检查是否合理
                if ch_num - last_chapter > 1 and not travel_method:
                    # 跨多章仍在同一地点，但没有说明如何返回
                    inconsistencies.append(
                        TimelineInconsistency(
                            chapter_number=ch_num,
                            issue_type="npc_location",
                            description=f"角色'{character_name}'在第{last_chapter}章出现在'{last_location}'，"
                            f"中间经过{ch_num - last_chapter - 1}章后"
                            f"又在第{ch_num}章出现在同一地点，"
                            f"但没有说明如何返回",
                            severity="medium",
                            suggestion=f"建议补充角色返回'{last_location}'的过程描述",
                        )
                    )

            last_location = location
            last_chapter = ch_num

        # 检查3：伤势状态合理性
        last_injuries: List[str] = []
        last_chapter_for_injury = 0
        for ch_data in sorted_chapters:
            ch_num = ch_data.get("chapter", 0)
            injuries = ch_data.get("injuries", [])

            # 检查伤势恢复是否合理（简单规则：重伤不会在1章内完全恢复）
            if last_injuries and not injuries:
                # 伤势消失，检查章节间隔
                if ch_num - last_chapter_for_injury < 2:
                    severe_injuries = [i for i in last_injuries if "重" in i or "伤" in i]
                    if severe_injuries:
                        inconsistencies.append(
                            TimelineInconsistency(
                                chapter_number=ch_num,
                                issue_type="npc_injury",
                                description=f"角色'{character_name}'在第{last_chapter_for_injury}章"
                                f"受重伤({', '.join(severe_injuries)})，"
                                f"但在第{ch_num}章伤势完全消失，恢复过快",
                                severity="low",
                                suggestion="建议补充伤势恢复过程，或调整章节时间间隔",
                            )
                        )

            if injuries:
                last_injuries = injuries
                last_chapter_for_injury = ch_num

        return inconsistencies

    def detect_time_acceleration(
        self,
        threshold: float = 3.0,
    ) -> List[TimelineInconsistency]:
        """检测时间加速/减速异常.

        基于已记录的TimeAnchor数据：
        - 计算相邻章节之间的时间跨度
        - 计算平均时间推进速度
        - 标记偏离平均速度超过threshold倍的章节

        例如：前5章每章推进1天，第6章突然跳到1年后 -> 异常

        Args:
            threshold: 偏离阈值倍数，默认3.0倍

        Returns:
            时间线不一致问题列表
        """
        inconsistencies: List[TimelineInconsistency] = []

        # 需要至少3个章节的数据才有意义
        if len(self.anchors) < 3:
            return inconsistencies

        # 按章节号排序
        sorted_chapters = sorted(self.anchors.keys())

        # 计算各章节间的时间跨度
        time_jumps: List[Tuple[int, int, int]] = []  # (章节号, 天数差, 章节间隔)
        for i in range(1, len(sorted_chapters)):
            prev_ch = sorted_chapters[i - 1]
            curr_ch = sorted_chapters[i]
            prev_anchor = self.anchors[prev_ch]
            curr_anchor = self.anchors[curr_ch]

            day_diff = curr_anchor.story_day - prev_anchor.story_day
            chapter_gap = curr_ch - prev_ch

            if day_diff >= 0 and chapter_gap > 0:
                time_jumps.append((curr_ch, day_diff, chapter_gap))

        if len(time_jumps) < 2:
            return inconsistencies

        # 计算平均每章推进天数（排除0天的情况）
        speeds = [day_diff / ch_gap for _, day_diff, ch_gap in time_jumps if day_diff > 0]
        if not speeds:
            return inconsistencies

        avg_speed = sum(speeds) / len(speeds)

        # 检测异常加速/减速
        for ch_num, day_diff, ch_gap in time_jumps:
            if day_diff <= 0:
                continue

            current_speed = day_diff / ch_gap

            # 检测加速（当前速度远大于平均速度）
            if current_speed > avg_speed * threshold and day_diff > 7:
                inconsistencies.append(
                    TimelineInconsistency(
                        chapter_number=ch_num,
                        issue_type="time_acceleration",
                        description=f"时间加速异常：第{ch_num}章时间推进了{day_diff}天，"
                        f"平均每章推进{current_speed:.1f}天，"
                        f"是平均速度({avg_speed:.1f}天/章)的{current_speed/avg_speed:.1f}倍",
                        current_anchor=self.anchors.get(ch_num),
                        severity="medium",
                        suggestion=f"建议检查第{ch_num}章的时间跳跃是否合理，"
                        f"或在前文添加时间过渡说明",
                    )
                )

            # 检测减速（当前速度远小于平均速度，但不是0）
            elif avg_speed > 1 and current_speed < avg_speed / threshold and current_speed < 1:
                inconsistencies.append(
                    TimelineInconsistency(
                        chapter_number=ch_num,
                        issue_type="time_deceleration",
                        description=f"时间减速异常：第{ch_num}章时间仅推进{day_diff}天，"
                        f"平均每章推进{current_speed:.1f}天，"
                        f"远低于平均速度({avg_speed:.1f}天/章)",
                        current_anchor=self.anchors.get(ch_num),
                        severity="low",
                        suggestion="如果这是有意为之（如详细描写某一天），请忽略此提示",
                    )
                )

        return inconsistencies

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
                                            suggestion="请检查时间推进是否合理，或添加'次日'等说明",
                                        )
                                    )

        return report

    def enforce_monotonic_time(
        self,
        chapter_number: int,
        proposed_anchor: TimeAnchor,
    ) -> Tuple[bool, List[TimelineInconsistency]]:
        """强制时间单调递增校验.

        每章结束后记录时间标记，下一章的时间标记必须 >= 上一章。
        如检测到时间回退，立即标记为 high severity 问题。

        Args:
            chapter_number: 当前章节号
            proposed_anchor: 提议的时间锚点

        Returns:
            (是否通过, 不一致问题列表)
        """
        inconsistencies: List[TimelineInconsistency] = []
        prev_chapter = chapter_number - 1

        if prev_chapter not in self.anchors:
            # 无前章，直接通过
            return True, inconsistencies

        prev_anchor = self.anchors[prev_chapter]

        # 1. 检查故事天数是否回退
        if proposed_anchor.story_day < prev_anchor.story_day:
            inconsistencies.append(
                TimelineInconsistency(
                    chapter_number=chapter_number,
                    issue_type="time_jump",
                    description=f"时间回退：第{chapter_number}章故事第{proposed_anchor.story_day}天，"
                    f"早于第{prev_chapter}章的故事第{prev_anchor.story_day}天",
                    previous_anchor=prev_anchor,
                    current_anchor=proposed_anchor,
                    severity="high",
                    suggestion=f"第{chapter_number}章的故事天数必须 >= 第{prev_chapter}章的"
                    f"{prev_anchor.story_day}天，请修正时间描述",
                )
            )

        # 2. 检查时段顺序（同一天内）
        if proposed_anchor.story_day == prev_anchor.story_day:
            time_order = [
                "黎明", "清晨", "早晨", "上午", "中午", "正午",
                "下午", "傍晚", "黄昏", "夜晚", "深夜", "午夜", "凌晨",
            ]
            prev_markers = prev_anchor.time_markers
            curr_markers = proposed_anchor.time_markers

            if prev_markers and curr_markers:
                for pm in prev_markers:
                    for cm in curr_markers:
                        if pm in time_order and cm in time_order:
                            prev_idx = time_order.index(pm)
                            curr_idx = time_order.index(cm)
                            if curr_idx < prev_idx and cm != "凌晨":
                                inconsistencies.append(
                                    TimelineInconsistency(
                                        chapter_number=chapter_number,
                                        issue_type="contradiction",
                                        description=f"时段回退：第{prev_chapter}章已到'{pm}'，"
                                        f"第{chapter_number}章仍在同一天但变为'{cm}'",
                                        previous_anchor=prev_anchor,
                                        current_anchor=proposed_anchor,
                                        severity="high",
                                        suggestion=f"建议将第{chapter_number}章时间标记为'次日{cm}'或之后",
                                    )
                                )

        # 3. 检查相对时间是否回退
        if prev_anchor.relative_time and proposed_anchor.relative_time:
            prev_order = self._time_mark_to_order_value(prev_anchor.relative_time)
            curr_order = self._time_mark_to_order_value(proposed_anchor.relative_time)
            if 0 < curr_order < prev_order:
                inconsistencies.append(
                    TimelineInconsistency(
                        chapter_number=chapter_number,
                        issue_type="contradiction",
                        description=f"相对时间回退：第{prev_chapter}章为「{prev_anchor.relative_time}」，"
                        f"第{chapter_number}章变为「{proposed_anchor.relative_time}」",
                        previous_anchor=prev_anchor,
                        current_anchor=proposed_anchor,
                        severity="high",
                        suggestion="请确认时间推进是否合理，禁止无理由的时间回退",
                    )
                )

        passed = len(inconsistencies) == 0
        return passed, inconsistencies

    def _time_mark_to_order_value(self, mark: str) -> int:
        """将时间标记转换为可比较的顺序值.

        Returns:
            0=未知, 1+=可比较的顺序值
        """
        # 天数标记
        day_patterns = [
            (r"第(\d+)天", lambda m: int(m.group(1)) * 1000),
            (r"故事第(\d+)天", lambda m: int(m.group(1)) * 1000),
            (r"(\d+)天后", lambda m: int(m.group(1)) * 1000),
            (r"(\d+)日后", lambda m: int(m.group(1)) * 1000),
        ]
        import re as re_mod
        for pattern, extractor in day_patterns:
            match = re_mod.search(pattern, mark)
            if match:
                return extractor(match)

        # 相对时间
        relative_markers = {
            "次日": 1000, "翌日": 1000, "第二天": 1000,
            "三天后": 3000, "一周后": 7000, "半月后": 15000,
            "一个月后": 30000, "数日后": 5000, "数天后": 5000,
        }
        for marker, order in relative_markers.items():
            if marker in mark:
                return order

        # 时段（不关联天数的情况下，时段本身不可比较）
        return 0

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
