"""分层上下文压缩器 - 解决长篇小说上下文膨胀问题。

采用热/温/冷/核心四层记忆架构，将上下文保持在恒定 ~8K tokens。

层级设计：
- 热记忆 (Hot): 前 2 章完整摘要 + 前章结尾 500 字
- 温记忆 (Warm): 第 3-10 章的关键事件列表
- 冷记忆 (Cold): 更早章节的卷级摘要
- 核心记忆 (Core): 世界观 + 角色卡 + 主线（始终携带）
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class CompressedContext:
    """压缩后的上下文结构（增强版）。

    新增关键信息提取层：
    - 伏笔追踪：识别和保留未回收的伏笔
    - 角色发展轨迹：追踪角色状态变化
    - 关键事件：提取重大转折点
    - 未解决冲突：标记待解决的矛盾
    """

    core_memory: str = ""  # 核心记忆：世界观、角色、主线
    hot_memory: str = ""  # 热记忆：最近 2 章摘要
    warm_memory: str = ""  # 温记忆：前 3-10 章关键事件
    cold_memory: str = ""  # 冷记忆：卷级摘要
    previous_ending: str = ""  # 前章结尾 500 字

    # 新增：增强记忆层
    foreshadowing: List[Dict[str, Any]] = field(default_factory=list)  # 伏笔列表
    character_arcs: List[Dict[str, Any]] = field(default_factory=list)  # 角色发展轨迹
    key_events: List[Dict[str, Any]] = field(default_factory=list)  # 关键事件
    unresolved_conflicts: List[Dict[str, Any]] = field(
        default_factory=list
    )  # 未解决冲突

    total_tokens_estimate: int = 0

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        parts = []

        if self.core_memory:
            parts.append(f"【核心设定】\n{self.core_memory}")

        if self.cold_memory:
            parts.append(f"【早期剧情回顾】\n{self.cold_memory}")

        # 新增：增强记忆层
        if self.unresolved_conflicts:
            parts.append(
                f"【未解决冲突】\n{self._format_conflicts(self.unresolved_conflicts)}"
            )

        if self.foreshadowing:
            parts.append(
                f"【伏笔追踪】\n{self._format_foreshadowing(self.foreshadowing)}"
            )

        if self.character_arcs:
            parts.append(
                f"【角色发展】\n{self._format_character_arcs(self.character_arcs)}"
            )

        if self.warm_memory:
            parts.append(f"【近期剧情要点】\n{self.warm_memory}")

        if self.hot_memory:
            parts.append(f"【前章详情】\n{self.hot_memory}")

        if self.previous_ending:
            parts.append(f"【上章结尾】\n{self.previous_ending}")

        return "\n\n".join(parts)

    def _format_foreshadowing(self, foreshadowing: List[Dict[str, Any]]) -> str:
        """格式化伏笔信息."""
        lines = []
        for item in foreshadowing[:10]:  # 最多显示 10 个
            chapter = item.get("chapter", "?")
            content = item.get("content", "")[:50]
            status = item.get("status", "unresolved")
            lines.append(f"- 第{chapter}章：{content}... [{status}]")
        return "\n".join(lines)

    def _format_character_arcs(self, arcs: List[Dict[str, Any]]) -> str:
        """格式化角色发展信息."""
        lines = []
        for arc in arcs[:8]:  # 最多显示 8 个角色
            name = arc.get("name", "未知")
            changes = arc.get("recent_changes", [])
            if changes:
                lines.append(f"- {name}: {', '.join(changes[:2])}")
        return "\n".join(lines)

    def _format_conflicts(self, conflicts: List[Dict[str, Any]]) -> str:
        """格式化冲突信息."""
        lines = []
        for conflict in conflicts[:5]:  # 最多显示 5 个
            desc = conflict.get("description", "")[:50]
            priority = conflict.get("priority", "medium")
            lines.append(f"- {desc}... [优先级：{priority}]")
        return "\n".join(lines)


class ContextCompressor:
    """分层上下文压缩器。

    确保无论小说写到第几章，上下文大小保持在 ~8K tokens。
    """

    # 配置参数
    HOT_CHAPTERS = 2  # 热记忆：保留最近 N 章的完整摘要
    WARM_CHAPTERS = 8  # 温记忆：保留最近 N 章的关键事件
    MAX_EVENTS_PER_CHAPTER = 3  # 每章最多保留 N 个关键事件
    CHAPTERS_PER_VOLUME = 10  # 每卷章节数（用于冷记忆分组）

    PREVIOUS_ENDING_LENGTH = 500  # 前章结尾字数
    MAX_SUMMARY_LENGTH = 300  # 单章摘要最大字数
    MAX_VOLUME_SUMMARY_LENGTH = 200  # 卷摘要最大字数
    MAX_CORE_MEMORY_LENGTH = 2000  # 核心记忆最大字数

    def __init__(
        self,
        hot_chapters: int = 2,
        warm_chapters: int = 8,
        max_events_per_chapter: int = 3,
    ):
        self.HOT_CHAPTERS = hot_chapters
        self.WARM_CHAPTERS = warm_chapters
        self.MAX_EVENTS_PER_CHAPTER = max_events_per_chapter

    def compress(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        chapter_contents: Dict[int, str],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
        plot_outline: Any,
        volume_summaries: Optional[Dict[int, str]] = None,
    ) -> CompressedContext:
        """压缩上下文。

        Args:
            chapter_number: 当前要写的章节号
            chapter_summaries: {章节号: {key_events, plot_progress, ending_state, ...}}
            chapter_contents: {章节号: 完整内容} - 仅用于提取前章结尾
            world_setting: 世界观设定
            characters: 角色列表
            plot_outline: 情节大纲
            volume_summaries: {卷号: 卷摘要} - 可选，用于冷记忆

        Returns:
            CompressedContext
        """
        logger.info(
            f"[ContextCompressor] 压缩第 {chapter_number} 章上下文, "
            f"可用摘要: {len(chapter_summaries)} 章"
        )

        ctx = CompressedContext()

        # 1. 核心记忆（始终携带）
        ctx.core_memory = self._build_core_memory(
            world_setting, characters, plot_outline
        )

        # 2. 热记忆：前 2 章完整摘要
        ctx.hot_memory = self._build_hot_memory(chapter_number, chapter_summaries)

        # 3. 温记忆：前 3-10 章关键事件
        ctx.warm_memory = self._build_warm_memory(chapter_number, chapter_summaries)

        # 4. 冷记忆：更早章节的卷级摘要
        ctx.cold_memory = self._build_cold_memory(
            chapter_number, chapter_summaries, volume_summaries
        )

        # 5. 前章结尾
        prev_chapter = chapter_number - 1
        if prev_chapter in chapter_contents:
            content = chapter_contents[prev_chapter]
            ctx.previous_ending = self._extract_ending(content)
        elif prev_chapter in chapter_summaries:
            # 如果没有完整内容，使用摘要中的 ending_state
            summary = chapter_summaries[prev_chapter]
            ctx.previous_ending = summary.get("ending_state", "")

        # 估算 token 数（粗略：中文 1.5 字符 ≈ 1 token）
        total_len = len(ctx.to_prompt())
        ctx.total_tokens_estimate = int(total_len / 1.5)

        logger.info(
            f"[ContextCompressor] 压缩完成，估算 ~{ctx.total_tokens_estimate} tokens"
        )

        return ctx

    def _extract_foreshadowing(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        chapter_contents: Dict[int, str],
    ) -> List[Dict[str, Any]]:
        """提取伏笔信息。

        Args:
            chapter_number: 当前章节号
            chapter_summaries: 章节摘要
            chapter_contents: 章节内容

        Returns:
            伏笔列表，每个伏笔包含：chapter, content, type, status, importance
        """
        foreshadowing_list = []

        # 简单实现：从章节摘要中提取标记为伏笔的内容
        # 实际使用时可以集成 LLM 识别
        for ch in range(1, chapter_number):
            if ch not in chapter_summaries:
                continue

            summary = chapter_summaries[ch]

            # 检查是否有伏笔标记
            if "foreshadowing" in summary:
                foreshadowing_list.append(
                    {
                        "chapter": ch,
                        "content": summary.get("foreshadowing", ""),
                        "type": summary.get("foreshadowing_type", "plot"),
                        "status": "unresolved",
                        "importance": summary.get("importance", 3),
                    }
                )

        return foreshadowing_list

    def _track_character_changes(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        characters: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """追踪角色发展轨迹。

        Args:
            chapter_number: 当前章节号
            chapter_summaries: 章节摘要
            characters: 角色列表

        Returns:
            角色发展列表，每个角色包含：name, chapter_range, recent_changes, current_state
        """
        character_arcs = []

        # 构建角色名称到角色的映射
        char_map = {char.get("name", ""): char for char in characters}

        # 追踪每个角色的变化
        for char_name, char_data in char_map.items():
            if not char_name:
                continue

            recent_changes = []
            chapters_appeared = []

            # 扫描最近 10 章
            for ch in range(max(1, chapter_number - 10), chapter_number):
                if ch not in chapter_summaries:
                    continue

                summary = chapter_summaries[ch]
                key_events = summary.get("key_events", [])

                # 检查角色是否出现在关键事件中
                for event in key_events:
                    if char_name in str(event):
                        chapters_appeared.append(ch)
                        if "change" in str(event).lower() or "发展" in str(event):
                            recent_changes.append(str(event)[:100])

            # 只添加有变化的角色
            if recent_changes or len(chapters_appeared) > 0:
                character_arcs.append(
                    {
                        "name": char_name,
                        "chapter_range": [
                            min(chapters_appeared) if chapters_appeared else 1,
                            chapter_number - 1,
                        ],
                        "recent_changes": recent_changes[:3],  # 最多 3 个变化
                        "current_state": char_data.get("current_status", "未知"),
                    }
                )

        return character_arcs

    def _extract_key_events(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """提取关键事件。

        Args:
            chapter_number: 当前章节号
            chapter_summaries: 章节摘要

        Returns:
            关键事件列表，每个事件包含：chapter, description, importance, type
        """
        key_events = []

        # 扫描最近 10 章
        for ch in range(max(1, chapter_number - 10), chapter_number):
            if ch not in chapter_summaries:
                continue

            summary = chapter_summaries[ch]
            events = summary.get("key_events", [])

            for event in events:
                if isinstance(event, dict):
                    key_events.append(
                        {
                            "chapter": ch,
                            "description": event.get("description", str(event))[:100],
                            "importance": event.get("importance", 3),
                            "type": event.get("type", "plot"),
                        }
                    )
                else:
                    # 字符串事件
                    key_events.append(
                        {
                            "chapter": ch,
                            "description": str(event)[:100],
                            "importance": 3,
                            "type": "plot",
                        }
                    )

        # 按重要性排序，取前 10 个
        key_events.sort(key=lambda x: x.get("importance", 3), reverse=True)
        return key_events[:10]

    def _identify_unresolved_conflicts(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        plot_outline: Any,
    ) -> List[Dict[str, Any]]:
        """识别未解决的冲突。

        Args:
            chapter_number: 当前章节号
            chapter_summaries: 章节摘要
            plot_outline: 情节大纲

        Returns:
            未解决冲突列表，每个冲突包含：description, related_characters, priority, since_chapter
        """
        conflicts = []

        # 从章节摘要中识别未解决的冲突
        for ch in range(max(1, chapter_number - 10), chapter_number):
            if ch not in chapter_summaries:
                continue

            summary = chapter_summaries[ch]

            # 检查是否有冲突标记
            if "conflicts" in summary:
                for conflict in summary.get("conflicts", []):
                    if isinstance(conflict, dict):
                        conflicts.append(
                            {
                                "description": conflict.get("description", "")[:100],
                                "related_characters": conflict.get("characters", []),
                                "priority": conflict.get("priority", "medium"),
                                "since_chapter": ch,
                                "status": "unresolved",
                            }
                        )

        return conflicts

    def _build_core_memory(
        self,
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
        plot_outline: Any,
    ) -> str:
        """构建核心记忆：世界观 + 主要角色 + 主线."""
        parts = []

        # 世界观精简
        if world_setting:
            world_brief = self._compress_world_setting(world_setting)
            if world_brief:
                parts.append(f"世界观：{world_brief}")

        # 主要角色（只保留主角和重要配角）
        if characters:
            main_chars = self._compress_characters(characters)
            if main_chars:
                parts.append(f"主要角色：{main_chars}")

        # 主线情节
        if plot_outline:
            main_plot = self._compress_plot_outline(plot_outline)
            if main_plot:
                parts.append(f"主线：{main_plot}")

        result = "\n".join(parts)
        return result[: self.MAX_CORE_MEMORY_LENGTH]

    def _build_hot_memory(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> str:
        """构建热记忆：前 2 章完整摘要."""
        hot_start = max(1, chapter_number - self.HOT_CHAPTERS)
        parts = []

        for ch in range(hot_start, chapter_number):
            if ch not in chapter_summaries:
                continue

            summary = chapter_summaries[ch]
            chapter_text = self._format_chapter_summary(ch, summary)
            parts.append(chapter_text)

        return "\n".join(parts)

    def _build_warm_memory(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> str:
        """构建温记忆：前 3-10 章关键事件."""
        hot_start = max(1, chapter_number - self.HOT_CHAPTERS)
        warm_start = max(1, hot_start - self.WARM_CHAPTERS)
        warm_end = hot_start

        if warm_start >= warm_end:
            return ""

        events = []
        for ch in range(warm_start, warm_end):
            if ch not in chapter_summaries:
                continue

            summary = chapter_summaries[ch]
            key_events = summary.get("key_events", [])

            # 每章最多取 N 个关键事件
            for event in key_events[: self.MAX_EVENTS_PER_CHAPTER]:
                if isinstance(event, str):
                    events.append(f"第{ch}章: {event}")
                elif isinstance(event, dict):
                    events.append(
                        f"第{ch}章: {event.get('event', event.get('description', str(event)))}"
                    )

        if not events:
            return ""

        return "\n".join(events)

    def _build_cold_memory(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        volume_summaries: Optional[Dict[int, str]] = None,
    ) -> str:
        """构建冷记忆：更早章节的卷级摘要."""
        # 冷记忆起始点：跳过热+温记忆覆盖的章节
        cold_end = max(1, chapter_number - self.HOT_CHAPTERS - self.WARM_CHAPTERS)

        if cold_end <= 1:
            return ""

        # 如果有预计算的卷摘要，直接使用
        if volume_summaries:
            parts = []
            for vol_num, vol_summary in sorted(volume_summaries.items()):
                # 检查这个卷是否在冷记忆范围内
                vol_start = (vol_num - 1) * self.CHAPTERS_PER_VOLUME + 1
                if vol_start < cold_end:
                    parts.append(f"第{vol_num}卷: {vol_summary}")
            return "\n".join(parts)

        # 否则，按卷聚合章节摘要
        volumes: Dict[int, List[str]] = {}
        for ch in range(1, cold_end):
            if ch not in chapter_summaries:
                continue

            vol_num = (ch - 1) // self.CHAPTERS_PER_VOLUME + 1
            if vol_num not in volumes:
                volumes[vol_num] = []

            summary = chapter_summaries[ch]
            plot_progress = summary.get("plot_progress", "")
            if plot_progress:
                volumes[vol_num].append(plot_progress[:100])

        # 合并为卷摘要
        parts = []
        for vol_num, summaries in sorted(volumes.items()):
            combined = "；".join(summaries)
            parts.append(f"第{vol_num}卷: {combined[:self.MAX_VOLUME_SUMMARY_LENGTH]}")

        return "\n".join(parts)

    def _format_chapter_summary(
        self, chapter_number: int, summary: Dict[str, Any]
    ) -> str:
        """格式化单章摘要."""
        parts = [f"第{chapter_number}章"]

        # 情节进展
        plot_progress = summary.get("plot_progress", "")
        if plot_progress:
            parts.append(f"剧情: {plot_progress[:self.MAX_SUMMARY_LENGTH]}")

        # 关键事件
        key_events = summary.get("key_events", [])
        if key_events:
            events_text = "、".join(
                str(e) if isinstance(e, str) else e.get("event", str(e))
                for e in key_events[:3]
            )
            parts.append(f"事件: {events_text}")

        # 角色变化
        char_changes = summary.get("character_changes", "")
        if char_changes:
            parts.append(f"角色: {char_changes[:100]}")

        return " | ".join(parts)

    def _extract_ending(self, content: str) -> str:
        """提取章节结尾部分."""
        if not content:
            return ""

        ending = content[-self.PREVIOUS_ENDING_LENGTH :]

        # 尝试从句子开头开始
        first_period = ending.find("。")
        if 0 < first_period < 100:
            ending = ending[first_period + 1 :]

        return ending.strip()

    def _compress_world_setting(self, world_setting: Dict[str, Any]) -> str:
        """压缩世界观设定."""
        parts = []

        # 世界类型
        world_type = world_setting.get("world_type", "")
        if world_type:
            parts.append(world_type)

        # 力量体系
        power_system = world_setting.get("power_system", {})
        if isinstance(power_system, dict):
            system_name = power_system.get("name", "")
            if system_name:
                parts.append(f"力量体系:{system_name}")
        elif isinstance(power_system, str):
            parts.append(f"力量体系:{power_system[:50]}")

        # 主要势力
        factions = world_setting.get("factions", [])
        if factions:
            faction_names = []
            for f in factions[:3]:
                if isinstance(f, dict):
                    faction_names.append(f.get("name", str(f)))
                else:
                    faction_names.append(str(f))
            parts.append(f"势力:{','.join(faction_names)}")

        return "；".join(parts)

    def _compress_characters(self, characters: List[Dict[str, Any]]) -> str:
        """压缩角色信息，只保留主要角色."""
        main_chars = []

        for char in characters:
            role_type = char.get("role_type", "")
            name = char.get("name", "")

            # 只保留主角和重要配角
            if (
                role_type in ("protagonist", "主角", "supporting", "配角")
                or not role_type
            ):
                char_brief = name
                personality = char.get("personality", "")
                if personality:
                    char_brief += f"({personality[:20]})"
                main_chars.append(char_brief)

            if len(main_chars) >= 5:  # 最多 5 个角色
                break

        return "、".join(main_chars)

    def _compress_plot_outline(self, plot_outline: Any) -> str:
        """压缩情节大纲."""
        if isinstance(plot_outline, str):
            return plot_outline[:200]

        if isinstance(plot_outline, list):
            # 如果是卷列表
            parts = []
            for vol in plot_outline[:3]:
                if isinstance(vol, dict):
                    title = vol.get("title", "")
                    summary = vol.get("summary", "")
                    parts.append(f"{title}:{summary[:50]}")
            return "；".join(parts)

        if isinstance(plot_outline, dict):
            # 提取主线情节
            main_plot = plot_outline.get("main_plot", "")
            if isinstance(main_plot, str):
                return main_plot[:200]
            if isinstance(main_plot, dict):
                return main_plot.get("summary", str(main_plot))[:200]

            # 或者卷列表
            volumes = plot_outline.get("volumes", [])
            if volumes:
                return self._compress_plot_outline(volumes)

        return ""


# 便捷函数
def compress_context(
    chapter_number: int,
    chapter_summaries: Dict[int, Dict[str, Any]],
    chapter_contents: Dict[int, str],
    world_setting: Dict[str, Any],
    characters: List[Dict[str, Any]],
    plot_outline: Any,
    **kwargs,
) -> CompressedContext:
    """便捷函数：压缩上下文."""
    compressor = ContextCompressor(**kwargs)
    return compressor.compress(
        chapter_number=chapter_number,
        chapter_summaries=chapter_summaries,
        chapter_contents=chapter_contents,
        world_setting=world_setting,
        characters=characters,
        plot_outline=plot_outline,
    )
