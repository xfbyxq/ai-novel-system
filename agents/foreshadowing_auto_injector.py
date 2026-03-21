"""
ForeshadowingAutoInjector - 伏笔自动注入系统

功能：
1. 自动识别当前章需要回收的伏笔（超期提醒）
2. 识别当前章应该埋设的新伏笔（基于大纲）
3. 生成伏笔提示词并强制注入到创作流程
4. 追踪伏笔状态变化

解决根本原因 5：伏笔追踪未集成到生成流程
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.logging_config import logger


class ForeshadowingStatus(str, Enum):
    """伏笔状态."""

    PENDING = "pending"  # 待回收
    PLANTED = "planted"  # 已埋设
    PAYING_OFF = "paying_off"  # 回收中
    RESOLVED = "resolved"  # 已回收
    ABANDONED = "abandoned"  # 已废弃


@dataclass
class Foreshadowing:
    """伏笔定义."""

    id: str
    content: str  # 伏笔内容
    planted_chapter: int  # 埋设章节
    expected_resolve_chapter: int = 0  # 预期回收章节
    actual_resolve_chapter: int = 0  # 实际回收章节

    # 元数据
    importance: int = 5  # 1-10
    category: str = ""  # 类别：plot, character, world_building
    related_characters: List[str] = field(default_factory=list)
    related_plot_points: List[str] = field(default_factory=list)

    # 状态
    status: ForeshadowingStatus = ForeshadowingStatus.PENDING
    payoff_content: str = ""  # 回收内容

    # 追踪
    reminder_count: int = 0  # 被提醒次数
    last_reminder_chapter: int = 0  # 最后提醒章节

    @property
    def urgency_score(self) -> int:
        """计算紧急程度分数."""
        if self.status == ForeshadowingStatus.RESOLVED:
            return 0

        # 基于超期程度计算
        current_chapter = self.planted_chapter  # 简化，实际应该从外部获取
        chapters_since = current_chapter - self.planted_chapter

        # 重要性 * 超期章数
        return self.importance * max(1, chapters_since)

    @property
    def is_overdue(self) -> bool:
        """是否超期."""
        if self.expected_resolve_chapter == 0:
            return False
        current_chapter = self.planted_chapter
        return current_chapter > self.expected_resolve_chapter

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "id": self.id,
            "content": self.content,
            "planted_chapter": self.planted_chapter,
            "expected_resolve_chapter": self.expected_resolve_chapter,
            "importance": self.importance,
            "category": self.category,
            "related_characters": self.related_characters,
            "status": (
                self.status.value if hasattr(self.status, "value") else str(self.status)
            ),
            "payoff_content": self.payoff_content,
            "is_overdue": self.is_overdue,
            "urgency_score": self.urgency_score,
        }


@dataclass
class ForeshadowingTask:
    """伏笔任务."""

    foreshadowing_id: str
    task_type: str  # "plant", "payoff", "reminder"
    content: str
    priority: int  # 1-10
    due_chapter: int
    description: str = ""
    related_plot_point: str = ""

    def to_prompt(self) -> str:
        """转换为提示词."""
        priority_icon = (
            "⚠️" if self.priority >= 8 else "📌" if self.priority >= 5 else "💡"
        )

        if self.task_type == "payoff":
            return (
                f"{priority_icon} **回收伏笔**（第{self.due_chapter}章）\n"
                f"内容：{self.content}\n"
                f"优先级：{'高' if self.priority >= 8 else '中' if self.priority >= 5 else '低'}"
            )
        elif self.task_type == "plant":
            return (
                f"{priority_icon} **埋设伏笔**（为第{self.due_chapter}章）\n"
                f"内容：{self.content}\n"
                f"描述：{self.description}"
            )
        else:
            return f"{priority_icon} **提醒**：{self.content}"


@dataclass
class ForeshadowingReport:
    """伏笔报告."""

    chapter_number: int

    # 任务
    must_payoff_tasks: List[ForeshadowingTask] = field(default_factory=list)
    should_payoff_tasks: List[ForeshadowingTask] = field(default_factory=list)
    can_plant_tasks: List[ForeshadowingTask] = field(default_factory=list)

    # 统计
    total_pending: int = 0
    total_overdue: int = 0
    total_resolved_this_chapter: int = 0

    # 建议
    suggestions: List[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """转换为提示词."""
        parts = ["## 伏笔任务"]

        # 必须回收的伏笔
        if self.must_payoff_tasks:
            parts.append("\n### ⚠️ 必须回收的伏笔（已超期）")
            for task in self.must_payoff_tasks:
                parts.append(f"- {task.to_prompt()}")

        # 应该回收的伏笔
        if self.should_payoff_tasks:
            parts.append("\n### 📌 建议回收的伏笔")
            for task in self.should_payoff_tasks:
                parts.append(f"- {task.to_prompt()}")

        # 可以埋设的伏笔
        if self.can_plant_tasks:
            parts.append("\n### 💡 可以埋设的新伏笔")
            for task in self.can_plant_tasks:
                parts.append(f"- {task.to_prompt()}")

        # 统计
        parts.append(
            f"\n**统计**: 待回收 {self.total_pending} 个，超期 {self.total_overdue} 个"
        )

        return "\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "chapter_number": self.chapter_number,
            "must_payoff": [t.to_dict() for t in self.must_payoff_tasks],
            "should_payoff": [t.to_dict() for t in self.should_payoff_tasks],
            "can_plant": [t.to_dict() for t in self.can_plant_tasks],
            "statistics": {
                "total_pending": self.total_pending,
                "total_overdue": self.total_overdue,
                "resolved_this_chapter": self.total_resolved_this_chapter,
            },
            "suggestions": self.suggestions,
        }


class ForeshadowingAutoInjector:
    """
    伏笔自动注入系统

    核心功能：
    1. 追踪所有伏笔的状态
    2. 为每章生成伏笔任务
    3. 自动注入到创作提示词
    4. 识别伏笔回收机会
    """

    def __init__(self, novel_id: str):
        """
        初始化伏笔注入器

        Args:
            novel_id: 小说 ID
        """
        self.novel_id = novel_id
        self.foreshadowings: Dict[str, Foreshadowing] = {}
        self.resolution_history: List[Dict[str, Any]] = []
        self.injection_history: List[Dict[str, Any]] = []

        logger.info(f"ForeshadowingAutoInjector initialized for novel {novel_id}")

    def add_foreshadowing(self, foreshadowing: Foreshadowing):
        """添加伏笔."""
        self.foreshadowings[foreshadowing.id] = foreshadowing
        logger.info(
            f"Added foreshadowing: {foreshadowing.content[:50]}... "
            f"(chapter {foreshadowing.planted_chapter})"
        )

    def remove_foreshadowing(self, foreshadowing_id: str):
        """移除伏笔."""
        if foreshadowing_id in self.foreshadowings:
            del self.foreshadowings[foreshadowing_id]
            logger.info(f"Removed foreshadowing: {foreshadowing_id}")

    def mark_as_resolved(
        self, foreshadowing_id: str, resolve_chapter: int, payoff_content: str = ""
    ):
        """标记伏笔为已回收."""
        if foreshadowing_id not in self.foreshadowings:
            logger.warning(f"Foreshadowing not found: {foreshadowing_id}")
            return

        foreshadow = self.foreshadowings[foreshadowing_id]
        foreshadow.status = ForeshadowingStatus.RESOLVED
        foreshadow.actual_resolve_chapter = resolve_chapter
        foreshadow.payoff_content = payoff_content

        # 记录回收历史
        self.resolution_history.append(
            {
                "foreshadowing_id": foreshadowing_id,
                "resolve_chapter": resolve_chapter,
                "payoff_content": payoff_content,
                "timestamp": datetime.now().isoformat(),
            }
        )

        logger.info(
            f"Marked foreshadowing as resolved: {foreshadowing_id} "
            f"(chapter {resolve_chapter})"
        )

    def get_chapter_foreshadowing_tasks(
        self, current_chapter: int, plot_outline: Optional[Dict[str, Any]] = None
    ) -> ForeshadowingReport:
        """
        获取当前章的伏笔任务

        Args:
            current_chapter: 当前章节号
            plot_outline: 大纲（用于识别应该埋设的伏笔）

        Returns:
            ForeshadowingReport
        """
        logger.info(f"Generating foreshadowing tasks for chapter {current_chapter}")

        report = ForeshadowingReport(chapter_number=current_chapter)

        # 1. 识别需要回收的伏笔
        self._identify_payoff_tasks(current_chapter, report)

        # 2. 识别可以埋设的伏笔
        if plot_outline:
            self._identify_plant_tasks(current_chapter, plot_outline, report)

        # 3. 统计
        report.total_pending = sum(
            1
            for f in self.foreshadowings.values()
            if f.status == ForeshadowingStatus.PENDING
        )
        report.total_overdue = sum(
            1
            for f in self.foreshadowings.values()
            if f.is_overdue and f.status != ForeshadowingStatus.RESOLVED
        )
        report.total_resolved_this_chapter = sum(
            1
            for h in self.resolution_history
            if h["resolve_chapter"] == current_chapter
        )

        # 4. 生成建议
        self._generate_suggestions(report)

        # 记录注入历史
        self.injection_history.append(
            {
                "chapter": current_chapter,
                "must_payoff": len(report.must_payoff_tasks),
                "should_payoff": len(report.should_payoff_tasks),
                "can_plant": len(report.can_plant_tasks),
            }
        )

        return report

    def _identify_payoff_tasks(self, current_chapter: int, report: ForeshadowingReport):
        """识别需要回收的伏笔任务."""
        for foreshadow in self.foreshadowings.values():
            if foreshadow.status == ForeshadowingStatus.RESOLVED:
                continue

            chapters_since = current_chapter - foreshadow.planted_chapter

            # 超期 5 章以上 + 高重要性 = 必须回收
            if chapters_since >= 5 and foreshadow.importance >= 7:
                task = ForeshadowingTask(
                    foreshadowing_id=foreshadow.id,
                    task_type="payoff",
                    content=foreshadow.content,
                    priority=10,
                    due_chapter=foreshadow.planted_chapter,
                    description=f"已超期{chapters_since}章，重要性：{foreshadow.importance}",
                )
                report.must_payoff_tasks.append(task)
                foreshadow.reminder_count += 1
                foreshadow.last_reminder_chapter = current_chapter

            # 超期 3 章 = 应该回收
            elif chapters_since >= 3:
                task = ForeshadowingTask(
                    foreshadowing_id=foreshadow.id,
                    task_type="payoff",
                    content=foreshadow.content,
                    priority=7,
                    due_chapter=foreshadow.planted_chapter,
                    description=f"已超期{chapters_since}章",
                )
                report.should_payoff_tasks.append(task)
                foreshadow.reminder_count += 1
                foreshadow.last_reminder_chapter = current_chapter

            # 预期回收章节 = 当前章
            elif (
                foreshadow.expected_resolve_chapter == current_chapter
                and foreshadow.importance >= 5
            ):
                task = ForeshadowingTask(
                    foreshadowing_id=foreshadow.id,
                    task_type="payoff",
                    content=foreshadow.content,
                    priority=8,
                    due_chapter=foreshadow.planted_chapter,
                    description="预期在本章回收",
                )
                report.should_payoff_tasks.append(task)

    def _identify_plant_tasks(
        self,
        current_chapter: int,
        plot_outline: Dict[str, Any],
        report: ForeshadowingReport,
    ):
        """识别可以埋设的伏笔任务."""
        # 查找未来的转折点
        future_turning_points = self._get_future_turning_points(
            current_chapter, plot_outline, look_ahead=10
        )

        for turning_point in future_turning_points:
            target_chapter = turning_point.get("chapter", 0)
            event = turning_point.get("event", "")

            # 检查是否已有伏笔
            existing_foreshadow = self._has_foreshadowing_for_event(event)

            if not existing_foreshadow:
                # 需要提前埋设
                chapters_ahead = target_chapter - current_chapter

                # 如果转折点在未来 5-10 章，现在应该埋设伏笔
                if 5 <= chapters_ahead <= 10:
                    task = ForeshadowingTask(
                        foreshadowing_id=f"plant_{target_chapter}_{event[:20]}",
                        task_type="plant",
                        content=f"为第{target_chapter}章的「{event}」埋下伏笔",
                        priority=6,
                        due_chapter=target_chapter,
                        description=f"建议在本章埋设伏笔，为{chapters_ahead}章后的转折做铺垫",
                    )
                    report.can_plant_tasks.append(task)

    def _get_future_turning_points(
        self, current_chapter: int, plot_outline: Dict[str, Any], look_ahead: int = 10
    ) -> List[Dict[str, Any]]:
        """获取未来的转折点."""
        turning_points = []

        # 从大纲中提取关键事件
        key_events = plot_outline.get("key_events", [])

        for event_data in key_events:
            if isinstance(event_data, dict):
                event_chapter = event_data.get("chapter", 0)
                if current_chapter < event_chapter <= current_chapter + look_ahead:
                    turning_points.append(
                        {"chapter": event_chapter, "event": event_data.get("event", "")}
                    )

        return turning_points

    def _has_foreshadowing_for_event(self, event: str) -> Optional[Foreshadowing]:
        """检查是否已有伏笔针对某个事件."""
        event_lower = event.lower()

        for foreshadow in self.foreshadowings.values():
            # 检查相关性
            if foreshadow.status == ForeshadowingStatus.RESOLVED:
                continue

            # 简化检查：关键词匹配
            for plot_point in foreshadow.related_plot_points:
                if event_lower in plot_point.lower():
                    return foreshadow

        return None

    def _generate_suggestions(self, report: ForeshadowingReport):
        """生成建议."""
        if report.must_payoff_tasks:
            report.suggestions.append(
                f"⚠️ 有{len(report.must_payoff_tasks)}个关键伏笔已超期，必须在本章回收！"
            )

        if len(report.should_payoff_tasks) >= 3:
            report.suggestions.append(
                f"📌 有{len(report.should_payoff_tasks)}个伏笔建议回收，避免堆积"
            )

        if report.can_plant_tasks:
            report.suggestions.append(
                f"💡 可以埋设{len(report.can_plant_tasks)}个新伏笔，为未来情节做铺垫"
            )

        # 检查伏笔密度
        if report.total_pending > 10:
            report.suggestions.append(
                "⚠️ 待回收伏笔过多（{0}个），建议加快回收节奏".format(
                    report.total_pending
                )
            )

    def build_foreshadowing_prompt(
        self, current_chapter: int, plot_outline: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建伏笔提示词

        强制提醒作家需要回收/埋设的伏笔
        """
        report = self.get_chapter_foreshadowing_tasks(current_chapter, plot_outline)
        return report.to_prompt()

    def inject_to_prompt(
        self,
        existing_prompt: str,
        current_chapter: int,
        plot_outline: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        将伏笔要求注入到现有提示词

        Args:
            existing_prompt: 现有的提示词
            current_chapter: 当前章节号
            plot_outline: 大纲

        Returns:
            注入后的提示词
        """
        foreshadowing_section = self.build_foreshadowing_prompt(
            current_chapter, plot_outline
        )

        return f"""
{existing_prompt}

---

{foreshadowing_section}

**创作要求**:
- 必须回应所有"必须回收"的伏笔
- 尽量回应"建议回收"的伏笔
- 考虑埋设新的伏笔为未来做铺垫
"""

    def validate_payoff_completion(
        self, chapter_plan: Dict[str, Any], report: ForeshadowingReport
    ) -> Dict[str, Any]:
        """
        验证章节计划是否完成了伏笔任务

        Args:
            chapter_plan: 章节计划
            report: 伏笔报告

        Returns:
            验证结果
        """
        result = {
            "passed": True,
            "completed_payoffs": [],
            "missing_payoffs": [],
            "planted_foreshadowings": [],
            "suggestions": [],
        }

        chapter_text = json.dumps(chapter_plan, ensure_ascii=False).lower()

        # 检查必须回收的伏笔
        for task in report.must_payoff_tasks:
            task_content_lower = task.content.lower()

            # 简化检查：关键词匹配
            keywords = [w for w in task_content_lower.split() if len(w) > 1][:3]

            if any(kw in chapter_text for kw in keywords):
                result["completed_payoffs"].append(task.foreshadowing_id)
            else:
                result["missing_payoffs"].append(
                    {
                        "id": task.foreshadowing_id,
                        "content": task.content,
                        "priority": "critical",
                    }
                )
                result["passed"] = False

        # 检查建议回收的伏笔
        for task in report.should_payoff_tasks:
            task_content_lower = task.content.lower()
            keywords = [w for w in task_content_lower.split() if len(w) > 1][:3]

            if any(kw in chapter_text for kw in keywords):
                result["completed_payoffs"].append(task.foreshadowing_id)
            else:
                result["missing_payoffs"].append(
                    {
                        "id": task.foreshadowing_id,
                        "content": task.content,
                        "priority": "medium",
                    }
                )

        # 检查是否埋设了新伏笔
        planned_foreshadowings = chapter_plan.get("foreshadowing_plants", [])
        result["planted_foreshadowings"] = planned_foreshadowings

        # 生成建议
        if result["missing_payoffs"]:
            critical_missing = [
                m for m in result["missing_payoffs"] if m["priority"] == "critical"
            ]
            if critical_missing:
                result["suggestions"].append(
                    f"⚠️ 必须回收{len(critical_missing)}个关键伏笔：{', '.join(m['content'] for m in critical_missing)}"
                )

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息."""
        total = len(self.foreshadowings)
        resolved = sum(
            1
            for f in self.foreshadowings.values()
            if f.status == ForeshadowingStatus.RESOLVED
        )
        overdue = sum(
            1
            for f in self.foreshadowings.values()
            if f.is_overdue and f.status != ForeshadowingStatus.RESOLVED
        )

        resolution_rate = resolved / total if total > 0 else 0

        return {
            "total_foreshadowings": total,
            "resolved": resolved,
            "pending": total - resolved,
            "overdue": overdue,
            "resolution_rate": round(resolution_rate, 2),
            "total_injections": len(self.injection_history),
            "total_resolutions": len(self.resolution_history),
        }

    def export_foreshadowings(self) -> List[Dict[str, Any]]:
        """导出所有伏笔."""
        return [f.to_dict() for f in self.foreshadowings.values()]


# 便捷函数
def create_foreshadowing_injector(novel_id: str) -> ForeshadowingAutoInjector:
    """便捷函数：创建伏笔注入器."""
    return ForeshadowingAutoInjector(novel_id)


def get_chapter_foreshadowing_requirements(
    novel_id: str,
    current_chapter: int,
    foreshadowings: List[Dict[str, Any]],
    plot_outline: Optional[Dict[str, Any]] = None,
) -> str:
    """便捷函数：获取章节伏笔要求."""
    injector = ForeshadowingAutoInjector(novel_id)

    # 添加伏笔
    for fb_data in foreshadowings:
        foreshadow = Foreshadowing(
            id=fb_data.get("id", ""),
            content=fb_data.get("content", ""),
            planted_chapter=fb_data.get("planted_chapter", 0),
            expected_resolve_chapter=fb_data.get("expected_resolve_chapter", 0),
            importance=fb_data.get("importance", 5),
            status=ForeshadowingStatus(fb_data.get("status", "pending")),
        )
        injector.add_foreshadowing(foreshadow)

    return injector.build_foreshadowing_prompt(current_chapter, plot_outline)
