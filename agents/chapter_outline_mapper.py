"""
ChapterOutlineMapper - 章节大纲映射器.

功能：
1. 将卷级大纲分解为章节级任务
2. 为每章分配"必须完成的大纲事件"
3. 追踪大纲完成进度

解决根本原因 4：情节规划缺乏章节级粒度
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class TensionCycle:
    """张力循环（欲扬先抑）."""

    cycle_number: int
    start_chapter: int
    end_chapter: int
    suppress_chapters: List[int]  # 压制期章节
    release_chapter: int  # 释放期章节

    suppression_events: List[str] = field(default_factory=list)
    release_events: List[str] = field(default_factory=list)

    def position(self, chapter_number: int) -> str:
        """判断章节在循环中的位置."""
        if chapter_number in self.suppress_chapters:
            return "suppress"
        elif chapter_number == self.release_chapter:
            return "release"
        else:
            return "transition"

    def progress(self, chapter_number: int) -> float:
        """计算循环进度 (0-1)."""
        if chapter_number < self.start_chapter:
            return 0.0
        elif chapter_number > self.end_chapter:
            return 1.0
        else:
            total = self.end_chapter - self.start_chapter + 1
            current = chapter_number - self.start_chapter
            return min(1.0, current / total)


@dataclass
class ChapterOutlineTask:
    """章节级大纲任务."""

    chapter_number: int
    volume_number: int

    # 强制性事件（必须完成）
    mandatory_events: List[str] = field(default_factory=list)

    # 可选事件（建议完成）
    optional_events: List[str] = field(default_factory=list)

    # 伏笔任务
    foreshadowing_to_plant: List[str] = field(default_factory=list)
    foreshadowing_to_payoff: List[str] = field(default_factory=list)

    # 角色任务
    character_development: Dict[str, str] = field(default_factory=dict)

    # 情感基调
    emotional_tone: str = ""

    # 大纲任务描述
    task_description: str = ""

    # 元数据
    is_milestone: bool = False
    is_climax: bool = False
    is_golden_chapter: bool = False  # 黄金三章

    def to_prompt(self) -> str:
        """转换为提示词格式."""
        parts = [
            f"## 第{self.chapter_number}章 大纲任务（第{self.volume_number}卷）",
        ]

        # 强制性事件
        if self.mandatory_events:
            parts.append("**必须完成的事件**:")
            for event in self.mandatory_events:
                parts.append(f"- ⚠️ {event}")

        # 可选事件
        if self.optional_events:
            parts.append("**建议事件**:")
            for event in self.optional_events:
                parts.append(f"- {event}")

        # 伏笔任务
        if self.foreshadowing_to_plant:
            parts.append("**需要埋设的伏笔**:")
            for fb in self.foreshadowing_to_plant:
                parts.append(f"- 🌱 {fb}")

        if self.foreshadowing_to_payoff:
            parts.append("**需要回收的伏笔**:")
            for fb in self.foreshadowing_to_payoff:
                parts.append(f"- ✅ {fb}")

        # 角色发展
        if self.character_development:
            parts.append("**角色发展**:")
            for char, dev in self.character_development.items():
                parts.append(f"- {char}: {dev}")

        # 情感基调
        if self.emotional_tone:
            parts.append(f"**情感基调**: {self.emotional_tone}")

        # 特殊标记
        if self.is_golden_chapter:
            parts.append("**⚡ 黄金三章：必须吸引读者**")
        if self.is_milestone:
            parts.append("**🎯 里程碑章节：重大转折点**")
        if self.is_climax:
            parts.append("**🔥 高潮章节：全卷最高点**")

        return "\n".join(parts)

    def is_complete(self, chapter_plan: Dict[str, Any]) -> bool:
        """检查章节计划是否完成了大纲任务."""
        # 简单检查：是否包含所有强制性事件的关键词
        chapter_text = json.dumps(chapter_plan, ensure_ascii=False)

        for event in self.mandatory_events:
            # 简化：检查事件关键词是否出现
            keywords = event.split()[:3]  # 取前 3 个词作为关键词
            if not any(kw in chapter_text for kw in keywords if len(kw) > 1):
                return False

        return True


@dataclass
class OutlineValidationReport:
    """大纲验证报告."""

    chapter_number: int
    passed: bool = False

    # 完成情况
    completed_events: List[str] = field(default_factory=list)
    missing_events: List[str] = field(default_factory=list)

    # 伏笔检查
    planted_foreshadowings: List[str] = field(default_factory=list)
    missing_foreshadowings: List[str] = field(default_factory=list)

    # 评分
    completion_rate: float = 0.0
    quality_score: float = 0.0

    # 建议
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "chapter_number": self.chapter_number,
            "passed": self.passed,
            "completion": {
                "completed_events": self.completed_events,
                "missing_events": self.missing_events,
            },
            "foreshadowing": {
                "planted": self.planted_foreshadowings,
                "missing": self.missing_foreshadowings,
            },
            "scores": {
                "completion_rate": self.completion_rate,
                "quality_score": self.quality_score,
            },
            "suggestions": self.suggestions,
        }


class ChapterOutlineMapper:
    """
    章节大纲映射器.

    核心算法：
    1. 解析卷级大纲的张力循环
    2. 将关键事件分配到具体章节
    3. 为每章生成强制性任务列表
    """

    def __init__(self, novel_id: str):
        """初始化方法."""
        self.novel_id = novel_id
        self.volume_outlines: Dict[int, Dict[str, Any]] = {}
        self.tension_cycles: Dict[int, List[TensionCycle]] = {}
        self.chapter_tasks: Dict[int, ChapterOutlineTask] = {}
        logger.info(f"ChapterOutlineMapper initialized for novel {novel_id}")

    def load_volume_outline(
        self,
        volume_number: int,
        volume_outline: Dict[str, Any],
        total_chapters_in_volume: int,
        chapter_config: Optional[Dict[str, Any]] = None,
    ):
        """
        加载卷大纲并解析张力循环.

        Args:
            volume_number: 卷号
            volume_outline: 卷大纲数据
            total_chapters_in_volume: 卷总章节数
            chapter_config: 章节配置（可选）
                {
                    "total_chapters": 总章节数，
                    "min_chapters": 最小章节数，
                    "max_chapters": 最大章节数，
                    "flexible": 是否允许灵活调整
                }
        """
        logger.info(
            f"Loading volume {volume_number} outline with {total_chapters_in_volume} chapters"
        )

        self.volume_outlines[volume_number] = volume_outline

        # 存储章节配置
        if chapter_config:
            self.volume_outlines[volume_number]["chapter_config"] = chapter_config

        # 解析张力循环
        self.tension_cycles[volume_number] = self._parse_tension_cycles(
            volume_outline, total_chapters_in_volume, chapter_config
        )

        logger.info(
            f"Volume {volume_number} loaded with "
            f"{len(self.tension_cycles[volume_number])} tension cycles"
        )

    def decompose_outline_to_chapters(
        self,
        volume_number: int,
        foreshadowings: Optional[List[Dict[str, Any]]] = None,
        character_states: Optional[Dict[str, Any]] = None,
    ) -> List[ChapterOutlineTask]:
        """
        将卷大纲分解为章节级任务列表.

        支持自动章节拆分和主线细化

        Args:
            volume_number: 卷号
            foreshadowings: 伏笔列表（用于分配伏笔任务）
            character_states: 角色状态（用于分配角色发展任务）

        Returns:
            章节任务列表
        """
        logger.info(f"Decomposing volume {volume_number} outline to chapters")

        volume_outline = self.volume_outlines.get(volume_number)
        if not volume_outline:
            logger.warning(f"Volume {volume_number} outline not found")
            return []

        # 获取章节配置
        chapter_config = volume_outline.get("chapter_config", {})
        total_chapters = chapter_config.get("total_chapters", 0)

        if total_chapters == 0:
            # 从张力循环推断章节数
            cycles = self.tension_cycles.get(volume_number, [])
            if cycles:
                total_chapters = max(c.end_chapter for c in cycles)
            else:
                logger.warning(
                    f"Cannot determine total chapters for volume {volume_number}"
                )
                return []

        chapter_tasks = []

        # 为每章生成任务
        for ch_num in range(1, total_chapters + 1):
            task = self.map_outline_to_chapter(
                volume_number=volume_number,
                chapter_number=ch_num,
                foreshadowings=foreshadowings,
            )

            # 添加角色发展任务
            if character_states:
                self._add_character_development_tasks(task, ch_num, character_states)

            chapter_tasks.append(task)

        logger.info(
            f"Volume {volume_number} decomposed into {len(chapter_tasks)} chapter tasks"
        )

        return chapter_tasks

    def _add_character_development_tasks(
        self,
        task: ChapterOutlineTask,
        chapter_number: int,
        character_states: Dict[str, Any],
    ):
        """添加角色发展任务."""
        for char_name, state in character_states.items():
            # 检查角色是否在当前章节有发展需求
            pending_events = state.get("pending_events", [])
            state.get("current_location", "")
            emotional_state = state.get("emotional_state", "")

            # 如果有待处理事件，添加到章节任务
            if pending_events:
                for event in pending_events[:2]:
                    task.character_development[char_name] = f"处理：{event}"

            # 根据情感状态添加发展任务
            if emotional_state and chapter_number % 5 == 0:
                task.character_development[char_name] = f"情感发展：{emotional_state}"

    def _parse_tension_cycles(
        self,
        volume_outline: Dict[str, Any],
        total_chapters: int,
        chapter_config: Optional[Dict[str, Any]] = None,
    ) -> List[TensionCycle]:
        """
        从卷大纲中解析张力循环.

        期望的卷大纲结构：
        {
            "tension_cycles": [
                {
                    "suppress_events": [...],
                    "release_event": "...",
                    "chapters": [start, end]
                }
            ]
        }

        Args:
            volume_outline: 卷大纲
            total_chapters: 卷总章节数
            chapter_config: 章节配置（可选）

        Returns:
            张力循环列表
        """
        cycles = []

        tension_cycles_data = volume_outline.get("tension_cycles", [])

        if not tension_cycles_data:
            # 如果没有明确定义，自动创建默认循环
            logger.info("No tension cycles defined, creating default cycles")
            return self._create_default_tension_cycles(total_chapters, chapter_config)

        # 检查章节配置
        flexible = chapter_config.get("flexible", True) if chapter_config else True
        max_chapters = (
            chapter_config.get("max_chapters", total_chapters * 1.5)
            if chapter_config
            else total_chapters * 1.5
        )

        for i, cycle_data in enumerate(tension_cycles_data):
            chapters_range = cycle_data.get("chapters", [])
            if len(chapters_range) != 2:
                continue

            start_ch, end_ch = chapters_range

            # 如果章节范围超过配置，进行调整
            if end_ch > max_chapters and flexible:
                logger.warning(
                    f"Tension cycle {i+1} exceeds max chapters ({end_ch} > {max_chapters}), adjusting"
                )
                scale_factor = max_chapters / end_ch
                start_ch = int(start_ch * scale_factor)
                end_ch = int(end_ch * scale_factor)

            # 计算压制期和释放期
            # 默认：前 70% 为压制期，最后 30% 为释放期
            suppress_end = int(start_ch + (end_ch - start_ch) * 0.7)
            release_ch = end_ch

            suppress_chapters = list(range(start_ch, suppress_end + 1))

            # 兼容两种格式：release_event（单数字符串）和 release_events（复数列表）
            release_event = cycle_data.get("release_event")
            release_events_raw = cycle_data.get("release_events")

            if isinstance(release_event, str) and release_event:
                release_events_list = [release_event]
            elif isinstance(release_events_raw, list):
                release_events_list = release_events_raw
            elif isinstance(release_event, list):
                # 防止 release_event 意外是列表
                release_events_list = release_event
            else:
                release_events_list = []

            cycle = TensionCycle(
                cycle_number=i + 1,
                start_chapter=start_ch,
                end_chapter=end_ch,
                suppress_chapters=suppress_chapters,
                release_chapter=release_ch,
                suppression_events=cycle_data.get("suppress_events", []),
                release_events=release_events_list,
            )

            cycles.append(cycle)

        return cycles

    def _create_default_tension_cycles(
        self, total_chapters: int, chapter_config: Optional[Dict[str, Any]] = None
    ) -> List[TensionCycle]:
        """
        创建默认张力循环.

        Args:
            total_chapters: 卷总章节数
            chapter_config: 章节配置（可选）

        Returns:
            张力循环列表
        """
        cycles = []

        # 检查章节配置
        min_chapters = chapter_config.get("min_chapters", 3) if chapter_config else 3
        max_chapters = chapter_config.get("max_chapters", 12) if chapter_config else 12

        # 根据章节数动态调整循环大小
        # 章节数少则循环小，章节数多则循环大
        if total_chapters <= min_chapters:
            cycle_size = 3  # 小循环
        elif total_chapters >= max_chapters:
            cycle_size = 8  # 大循环
        else:
            # 中等章节数，按比例计算
            cycle_size = max(3, min(8, total_chapters // 2))

        num_cycles = (total_chapters + cycle_size - 1) // cycle_size

        for i in range(num_cycles):
            start_ch = i * cycle_size + 1
            end_ch = min((i + 1) * cycle_size, total_chapters)

            suppress_end = int(start_ch + (end_ch - start_ch) * 0.6)
            suppress_chapters = list(range(start_ch, suppress_end + 1))

            cycle = TensionCycle(
                cycle_number=i + 1,
                start_chapter=start_ch,
                end_chapter=end_ch,
                suppress_chapters=suppress_chapters,
                release_chapter=end_ch,
                suppression_events=[f"第{start_ch}章的挫折"],
                release_events=[f"第{end_ch}章的胜利"],
            )

            cycles.append(cycle)

        return cycles

    def map_outline_to_chapter(
        self,
        volume_number: int,
        chapter_number: int,
        foreshadowings: Optional[List[Dict[str, Any]]] = None,
    ) -> ChapterOutlineTask:
        """
        为指定章节分配大纲任务.

        Args:
            volume_number: 卷号
            chapter_number: 章节号
            foreshadowings: 伏笔列表（用于分配伏笔任务）

        Returns:
            ChapterOutlineTask
        """
        logger.info(
            f"Mapping outline to chapter {chapter_number} (volume {volume_number})"
        )

        # 1. 获取卷大纲
        volume_outline = self.volume_outlines.get(volume_number)
        if not volume_outline:
            logger.warning(f"Volume {volume_number} outline not found")
            return self._create_empty_task(chapter_number, volume_number)

        # 2. 找到当前章所属的张力循环
        current_cycle = self._find_current_cycle(volume_number, chapter_number)

        # 3. 创建任务
        task = ChapterOutlineTask(
            chapter_number=chapter_number, volume_number=volume_number
        )

        # 4. 根据循环位置分配事件
        if current_cycle:
            position = current_cycle.position(chapter_number)
            cycle_progress = current_cycle.progress(chapter_number)

            if position == "suppress":
                task.mandatory_events = current_cycle.suppression_events[:2]
                task.emotional_tone = "压抑、挫折、积累"
            elif position == "release":
                task.mandatory_events = current_cycle.release_events
                task.emotional_tone = "爽快、胜利、爆发"
                task.is_milestone = True
            else:
                task.mandatory_events = current_cycle.suppression_events[-1:]
                task.optional_events = current_cycle.release_events[:1]
                task.emotional_tone = "过渡、铺垫"

            # 将张力循环进度信息添加到任务描述，而非强制事件列表
            task.task_description += f"\n当前处于张力循环 #{current_cycle.cycle_number}，进度 {cycle_progress:.0%}。"

        # 5. 添加卷的关键事件
        key_events = volume_outline.get("key_events", [])
        for event_data in key_events:
            if isinstance(event_data, dict):
                event_chapter = event_data.get("chapter", 0)
                if event_chapter == chapter_number:
                    task.mandatory_events.append(event_data.get("event", ""))
                    task.is_milestone = True
                    # 新增：添加事件影响说明
                    if "impact" in event_data:
                        task.optional_events.append(f"影响：{event_data['impact']}")
            elif isinstance(event_data, str):
                # 字符串格式，无法确定章节，跳过
                pass

        # 6. 添加伏笔任务
        if foreshadowings:
            self._add_foreshadowing_tasks(task, chapter_number, foreshadowings)

        # 7. 检查是否是黄金三章
        if chapter_number <= 3:
            task.is_golden_chapter = True
            task.emotional_tone = "吸引读者、建立期待"

        # 8. 检查是否是高潮章
        climax_chapter = volume_outline.get("climax_chapter")
        if climax_chapter == chapter_number:
            task.is_climax = True
            task.emotional_tone = "高潮、最大冲突"

        # 9. 生成任务描述
        task.task_description = self._generate_task_description(task, volume_outline)

        # 10. 新增：添加主线细化信息
        main_plot_thread = self._extract_main_plot_thread(
            volume_outline, chapter_number
        )
        if main_plot_thread:
            task.optional_events.append(f"主线推进：{main_plot_thread}")

        # 缓存任务
        self.chapter_tasks[chapter_number] = task

        logger.info(
            f"Chapter {chapter_number} task created: "
            f"{len(task.mandatory_events)} mandatory events, "
            f"{len(task.optional_events)} optional events"
        )

        return task

    def _extract_main_plot_thread(
        self, volume_outline: Dict[str, Any], chapter_number: int
    ) -> str:
        """
        提取主线剧情线索.

        从卷大纲中提取当前章节应推进的主线剧情

        Args:
            volume_outline: 卷大纲
            chapter_number: 章节号

        Returns:
            主线剧情线索描述
        """
        # 检查是否有主线剧情定义
        main_plot = volume_outline.get("main_plot", {})
        if not main_plot:
            return ""

        # 根据章节位置判断主线阶段
        chapter_config = volume_outline.get("chapter_config", {})
        total_chapters = chapter_config.get("total_chapters", 0)

        if total_chapters == 0:
            cycles = self.tension_cycles.get(volume_outline.get("number", 1), [])
            if cycles:
                total_chapters = max(c.end_chapter for c in cycles)

        if total_chapters == 0:
            return ""

        progress = chapter_number / total_chapters

        # 根据进度返回不同的主线阶段
        if progress < 0.2:
            return main_plot.get("setup", "故事开端")
        elif progress < 0.5:
            return main_plot.get("conflict", "冲突发展")
        elif progress < 0.8:
            return main_plot.get("climax", "高潮铺垫")
        else:
            return main_plot.get("resolution", "结局收尾")

    def _find_current_cycle(
        self, volume_number: int, chapter_number: int
    ) -> Optional[TensionCycle]:
        """找到当前章所属的张力循环."""
        cycles = self.tension_cycles.get(volume_number, [])

        for cycle in cycles:
            if cycle.start_chapter <= chapter_number <= cycle.end_chapter:
                return cycle

        return None

    def _add_foreshadowing_tasks(
        self,
        task: ChapterOutlineTask,
        chapter_number: int,
        foreshadowings: List[Dict[str, Any]],
    ):
        """
        添加伏笔任务.

        增强功能：
        1. 智能伏笔分配：根据张力循环位置分配伏笔
        2. 伏笔优先级：高优先级伏笔优先分配
        3. 伏笔回收提醒：提前 1-2 章提醒即将回收的伏笔
        """
        # 1. 获取当前张力循环位置
        current_cycle = None
        for cycle in self.tension_cycles.get(task.volume_number, []):
            if cycle.start_chapter <= chapter_number <= cycle.end_chapter:
                current_cycle = cycle
                break

        cycle_position = (
            current_cycle.position(chapter_number) if current_cycle else None
        )

        # 2. 分类伏笔
        pending_foreshadowings = [
            fb for fb in foreshadowings if fb.get("status") == "pending"
        ]

        # 按优先级排序
        pending_foreshadowings.sort(key=lambda x: x.get("importance", 5), reverse=True)

        for foreshadow in pending_foreshadowings:
            planted_chapter = foreshadow.get("planted_chapter", 0)
            expected_resolve = foreshadow.get("expected_resolve_chapter", 0)
            importance = foreshadow.get("importance", 5)
            content = foreshadow.get("content", "")

            # 检查是否需要回收
            if expected_resolve == chapter_number:
                task.foreshadowing_to_payoff.append(
                    f"[第{planted_chapter}章] {content}"
                )
            # 检查是否超期
            elif chapter_number - planted_chapter >= 5 and importance >= 7:
                task.foreshadowing_to_payoff.append(f"[超期] {content}")
            # 提前提醒：距离回收还有 1-2 章
            elif expected_resolve > 0 and 0 < expected_resolve - chapter_number <= 2:
                task.foreshadowing_to_plant.append(
                    f"[即将回收] {content} (第{expected_resolve}章回收)"
                )

            # 3. 根据张力循环位置智能分配伏笔埋设
            # 压制期适合埋设伏笔，释放期适合回收伏笔
            if cycle_position == "suppress" and planted_chapter == 0:
                # 压制期是埋设伏笔的好时机
                if importance >= 6:  # 中高优先级伏笔
                    task.foreshadowing_to_plant.append(
                        f"[建议埋设] {content} (重要性：{importance})"
                    )

    def analyze_tension_cycle_distribution(self, volume_number: int) -> Dict[str, Any]:
        """
        分析张力循环分布.

        提供张力循环的详细分析，包括：
        - 各循环的章节分布
        - 压制期与释放期比例
        - 事件密度分析

        Args:
            volume_number: 卷号

        Returns:
            张力循环分析报告
        """
        cycles = self.tension_cycles.get(volume_number, [])

        if not cycles:
            return {
                "error": "未找到张力循环",
                "volume_number": volume_number,
            }

        total_chapters = max(c.end_chapter for c in cycles)

        analysis = {
            "volume_number": volume_number,
            "total_chapters": total_chapters,
            "total_cycles": len(cycles),
            "cycles": [],
            "overall_rhythm": "",
        }

        total_suppress = 0
        total_release = 0

        for cycle in cycles:
            suppress_count = len(cycle.suppress_chapters)
            release_count = 1  # 释放期通常 1 章

            total_suppress += suppress_count
            total_release += release_count

            cycle_analysis = {
                "cycle_number": cycle.cycle_number,
                "chapter_range": [cycle.start_chapter, cycle.end_chapter],
                "suppress_chapters": suppress_count,
                "release_chapter": cycle.release_chapter,
                "suppress_events_count": len(cycle.suppression_events),
                "release_events_count": len(cycle.release_events),
                "rhythm": f"{suppress_count}:1",
            }

            analysis["cycles"].append(cycle_analysis)

        # 计算整体节奏
        if total_suppress > 0:
            ratio = total_suppress / total_release
            if ratio < 3:
                analysis["overall_rhythm"] = "快节奏（频繁释放）"
            elif ratio < 6:
                analysis["overall_rhythm"] = "中等节奏（平衡）"
            else:
                analysis["overall_rhythm"] = "慢节奏（长期压抑）"

        analysis["suppress_release_ratio"] = f"{total_suppress}:{total_release}"

        return analysis

    def distribute_foreshadowings_across_chapters(
        self,
        volume_number: int,
        foreshadowings: List[Dict[str, Any]],
        total_chapters: int,
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        在章节间智能分配伏笔.

        根据张力循环和伏笔重要性，自动分配伏笔到最佳章节

        Args:
            volume_number: 卷号
            foreshadowings: 伏笔列表
            total_chapters: 总章节数

        Returns:
            章节到伏笔列表的映射 {chapter_number: [foreshadowings]}
        """
        distribution = {i: [] for i in range(1, total_chapters + 1)}

        # 1. 分类伏笔
        high_priority = [
            fb
            for fb in foreshadowings
            if fb.get("importance", 5) >= 7 and fb.get("status") == "pending"
        ]
        medium_priority = [
            fb
            for fb in foreshadowings
            if 4 <= fb.get("importance", 5) < 7 and fb.get("status") == "pending"
        ]
        low_priority = [
            fb
            for fb in foreshadowings
            if fb.get("importance", 5) < 4 and fb.get("status") == "pending"
        ]

        # 2. 获取张力循环
        cycles = self.tension_cycles.get(volume_number, [])

        if not cycles:
            # 没有张力循环，均匀分配
            for i, fb in enumerate(foreshadowings):
                ch_num = (i % total_chapters) + 1
                distribution[ch_num].append(fb)
            return distribution

        # 3. 根据张力循环分配伏笔
        # 高优先级伏笔：分配到前 30% 的压制期
        # 中优先级伏笔：分配到中间 50%
        # 低优先级伏笔：分配到后 20%

        for cycle in cycles:
            suppress_chapters = cycle.suppress_chapters
            if not suppress_chapters:
                continue

            # 计算压制期的分段
            early_suppress = suppress_chapters[: len(suppress_chapters) // 3]
            mid_suppress = suppress_chapters[
                len(suppress_chapters) // 3 : 2 * len(suppress_chapters) // 3
            ]
            late_suppress = suppress_chapters[2 * len(suppress_chapters) // 3 :]

            # 分配高优先级伏笔到早期压制期
            for idx, fb in enumerate(high_priority[: len(early_suppress)]):
                if early_suppress:
                    ch_num = early_suppress[idx % len(early_suppress)]
                    distribution[ch_num].append(
                        {**fb, "distribution_reason": "高优先级伏笔，早期压制期埋设"}
                    )

            # 分配中优先级伏笔到中期压制期
            for idx, fb in enumerate(medium_priority[: len(mid_suppress)]):
                if mid_suppress:
                    ch_num = mid_suppress[idx % len(mid_suppress)]
                    distribution[ch_num].append(
                        {**fb, "distribution_reason": "中优先级伏笔，中期压制期埋设"}
                    )

            # 分配低优先级伏笔到后期压制期
            for idx, fb in enumerate(low_priority[: len(late_suppress)]):
                if late_suppress:
                    ch_num = late_suppress[idx % len(late_suppress)]
                    distribution[ch_num].append(
                        {**fb, "distribution_reason": "低优先级伏笔，后期压制期埋设"}
                    )

        # 4. 移除空章节
        distribution = {k: v for k, v in distribution.items() if v}

        return distribution

    def _generate_task_description(
        self, task: ChapterOutlineTask, volume_outline: Dict[str, Any]
    ) -> str:
        """生成任务描述."""
        parts = []

        if task.is_golden_chapter:
            parts.append("这是黄金三章之一，必须吸引读者继续阅读。")

        if task.is_climax:
            parts.append("这是本卷的高潮章节，需要营造最大的冲突和张力。")

        if task.mandatory_events:
            parts.append(f"本章必须完成{len(task.mandatory_events)}个关键事件。")

        if task.foreshadowing_to_payoff:
            parts.append(f"本章需要回收{len(task.foreshadowing_to_payoff)}个伏笔。")

        return " ".join(parts)

    def _create_empty_task(
        self, chapter_number: int, volume_number: int
    ) -> ChapterOutlineTask:
        """创建空任务（当找不到大纲时）."""
        return ChapterOutlineTask(
            chapter_number=chapter_number,
            volume_number=volume_number,
            mandatory_events=["推进剧情发展"],
            optional_events=[],
            emotional_tone="根据情节需要",
        )

    def validate_chapter_against_outline(
        self, chapter_plan: Dict[str, Any], chapter_number: int
    ) -> OutlineValidationReport:
        """
        验证章节计划是否完成了大纲任务.

        Args:
            chapter_plan: 章节计划
            chapter_number: 章节号

        Returns:
            OutlineValidationReport
        """
        logger.info(f"Validating chapter {chapter_number} against outline")

        report = OutlineValidationReport(chapter_number=chapter_number)

        # 获取任务
        task = self.chapter_tasks.get(chapter_number)
        if not task:
            report.suggestions.append("未找到大纲任务，无法验证")
            return report

        # 检查强制性事件完成情况
        chapter_text = json.dumps(chapter_plan, ensure_ascii=False).lower()

        for event in task.mandatory_events:
            event_lower = event.lower()
            # 简化检查：关键词匹配
            keywords = [w for w in event_lower.split() if len(w) > 1][:3]

            if any(kw in chapter_text for kw in keywords):
                report.completed_events.append(event)
            else:
                report.missing_events.append(event)

        # 检查伏笔任务
        foreshadowings_planned = chapter_plan.get("foreshadowing_payoffs", [])

        for fb_task in task.foreshadowing_to_payoff:
            if any(fb_task.lower() in fb.lower() for fb in foreshadowings_planned):
                report.planted_foreshadowings.append(fb_task)
            else:
                report.missing_foreshadowings.append(fb_task)

        # 计算完成率
        total_mandatory = len(task.mandatory_events)
        completed = len(report.completed_events)

        report.completion_rate = (
            completed / total_mandatory if total_mandatory > 0 else 0
        )

        # 质量评分
        report.quality_score = report.completion_rate * 10

        # 调整：如果缺失高优先级伏笔，扣分
        if report.missing_foreshadowings:
            report.quality_score -= len(report.missing_foreshadowings) * 0.5

        # 判断是否通过
        report.passed = report.completion_rate >= 0.8 and report.quality_score >= 7.0

        # 生成建议
        if not report.passed:
            if report.missing_events:
                report.suggestions.append(
                    f"建议补充以下事件：{', '.join(report.missing_events)}"
                )
            if report.missing_foreshadowings:
                report.suggestions.append(
                    f"建议回收伏笔：{', '.join(report.missing_foreshadowings)}"
                )

        logger.info(
            f"Validation completed: completion_rate={report.completion_rate:.1f}, "
            f"passed={report.passed}"
        )

        return report

    def get_outline_progress(
        self, volume_number: int, current_chapter: int
    ) -> Dict[str, Any]:
        """获取大纲进度."""
        self.tension_cycles.get(volume_number, [])

        completed_tasks = sum(
            1 for ch, task in self.chapter_tasks.items() if ch <= current_chapter
        )

        total_events = sum(
            len(task.mandatory_events)
            for task in self.chapter_tasks.values()
            if task.chapter_number <= current_chapter
        )

        return {
            "volume_number": volume_number,
            "current_chapter": current_chapter,
            "completed_chapters": completed_tasks,
            "total_events_assigned": total_events,
            "current_cycle": (
                self._find_current_cycle(volume_number, current_chapter).cycle_number
                if self._find_current_cycle(volume_number, current_chapter)
                else 0
            ),
            "cycle_progress": (
                self._find_current_cycle(volume_number, current_chapter).progress(
                    current_chapter
                )
                if self._find_current_cycle(volume_number, current_chapter)
                else 0
            ),
        }


# 便捷函数
def create_outline_mapper(novel_id: str) -> ChapterOutlineMapper:
    """便捷函数：创建大纲映射器."""
    return ChapterOutlineMapper(novel_id)


def map_chapter_outline_task(
    novel_id: str,
    volume_outline: Dict[str, Any],
    chapter_number: int,
    volume_number: int,
    total_chapters: int,
    chapter_config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> ChapterOutlineTask:
    """
    便捷函数：为章节分配大纲任务.

    Args:
        novel_id: 小说 ID
        volume_outline: 卷大纲
        chapter_number: 章节号
        volume_number: 卷号
        total_chapters: 卷总章节数
        chapter_config: 章节配置（可选）
        **kwargs: 其他参数（如 foreshadowings）

    Returns:
        ChapterOutlineTask
    """
    mapper = ChapterOutlineMapper(novel_id)
    mapper.load_volume_outline(
        volume_number, volume_outline, total_chapters, chapter_config
    )
    return mapper.map_outline_to_chapter(
        volume_number=volume_number,
        chapter_number=chapter_number,
        foreshadowings=kwargs.get("foreshadowings"),
    )


def decompose_volume_outline(
    novel_id: str,
    volume_outline: Dict[str, Any],
    volume_number: int,
    total_chapters: int,
    chapter_config: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> List[ChapterOutlineTask]:
    """
    便捷函数：将卷大纲分解为章节任务.

    Args:
        novel_id: 小说 ID
        volume_outline: 卷大纲
        volume_number: 卷号
        total_chapters: 卷总章节数
        chapter_config: 章节配置（可选）
        **kwargs: 其他参数（如 foreshadowings, character_states）

    Returns:
        ChapterOutlineTask 列表
    """
    mapper = ChapterOutlineMapper(novel_id)
    mapper.load_volume_outline(
        volume_number, volume_outline, total_chapters, chapter_config
    )
    return mapper.decompose_outline_to_chapters(
        volume_number=volume_number,
        foreshadowings=kwargs.get("foreshadowings"),
        character_states=kwargs.get("character_states"),
    )


def analyze_volume_tension(
    novel_id: str,
    volume_outline: Dict[str, Any],
    volume_number: int,
    total_chapters: int,
    chapter_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    便捷函数：分析卷张力循环分布.

    Args:
        novel_id: 小说 ID
        volume_outline: 卷大纲
        volume_number: 卷号
        total_chapters: 卷总章节数
        chapter_config: 章节配置（可选）

    Returns:
        张力循环分析报告
    """
    mapper = ChapterOutlineMapper(novel_id)
    mapper.load_volume_outline(
        volume_number, volume_outline, total_chapters, chapter_config
    )
    return mapper.analyze_tension_cycle_distribution(volume_number=volume_number)
