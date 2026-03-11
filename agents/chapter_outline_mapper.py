"""
ChapterOutlineMapper - 章节大纲映射器

功能：
1. 将卷级大纲分解为章节级任务
2. 为每章分配"必须完成的大纲事件"
3. 追踪大纲完成进度

解决根本原因 4：情节规划缺乏章节级粒度
"""
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.logging_config import logger


@dataclass
class TensionCycle:
    """张力循环（欲扬先抑）"""
    cycle_number: int
    start_chapter: int
    end_chapter: int
    suppress_chapters: List[int]  # 压制期章节
    release_chapter: int  # 释放期章节
    
    suppression_events: List[str] = field(default_factory=list)
    release_events: List[str] = field(default_factory=list)
    
    def position(self, chapter_number: int) -> str:
        """判断章节在循环中的位置"""
        if chapter_number in self.suppress_chapters:
            return "suppress"
        elif chapter_number == self.release_chapter:
            return "release"
        else:
            return "transition"
    
    def progress(self, chapter_number: int) -> float:
        """计算循环进度 (0-1)"""
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
    """章节级大纲任务"""
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
        """转换为提示词格式"""
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
        """检查章节计划是否完成了大纲任务"""
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
    """大纲验证报告"""
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
        """转换为字典"""
        return {
            "chapter_number": self.chapter_number,
            "passed": self.passed,
            "completion": {
                "completed_events": self.completed_events,
                "missing_events": self.missing_events
            },
            "foreshadowing": {
                "planted": self.planted_foreshadowings,
                "missing": self.missing_foreshadowings
            },
            "scores": {
                "completion_rate": self.completion_rate,
                "quality_score": self.quality_score
            },
            "suggestions": self.suggestions
        }


class ChapterOutlineMapper:
    """
    章节大纲映射器
    
    核心算法：
    1. 解析卷级大纲的张力循环
    2. 将关键事件分配到具体章节
    3. 为每章生成强制性任务列表
    """
    
    def __init__(self, novel_id: str):
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
        chapter_config: Optional[Dict[str, Any]] = None
    ):
        """
        加载卷大纲并解析张力循环
        
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
        logger.info(f"Loading volume {volume_number} outline with {total_chapters_in_volume} chapters")
        
        self.volume_outlines[volume_number] = volume_outline
        
        # 存储章节配置
        if chapter_config:
            self.volume_outlines[volume_number]["chapter_config"] = chapter_config
        
        # 解析张力循环
        self.tension_cycles[volume_number] = self._parse_tension_cycles(
            volume_outline,
            total_chapters_in_volume,
            chapter_config
        )
        
        logger.info(
            f"Volume {volume_number} loaded with "
            f"{len(self.tension_cycles[volume_number])} tension cycles"
        )
    
    def _parse_tension_cycles(
        self,
        volume_outline: Dict[str, Any],
        total_chapters: int,
        chapter_config: Optional[Dict[str, Any]] = None
    ) -> List[TensionCycle]:
        """
        从卷大纲中解析张力循环
        
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
        max_chapters = chapter_config.get("max_chapters", total_chapters * 1.5) if chapter_config else total_chapters * 1.5
        
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
            
            cycle = TensionCycle(
                cycle_number=i + 1,
                start_chapter=start_ch,
                end_chapter=end_ch,
                suppress_chapters=suppress_chapters,
                release_chapter=release_ch,
                suppression_events=cycle_data.get("suppress_events", []),
                release_events=[cycle_data.get("release_event", "")]
            )
            
            cycles.append(cycle)
        
        return cycles
    
    def _create_default_tension_cycles(
        self,
        total_chapters: int,
        chapter_config: Optional[Dict[str, Any]] = None
    ) -> List[TensionCycle]:
        """
        创建默认张力循环
        
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
                release_events=[f"第{end_ch}章的胜利"]
            )
            
            cycles.append(cycle)
        
        return cycles
    
    def map_outline_to_chapter(
        self,
        volume_number: int,
        chapter_number: int,
        foreshadowings: Optional[List[Dict[str, Any]]] = None
    ) -> ChapterOutlineTask:
        """
        为指定章节分配大纲任务
        
        Args:
            volume_number: 卷号
            chapter_number: 章节号
            foreshadowings: 伏笔列表（用于分配伏笔任务）
        
        Returns:
            ChapterOutlineTask
        """
        logger.info(f"Mapping outline to chapter {chapter_number} (volume {volume_number})")
        
        # 1. 获取卷大纲
        volume_outline = self.volume_outlines.get(volume_number)
        if not volume_outline:
            logger.warning(f"Volume {volume_number} outline not found")
            return self._create_empty_task(chapter_number, volume_number)
        
        # 2. 找到当前章所属的张力循环
        current_cycle = self._find_current_cycle(volume_number, chapter_number)
        
        # 3. 创建任务
        task = ChapterOutlineTask(
            chapter_number=chapter_number,
            volume_number=volume_number
        )
        
        # 4. 根据循环位置分配事件
        if current_cycle:
            position = current_cycle.position(chapter_number)
            
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
        
        # 5. 添加卷的关键事件
        key_events = volume_outline.get("key_events", [])
        for event_data in key_events:
            if isinstance(event_data, dict):
                event_chapter = event_data.get("chapter", 0)
                if event_chapter == chapter_number:
                    task.mandatory_events.append(event_data.get("event", ""))
                    task.is_milestone = True
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
        
        # 缓存任务
        self.chapter_tasks[chapter_number] = task
        
        logger.info(
            f"Chapter {chapter_number} task created: "
            f"{len(task.mandatory_events)} mandatory events"
        )
        
        return task
    
    def _find_current_cycle(
        self,
        volume_number: int,
        chapter_number: int
    ) -> Optional[TensionCycle]:
        """找到当前章所属的张力循环"""
        cycles = self.tension_cycles.get(volume_number, [])
        
        for cycle in cycles:
            if cycle.start_chapter <= chapter_number <= cycle.end_chapter:
                return cycle
        
        return None
    
    def _add_foreshadowing_tasks(
        self,
        task: ChapterOutlineTask,
        chapter_number: int,
        foreshadowings: List[Dict[str, Any]]
    ):
        """添加伏笔任务"""
        for foreshadow in foreshadowings:
            if foreshadow.get("status") != "pending":
                continue
            
            planted_chapter = foreshadow.get("planted_chapter", 0)
            expected_resolve = foreshadow.get("expected_resolve_chapter", 0)
            
            # 检查是否需要回收
            if expected_resolve == chapter_number:
                task.foreshadowing_to_payoff.append(
                    f"[第{planted_chapter}章] {foreshadow.get('content', '')}"
                )
            # 检查是否超期
            elif chapter_number - planted_chapter >= 5 and foreshadow.get("importance", 0) >= 7:
                task.foreshadowing_to_payoff.append(
                    f"[超期] {foreshadow.get('content', '')}"
                )
            
            # 检查是否需要埋设（基于大纲的未来事件）
            # 这里简化处理，实际应该分析大纲预测需要埋设的伏笔
    
    def _generate_task_description(
        self,
        task: ChapterOutlineTask,
        volume_outline: Dict[str, Any]
    ) -> str:
        """生成任务描述"""
        parts = []
        
        if task.is_golden_chapter:
            parts.append("这是黄金三章之一，必须吸引读者继续阅读。")
        
        if task.is_climax:
            parts.append("这是本卷的高潮章节，需要营造最大的冲突和张力。")
        
        if task.mandatory_events:
            parts.append(f"本章必须完成{len(task.mandatory_events)}个关键事件。")
        
        if task.foreshadowing_to_payoff:
            parts.append(
                f"本章需要回收{len(task.foreshadowing_to_payoff)}个伏笔。"
            )
        
        return " ".join(parts)
    
    def _create_empty_task(
        self,
        chapter_number: int,
        volume_number: int
    ) -> ChapterOutlineTask:
        """创建空任务（当找不到大纲时）"""
        return ChapterOutlineTask(
            chapter_number=chapter_number,
            volume_number=volume_number,
            mandatory_events=["推进剧情发展"],
            optional_events=[],
            emotional_tone="根据情节需要"
        )
    
    def validate_chapter_against_outline(
        self,
        chapter_plan: Dict[str, Any],
        chapter_number: int
    ) -> OutlineValidationReport:
        """
        验证章节计划是否完成了大纲任务
        
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
        
        report.completion_rate = completed / total_mandatory if total_mandatory > 0 else 0
        
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
        self,
        volume_number: int,
        current_chapter: int
    ) -> Dict[str, Any]:
        """获取大纲进度"""
        cycles = self.tension_cycles.get(volume_number, [])
        
        completed_tasks = sum(
            1 for ch, task in self.chapter_tasks.items()
            if ch <= current_chapter
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
                self._find_current_cycle(volume_number, current_chapter).progress(current_chapter)
                if self._find_current_cycle(volume_number, current_chapter)
                else 0
            )
        }


# 便捷函数
def create_outline_mapper(novel_id: str) -> ChapterOutlineMapper:
    """便捷函数：创建大纲映射器"""
    return ChapterOutlineMapper(novel_id)


def map_chapter_outline_task(
    novel_id: str,
    volume_outline: Dict[str, Any],
    chapter_number: int,
    volume_number: int,
    total_chapters: int,
    chapter_config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ChapterOutlineTask:
    """
    便捷函数：为章节分配大纲任务
    
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
    mapper.load_volume_outline(volume_number, volume_outline, total_chapters, chapter_config)
    return mapper.map_outline_to_chapter(
        volume_number=volume_number,
        chapter_number=chapter_number,
        foreshadowings=kwargs.get("foreshadowings")
    )
