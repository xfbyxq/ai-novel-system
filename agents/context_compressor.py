"""分层上下文压缩器 - 解决长篇小说上下文膨胀问题.

采用热/温/冷/核心四层记忆架构，将上下文保持在恒定 ~8K tokens。

层级设计：
- 热记忆 (Hot): 前 2 章完整摘要 + 前章结尾 500 字
- 温记忆 (Warm): 第 3-10 章的关键事件列表
- 冷记忆 (Cold): 更早章节的卷级摘要
- 核心记忆 (Core): 世界观 + 角色卡 + 主线（始终携带）
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class CompressedContext:
    """压缩后的上下文结构（增强版）.

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
    """分层上下文压缩器.

    采用动态压缩策略：先构建完整内容，总量超阈值时按优先级逐步压缩。
    优先级从高到低：core > ending > hot > warm > cold
    """

    # 配置参数
    HOT_CHAPTERS = 2  # 热记忆：保留最近 N 章的完整摘要
    WARM_CHAPTERS = 8  # 温记忆：保留最近 N 章的关键事件
    MAX_EVENTS_PER_CHAPTER = 3  # 每章最多保留 N 个关键事件
    CHAPTERS_PER_VOLUME = 10  # 每卷章节数（用于冷记忆分组）

    # 动态压缩配置
    MAX_TOTAL_TOKENS = 8000  # 总上下文token阈值（超出时启动压缩）
    PREVIOUS_ENDING_LENGTH = 800  # 前章结尾完整长度（增大以保留更多内容）
    SAFETY_MARGIN = 0.95  # 安全系数，避免边界溢出

    # 优先级定义（数值越小优先级越高，压缩时优先保留）
    PRIORITY_LEVELS = {
        'core': 1,      # 世界观、角色卡、主线 - 最高优先，始终保留
        'ending': 2,    # 前章结尾 - 高优先，影响衔接连贯性
        'hot': 3,       # 前2章摘要 - 中高优先，近期剧情
        'warm': 4,      # 前3-10章关键事件 - 中优先
        'cold': 5,      # 卷级摘要 - 低优先，最早被压缩
    }

    def __init__(
        self,
        hot_chapters: int = 2,
        warm_chapters: int = 8,
        max_events_per_chapter: int = 3,
        max_total_tokens: int = 8000,
    ):
        """初始化方法.

        Args:
            hot_chapters: 热记忆章节数
            warm_chapters: 温记忆章节数
            max_events_per_chapter: 每章最大事件数
            max_total_tokens: 总token阈值
        """
        self.HOT_CHAPTERS = hot_chapters
        self.WARM_CHAPTERS = warm_chapters
        self.MAX_EVENTS_PER_CHAPTER = max_events_per_chapter
        self.MAX_TOTAL_TOKENS = max_total_tokens

    def compress(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        chapter_contents: Dict[int, str],
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
        plot_outline: Any,
        volume_summaries: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> CompressedContext:
        """压缩上下文 - 动态策略版本.

        核心改进：先构建完整内容，总量超阈值时才按优先级逐步压缩。

        Args:
            chapter_number: 当前要写的章节号
            chapter_summaries: {章节号: {key_events, plot_progress, ending_state, ...}}
            chapter_contents: {章节号: 完整内容} - 用于提取前章结尾
            world_setting: 世界观设定
            characters: 角色列表
            plot_outline: 情节大纲
            volume_summaries: {卷号: {"summary": 摘要, "chapters": [start, end]}} - 可选

        Returns:
            CompressedContext - 压缩后的上下文，控制在MAX_TOTAL_TOKENS内
        """
        logger.info(
            f"[ContextCompressor] 构建第 {chapter_number} 章上下文, "
            f"可用摘要: {len(chapter_summaries)} 章, 可用内容: {len(chapter_contents)} 章"
        )

        ctx = CompressedContext()

        # ===== 步骤1：构建完整内容（不截取） =====
        # 1. 核心记忆（始终携带，优先级最高）
        ctx.core_memory = self._build_core_memory_full(
            world_setting, characters, plot_outline
        )

        # 2. 热记忆：前 N 章完整摘要（不截取）
        ctx.hot_memory = self._build_hot_memory_full(chapter_number, chapter_summaries)

        # 3. 温记忆：前章节关键事件（完整描述）
        ctx.warm_memory = self._build_warm_memory_full(chapter_number, chapter_summaries)

        # 4. 冷记忆：卷级摘要（完整摘要）
        ctx.cold_memory = self._build_cold_memory_full(
            chapter_number, chapter_summaries, volume_summaries
        )

        # 5. 前章结尾（完整结尾段落）
        prev_chapter = chapter_number - 1
        if prev_chapter in chapter_contents:
            content = chapter_contents[prev_chapter]
            ctx.previous_ending = self._extract_ending_full(content)
        elif prev_chapter in chapter_summaries:
            # 使用摘要中的 ending_state
            summary = chapter_summaries[prev_chapter]
            ctx.previous_ending = summary.get("ending_state", "")

        # ===== 步骤2：计算总token估算 =====
        ctx.total_tokens_estimate = self._estimate_tokens(ctx.to_prompt())

        logger.info(
            f"[ContextCompressor] 完整上下文构建完成，估算 ~{ctx.total_tokens_estimate} tokens"
        )

        # ===== 步骤3：动态压缩（仅在超阈值时启动） =====
        target_tokens = int(self.MAX_TOTAL_TOKENS * self.SAFETY_MARGIN)
        if ctx.total_tokens_estimate > target_tokens:
            logger.info(
                f"[ContextCompressor] 启动动态压缩，目标 ~{target_tokens} tokens"
            )
            ctx = self._adaptive_compress(ctx, target_tokens)
            ctx.total_tokens_estimate = self._estimate_tokens(ctx.to_prompt())
            logger.info(
                f"[ContextCompressor] 动态压缩完成，最终 ~{ctx.total_tokens_estimate} tokens"
            )

        return ctx

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数量.

        中文约1.5字符≈1token，英文约4字符≈1token。
        采用保守估算，取较大值。
        """
        # 简化估算：中文为主，取字符数/1.3（保守值）
        return int(len(text) / 1.3)

    def _adaptive_compress(
        self, ctx: CompressedContext, target_tokens: int
    ) -> CompressedContext:
        """按优先级逐步压缩，直到满足目标token数.

        压缩优先级（从低到高，优先压缩低优先级内容）：
        1. cold_memory - 卷级摘要，最早被压缩
        2. warm_memory - 关键事件列表
        3. hot_memory - 前章摘要细节
        4. previous_ending - 结尾（压缩幅度最小）
        5. core_memory - 核心记忆（极少情况才压缩）
        """
        compression_round = 0
        max_rounds = 10  # 最多10轮压缩，避免无限循环

        while ctx.total_tokens_estimate > target_tokens and compression_round < max_rounds:
            compression_round += 1
            current_tokens = ctx.total_tokens_estimate

            # 按优先级从低到高压缩
            # 第1优先：压缩cold_memory
            if ctx.cold_memory and len(ctx.cold_memory) > 100:
                ctx.cold_memory = self._truncate_by_ratio(ctx.cold_memory, 0.6)
                logger.debug(f"压缩cold_memory: {len(ctx.cold_memory)}字")

            # 第2优先：压缩warm_memory
            elif ctx.warm_memory and len(ctx.warm_memory) > 200:
                ctx.warm_memory = self._truncate_events(ctx.warm_memory, 0.7)
                logger.debug(f"压缩warm_memory: {len(ctx.warm_memory)}字")

            # 第3优先：压缩hot_memory细节
            elif ctx.hot_memory and len(ctx.hot_memory) > 500:
                ctx.hot_memory = self._simplify_summary(ctx.hot_memory, 0.8)
                logger.debug(f"压缩hot_memory: {len(ctx.hot_memory)}字")

            # 第4优先：压缩ending长度
            elif ctx.previous_ending and len(ctx.previous_ending) > 400:
                ctx.previous_ending = self._truncate_by_ratio(ctx.previous_ending, 0.7)
                logger.debug(f"压缩previous_ending: {len(ctx.previous_ending)}字")

            # 第5优先（最后）：压缩核心记忆（极端情况）
            elif ctx.core_memory and len(ctx.core_memory) > 800:
                ctx.core_memory = self._truncate_by_ratio(ctx.core_memory, 0.8)
                logger.debug(f"压缩core_memory: {len(ctx.core_memory)}字")

            # 如果所有内容都很短但仍超限，强制整体压缩
            else:
                # 按比例同时压缩所有内容
                if ctx.cold_memory:
                    ctx.cold_memory = self._truncate_by_ratio(ctx.cold_memory, 0.5)
                if ctx.warm_memory:
                    ctx.warm_memory = self._truncate_by_ratio(ctx.warm_memory, 0.5)
                if ctx.hot_memory:
                    ctx.hot_memory = self._truncate_by_ratio(ctx.hot_memory, 0.5)
                if ctx.previous_ending:
                    ctx.previous_ending = self._truncate_by_ratio(ctx.previous_ending, 0.5)
                logger.debug("强制整体压缩")

            # 更新token估算
            ctx.total_tokens_estimate = self._estimate_tokens(ctx.to_prompt())

            # 检查是否有效压缩
            if ctx.total_tokens_estimate >= current_tokens:
                logger.warning(
                    f"压缩效果不明显，第{compression_round}轮: "
                    f"{current_tokens} -> {ctx.total_tokens_estimate}"
                )
                break

        return ctx

    def _truncate_by_ratio(self, text: str, ratio: float) -> str:
        """按比例截取文本，优先保留完整句子."""
        target_len = int(len(text) * ratio)
        if target_len >= len(text):
            return text

        # 尝试在句子边界截取
        truncated = text[:target_len]
        last_period = truncated.rfind("。")
        if last_period > target_len * 0.7:  # 句号位置合理
            return truncated[:last_period + 1]
        return truncated.strip()

    def _truncate_events(self, events_text: str, ratio: float) -> str:
        """截取事件列表，保留重要事件."""
        lines = events_text.split("\n")
        target_count = int(len(lines) * ratio)
        if target_count >= len(lines):
            return events_text
        # 保留前N个事件（通常是最重要的）
        return "\n".join(lines[:target_count])

    def _simplify_summary(self, summary: str, ratio: float) -> str:
        """简化摘要，保留关键信息."""
        # 按比例截取，优先保留句子完整性
        return self._truncate_by_ratio(summary, ratio)

    def _extract_foreshadowing(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        chapter_contents: Dict[int, str],
    ) -> List[Dict[str, Any]]:
        """提取伏笔信息.

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
        """追踪角色发展轨迹.

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
        """提取关键事件.

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
        """识别未解决的冲突.

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

    def _build_core_memory_full(
        self,
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
        plot_outline: Any,
    ) -> str:
        """构建完整核心记忆：世界观 + 主要角色 + 主线（不截取）."""
        parts = []

        # 世界观完整描述
        if world_setting:
            world_brief = self._build_world_setting_full(world_setting)
            if world_brief:
                parts.append(f"世界观：{world_brief}")

        # 主要角色完整信息
        if characters:
            main_chars = self._build_characters_full(characters)
            if main_chars:
                parts.append(f"主要角色：{main_chars}")

        # 主线情节完整描述
        if plot_outline:
            main_plot = self._build_plot_outline_full(plot_outline)
            if main_plot:
                parts.append(f"主线：{main_plot}")

        return "\n".join(parts)

    def _build_world_setting_full(self, world_setting: Dict[str, Any]) -> str:
        """构建完整世界观描述."""
        parts = []

        world_type = world_setting.get("world_type", "")
        if world_type:
            parts.append(world_type)

        power_system = world_setting.get("power_system", {})
        if isinstance(power_system, dict):
            system_name = power_system.get("name", "")
            system_desc = power_system.get("description", "")
            if system_name:
                parts.append(f"力量体系:{system_name}" + (f" - {system_desc}" if system_desc else ""))
        elif isinstance(power_system, str):
            parts.append(f"力量体系:{power_system}")

        factions = world_setting.get("factions", [])
        if factions:
            faction_info = []
            for f in factions[:5]:  # 保留更多势力信息
                if isinstance(f, dict):
                    name = f.get("name", "")
                    desc = f.get("description", "")
                    faction_info.append(name + (f":{desc}" if desc else ""))
                else:
                    faction_info.append(str(f))
            parts.append(f"势力:{', '.join(faction_info)}")

        return "；".join(parts)

    def _build_characters_full(self, characters: List[Dict[str, Any]]) -> str:
        """构建完整角色信息."""
        main_chars = []

        for char in characters:
            role_type = char.get("role_type", "")
            name = char.get("name", "")

            # 保留主角和重要配角
            if role_type in ("protagonist", "主角", "supporting", "配角") or not role_type:
                # 完整角色信息
                char_parts = [name]
                personality = char.get("personality", "")
                if personality:
                    char_parts.append(f"性格:{personality}")
                background = char.get("background", "")
                if background:
                    char_parts.append(f"背景:{background}")
                # 正确格式：张三(性格:坚毅不拔, 背景:出身平凡)
                if len(char_parts) > 1:
                    main_chars.append(f"{char_parts[0]}({', '.join(char_parts[1:3])})")
                else:
                    main_chars.append(char_parts[0])

            if len(main_chars) >= 8:  # 增加到8个角色
                break

        return "、".join(main_chars)

    def _build_plot_outline_full(self, plot_outline: Any) -> str:
        """构建完整情节大纲."""
        if isinstance(plot_outline, str):
            return plot_outline

        if isinstance(plot_outline, list):
            parts = []
            for vol in plot_outline[:5]:  # 保留更多卷信息
                if isinstance(vol, dict):
                    title = vol.get("title", "")
                    summary = vol.get("summary", "")
                    parts.append(f"{title}:{summary}" if summary else title)
            return "；".join(parts)

        if isinstance(plot_outline, dict):
            main_plot = plot_outline.get("main_plot", "")
            if isinstance(main_plot, str):
                return main_plot
            if isinstance(main_plot, dict):
                return main_plot.get("summary", str(main_plot))

            volumes = plot_outline.get("volumes", [])
            if volumes:
                return self._build_plot_outline_full(volumes)

        return ""

    # 保留原方法名以兼容旧调用，但使用完整构建
    def _build_core_memory(
        self,
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
        plot_outline: Any,
    ) -> str:
        """构建核心记忆（兼容旧调用，内部使用完整构建）."""
        return self._build_core_memory_full(world_setting, characters, plot_outline)

    def _build_hot_memory_full(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> str:
        """构建热记忆：前N章完整摘要（不截取）."""
        hot_start = max(1, chapter_number - self.HOT_CHAPTERS)
        parts = []

        for ch in range(hot_start, chapter_number):
            if ch not in chapter_summaries:
                continue

            summary = chapter_summaries[ch]
            chapter_text = self._format_chapter_summary_full(ch, summary)
            parts.append(chapter_text)

        return "\n".join(parts)

    def _format_chapter_summary_full(
        self, chapter_number: int, summary: Dict[str, Any]
    ) -> str:
        """格式化单章完整摘要（不截取）."""
        parts = [f"第{chapter_number}章"]

        # 情节进展 - 完整内容
        plot_progress = summary.get("plot_progress", "")
        if plot_progress:
            parts.append(f"剧情: {plot_progress}")

        # 关键事件 - 完整列表
        key_events = summary.get("key_events", [])
        if key_events:
            events_text = "、".join(
                str(e) if isinstance(e, str) else e.get("event", e.get("description", str(e)))
                for e in key_events
            )
            parts.append(f"事件: {events_text}")

        # 角色变化 - 完整内容
        char_changes = summary.get("character_changes", "")
        if char_changes:
            parts.append(f"角色: {char_changes}")

        # 结尾状态
        ending_state = summary.get("ending_state", "")
        if ending_state:
            parts.append(f"结尾: {ending_state}")

        return " | ".join(parts)

    # 保留原方法名以兼容旧调用
    def _build_hot_memory(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> str:
        """构建热记忆（兼容旧调用，内部使用完整构建）."""
        return self._build_hot_memory_full(chapter_number, chapter_summaries)

    def _format_chapter_summary(
        self, chapter_number: int, summary: Dict[str, Any]
    ) -> str:
        """格式化单章摘要（兼容旧调用，内部使用完整格式）."""
        return self._format_chapter_summary_full(chapter_number, summary)

    def _build_warm_memory_full(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> str:
        """构建温记忆：前章节关键事件完整描述."""
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

            # 保留所有关键事件的完整描述
            for event in key_events:
                if isinstance(event, str):
                    events.append(f"第{ch}章: {event}")
                elif isinstance(event, dict):
                    event_desc = event.get("event", event.get("description", str(event)))
                    events.append(f"第{ch}章: {event_desc}")

        if not events:
            return ""

        return "\n".join(events)

    # 保留原方法名以兼容旧调用
    def _build_warm_memory(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
    ) -> str:
        """构建温记忆（兼容旧调用）."""
        return self._build_warm_memory_full(chapter_number, chapter_summaries)

    def _build_cold_memory_full(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        volume_summaries: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> str:
        """构建冷记忆：更早章节的卷级摘要（完整内容）.

        Args:
            chapter_number: 当前章节号
            chapter_summaries: 章节摘要字典
            volume_summaries: 卷摘要字典，格式：
                {卷号: {"summary": 摘要, "chapters": [start, end]}}
        """
        # 冷记忆起始点：跳过热+温记忆覆盖的章节
        cold_end = max(1, chapter_number - self.HOT_CHAPTERS - self.WARM_CHAPTERS)

        if cold_end <= 1:
            return ""

        # 如果有预计算的卷摘要，直接使用完整摘要
        if volume_summaries:
            parts = []
            for vol_num, vol_data in sorted(volume_summaries.items()):
                vol_summary = vol_data.get("summary", "") if isinstance(vol_data, dict) else str(vol_data)
                vol_chapters = vol_data.get("chapters", []) if isinstance(vol_data, dict) else []

                # 使用实际定义的章节范围判断卷是否在冷记忆范围内
                if vol_chapters and len(vol_chapters) >= 2:
                    vol_start = vol_chapters[0]
                else:
                    # fallback: 使用硬编码计算
                    vol_start = (vol_num - 1) * self.CHAPTERS_PER_VOLUME + 1

                if vol_start < cold_end:
                    # 完整摘要，不截取
                    parts.append(f"第{vol_num}卷: {vol_summary}")
            if parts:
                logger.info(
                    f"[ColdMemory] 使用卷摘要构建冷记忆，共 {len(parts)} 卷"
                )
            return "\n".join(parts)

        # 否则，按卷聚合章节摘要（完整内容）
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
                # 完整情节摘要，不截取
                volumes[vol_num].append(plot_progress)

        # 合并为卷摘要
        parts = []
        for vol_num, summaries in sorted(volumes.items()):
            combined = "；".join(summaries)
            # 完整合并，不截取
            parts.append(f"第{vol_num}卷: {combined}")

        return "\n".join(parts)

    # 保留原方法名以兼容旧调用
    def _build_cold_memory(
        self,
        chapter_number: int,
        chapter_summaries: Dict[int, Dict[str, Any]],
        volume_summaries: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> str:
        """构建冷记忆（兼容旧调用）."""
        return self._build_cold_memory_full(chapter_number, chapter_summaries, volume_summaries)

    def _extract_ending_full(self, content: str) -> str:
        """提取章节完整结尾段落."""
        if not content:
            return ""

        # 取更大的结尾段落
        ending = content[-self.PREVIOUS_ENDING_LENGTH :]

        # 尝试从句子开头开始
        first_period = ending.find("。")
        if 0 < first_period < 150:
            ending = ending[first_period + 1 :]

        return ending.strip()

    def _extract_ending(self, content: str) -> str:
        """提取章节结尾（兼容旧调用）."""
        return self._extract_ending_full(content)

    # 移除旧的固定截取压缩方法，保留为兼容别名
    def _compress_world_setting(self, world_setting: Dict[str, Any]) -> str:
        """压缩世界观设定（兼容旧调用）."""
        return self._build_world_setting_full(world_setting)

    def _compress_characters(self, characters: List[Dict[str, Any]]) -> str:
        """压缩角色信息（兼容旧调用）."""
        return self._build_characters_full(characters)

    def _compress_plot_outline(self, plot_outline: Any) -> str:
        """压缩情节大纲（兼容旧调用）."""
        return self._build_plot_outline_full(plot_outline)


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
