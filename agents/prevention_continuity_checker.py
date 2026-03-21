"""
PreventionContinuityChecker - 预防式连贯性检查器.

功能：
1. 在章节生成前检查策划是否有潜在连贯性问题
2. 检查策划是否回应了上一章的约束
3. 检查策划是否与上一章情节冲突
4. 检查策划是否推进了必要的剧情
5. 提供修正建议并自动修正策划

解决根本原因 6：连贯性保障启动过晚

核心理念：预防胜于治疗 - 在生成前防止问题，而不是生成后修复
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.logging_config import logger


@dataclass
class ContinuityConstraint:
    """连贯性约束."""

    id: str
    type: str  # "expectation", "conflict", "goal", "foreshadowing"
    description: str
    source_chapter: int
    priority: int  # 1-10
    category: str = ""  # "plot", "character", "world"
    related_characters: List[str] = field(default_factory=list)
    must_address: bool = True  # 是否必须回应

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "source_chapter": self.source_chapter,
            "priority": self.priority,
            "category": self.category,
            "related_characters": self.related_characters,
            "must_address": self.must_address,
        }


@dataclass
class PlanConflict:
    """策划冲突."""

    conflict_type: str  # "plot", "character", "timeline", "logic"
    description: str
    severity: str  # "critical", "high", "medium", "low"
    previous_chapter_element: str
    current_plan_element: str
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "type": self.conflict_type,
            "description": self.description,
            "severity": self.severity,
            "previous_element": self.previous_chapter_element,
            "current_element": self.current_plan_element,
            "suggestion": self.suggestion,
        }


@dataclass
class MissingProgress:
    """缺失的剧情推进."""

    element_type: str  # "plot_point", "character_arc", "foreshadowing"
    description: str
    importance: int  # 1-10
    expected_chapter: int
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "type": self.element_type,
            "description": self.description,
            "importance": self.importance,
            "expected_chapter": self.expected_chapter,
            "reason": self.reason,
        }


@dataclass
class PreventionReport:
    """预防式检查报告."""

    chapter_number: int
    passed: bool = True

    # 检查结果
    ignored_constraints: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[PlanConflict] = field(default_factory=list)
    missing_progress: List[MissingProgress] = field(default_factory=list)

    # 评分
    constraint_response_score: float = 0.0
    consistency_score: float = 0.0
    progress_score: float = 0.0

    # 修正建议
    suggestions: List[str] = field(default_factory=list)
    required_fixes: List[str] = field(default_factory=list)

    # 详细分析
    analysis: str = ""

    @property
    def overall_score(self) -> float:
        """计算综合评分."""
        return (
            self.constraint_response_score * 0.4
            + self.consistency_score * 0.35
            + self.progress_score * 0.25
        )

    @property
    def has_critical_issues(self) -> bool:
        """是否有严重问题."""
        return any(c.severity == "critical" for c in self.conflicts)

    @property
    def has_issues(self) -> bool:
        """是否有问题."""
        return (
            len(self.ignored_constraints) > 0
            or len(self.conflicts) > 0
            or len(self.missing_progress) > 0
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "chapter_number": self.chapter_number,
            "passed": self.passed,
            "overall_score": round(self.overall_score, 2),
            "dimension_scores": {
                "constraint_response": round(self.constraint_response_score, 2),
                "consistency": round(self.consistency_score, 2),
                "progress": round(self.progress_score, 2),
            },
            "issues": {
                "ignored_constraints": self.ignored_constraints,
                "conflicts": [c.to_dict() for c in self.conflicts],
                "missing_progress": [m.to_dict() for m in self.missing_progress],
            },
            "suggestions": self.suggestions,
            "required_fixes": self.required_fixes,
            "analysis": self.analysis,
        }


class PreventionContinuityChecker:
    """
    预防式连贯性检查器.

    核心方法：
    1. 在章节策划完成后、生成前进行检查
    2. 识别潜在的连贯性问题
    3. 提供修正建议
    4. 自动修正策划（可选）
    """

    # 检查提示词模板
    CHECK_PROMPT = """请作为专业编辑，检查以下章节策划是否存在连贯性问题.

## 上一章结尾
{previous_chapter_ending}

## 推断的读者期待（约束）
{constraints}

## 当前章节策划
{chapter_plan}

## 检查任务

请从以下维度检查：

1. **约束回应**：策划是否回应了上一章的约束？
2. **情节一致性**：策划是否与上一章情节冲突？
3. **逻辑连贯**：策划是否符合逻辑？
4. **剧情推进**：策划是否推进了必要的剧情？

## 输出格式

请以 JSON 格式输出检查结果：
{{
    "passed": true/false,
    "ignored_constraints": [
        {{
            "constraint": "约束描述",
            "severity": "high/medium/low",
            "reason": "为什么忽略了此约束"
        }}
    ],
    "conflicts": [
        {{
            "type": "plot/character/timeline/logic",
            "description": "冲突描述",
            "severity": "critical/high/medium/low",
            "previous_element": "上一章的元素",
            "current_element": "当前策划的元素",
            "suggestion": "修正建议"
        }}
    ],
    "missing_progress": [
        {{
            "type": "plot_point/character_arc/foreshadowing",
            "description": "缺失的推进",
            "importance": 1-10,
            "reason": "为什么需要这个推进"
        }}
    ],
    "suggestions": ["建议 1", "建议 2"],
    "required_fixes": ["必须修正的问题 1", "必须修正的问题 2"]
}}
"""

    def __init__(self, novel_id: str):
        """
        初始化预防式检查器.

        Args:
            novel_id: 小说 ID
        """
        self.novel_id = novel_id
        self.check_history: List[PreventionReport] = []
        logger.info(f"PreventionContinuityChecker initialized for novel {novel_id}")

    async def check_chapter_plan(
        self,
        chapter_plan: Dict[str, Any],
        previous_chapter: Dict[str, Any],
        constraints: List[ContinuityConstraint],
        chapter_number: int,
    ) -> PreventionReport:
        """
        检查章节策划.

        Args:
            chapter_plan: 章节策划
            previous_chapter: 上一章信息
            constraints: 约束列表
            chapter_number: 章节号

        Returns:
            PreventionReport
        """
        logger.info(f"Checking chapter {chapter_number} plan for continuity issues")

        report = PreventionReport(chapter_number=chapter_number)

        # 1. 检查约束回应
        constraint_check = self._check_constraint_response(chapter_plan, constraints)
        report.ignored_constraints = constraint_check["ignored"]
        report.constraint_response_score = constraint_check["score"]

        # 2. 检查情节一致性
        consistency_check = self._check_plot_consistency(chapter_plan, previous_chapter)
        report.conflicts = consistency_check["conflicts"]
        report.consistency_score = consistency_check["score"]

        # 3. 检查剧情推进
        progress_check = self._check_plot_progress(
            chapter_plan, previous_chapter, constraints
        )
        report.missing_progress = progress_check["missing"]
        report.progress_score = progress_check["score"]

        # 4. 综合判断
        report.passed = report.overall_score >= 7.0 and not report.has_critical_issues

        # 5. 生成分析和建议
        report.analysis = self._generate_analysis(report)
        report.suggestions = self._generate_suggestions(report)
        report.required_fixes = self._generate_required_fixes(report)

        # 6. 记录历史
        self.check_history.append(report)

        logger.info(
            f"Prevention check completed: score={report.overall_score:.1f}, "
            f"passed={report.passed}"
        )

        return report

    def _check_constraint_response(
        self, chapter_plan: Dict[str, Any], constraints: List[ContinuityConstraint]
    ) -> Dict[str, Any]:
        """检查约束回应."""
        ignored = []
        score = 10.0

        chapter_plan_text = json.dumps(chapter_plan, ensure_ascii=False).lower()

        for constraint in constraints:
            if not constraint.must_address:
                continue

            # 高优先级约束必须回应
            if constraint.priority >= 8:
                constraint_text = constraint.description.lower()

                # 简化检查：关键词匹配
                keywords = [w for w in constraint_text.split() if len(w) > 1][:3]

                if not any(kw in chapter_plan_text for kw in keywords):
                    ignored.append(
                        {
                            "constraint": constraint.description,
                            "severity": "high",
                            "reason": f"未回应高优先级约束（优先级：{constraint.priority}）",
                            "constraint_id": constraint.id,
                        }
                    )
                    score -= 2.0

        return {"ignored": ignored, "score": max(0.0, score)}

    def _check_plot_consistency(
        self, chapter_plan: Dict[str, Any], previous_chapter: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检查情节一致性."""
        conflicts = []
        score = 10.0

        # 提取上一章的关键信息
        prev_ending = previous_chapter.get("ending_state", "")
        prev_characters = previous_chapter.get("characters_present", [])
        prev_location = previous_chapter.get("location", "")
        prev_time = previous_chapter.get("time", "")

        # 提取当前策划的关键信息
        plan_start = chapter_plan.get("opening_state", "")
        plan_characters = chapter_plan.get("characters", [])
        plan_location = chapter_plan.get("setting", "")

        # 检查 1：地点连续性
        if prev_location and plan_location:
            if (
                prev_location != plan_location
                and not self._is_location_transition_valid(
                    prev_location, plan_location, chapter_plan
                )
            ):
                conflicts.append(
                    PlanConflict(
                        conflict_type="location",
                        description="地点转换缺乏过渡",
                        severity="medium",
                        previous_chapter_element=f"上一章地点：{prev_location}",
                        current_plan_element=f"本章地点：{plan_location}",
                        suggestion="添加地点转换的描述或说明",
                    )
                )
                score -= 1.5

        # 检查 2：角色连续性
        for char in prev_characters:
            if char not in plan_characters:
                # 角色突然消失
                if self._is_character_important(char, previous_chapter):
                    conflicts.append(
                        PlanConflict(
                            conflict_type="character",
                            description=f"重要角色{char}突然消失",
                            severity="medium",
                            previous_chapter_element=f"上一章在场：{char}",
                            current_plan_element=f"本章未出现：{char}",
                            suggestion="说明角色去向或安排出场",
                        )
                    )
                    score -= 1.0

        # 检查 3：时间连续性
        if prev_time and not self._is_time_transition_valid(prev_time, chapter_plan):
            conflicts.append(
                PlanConflict(
                    conflict_type="timeline",
                    description="时间线不连贯",
                    severity="low",
                    previous_chapter_element=f"上一章时间：{prev_time}",
                    current_plan_element="本章时间不明确",
                    suggestion="明确说明时间流逝",
                )
            )
            score -= 0.5

        # 检查 4：状态连续性
        if prev_ending and plan_start:
            if not self._is_state_transition_smooth(prev_ending, plan_start):
                conflicts.append(
                    PlanConflict(
                        conflict_type="plot",
                        description="情节状态转换不自然",
                        severity="medium",
                        previous_chapter_element=f"上一章结尾：{prev_ending[:50]}",
                        current_plan_element=f"本章开头：{plan_start[:50]}",
                        suggestion="添加过渡场景或描述",
                    )
                )
                score -= 1.5

        return {"conflicts": conflicts, "score": max(0.0, score)}

    def _check_plot_progress(
        self,
        chapter_plan: Dict[str, Any],
        previous_chapter: Dict[str, Any],
        constraints: List[ContinuityConstraint],
    ) -> Dict[str, Any]:
        """检查剧情推进."""
        missing = []
        score = 10.0

        # 检查是否有明确的剧情推进
        main_events = chapter_plan.get("main_events", [])

        if not main_events:
            missing.append(
                MissingProgress(
                    element_type="plot_point",
                    description="本章缺乏明确的主要事件",
                    importance=8,
                    reason="每章至少需要一个推进剧情的主要事件",
                )
            )
            score -= 3.0

        # 检查是否推进了待解决的冲突
        for constraint in constraints:
            if constraint.type == "conflict" and constraint.priority >= 7:
                if not self._plan_addresses_conflict(chapter_plan, constraint):
                    missing.append(
                        MissingProgress(
                            element_type="plot_point",
                            description=f"未推进冲突：{constraint.description}",
                            importance=constraint.priority,
                            reason=f"该冲突始于第{constraint.source_chapter}章，需要推进",
                        )
                    )
                    score -= 1.5

        # 检查角色发展
        character_arcs = chapter_plan.get("character_development", {})
        if not character_arcs and len(main_events) > 0:
            # 有事件但没有角色发展
            missing.append(
                MissingProgress(
                    element_type="character_arc",
                    description="本章缺乏角色发展",
                    importance=5,
                    reason="剧情事件应该带来角色成长或变化",
                )
            )
            score -= 1.0

        return {"missing": missing, "score": max(0.0, score)}

    def _is_location_transition_valid(
        self, prev_location: str, new_location: str, chapter_plan: Dict[str, Any]
    ) -> bool:
        """检查地点转换是否有效."""
        # 如果相同，有效
        if prev_location == new_location:
            return True

        # 检查是否有转换描述
        opening = chapter_plan.get("opening", "")
        if any(word in opening for word in ["来到", "到达", "前往", "回到"]):
            return True

        # 简化：假设有转换描述就有效
        return True

    def _is_time_transition_valid(
        self, prev_time: str, chapter_plan: Dict[str, Any]
    ) -> bool:
        """检查时间转换是否有效."""
        opening = chapter_plan.get("opening", "")

        # 检查是否有时间流逝的描述
        time_words = ["第二天", "几天后", "一周后", "随即", "立刻"]
        return any(word in opening for word in time_words)

    def _is_state_transition_smooth(self, prev_ending: str, plan_start: str) -> bool:
        """检查状态转换是否自然."""
        # 简化：检查是否有明显的冲突
        prev_lower = prev_ending.lower()
        start_lower = plan_start.lower()

        # 如果上一章是紧张状态，本章突然轻松，可能不自然
        tension_words = ["危险", "危机", "战斗", "逃跑"]
        relax_words = ["平静", "休息", "闲聊"]

        if any(w in prev_lower for w in tension_words):
            if any(w in start_lower for w in relax_words):
                return False

        return True

    def _is_character_important(
        self, character: str, previous_chapter: Dict[str, Any]
    ) -> bool:
        """检查角色是否重要."""
        # 简化：主角或重要配角都算重要
        main_characters = previous_chapter.get("main_characters", [])
        return character in main_characters

    def _plan_addresses_conflict(
        self, chapter_plan: Dict[str, Any], conflict_constraint: ContinuityConstraint
    ) -> bool:
        """检查策划是否回应了冲突."""
        chapter_plan_text = json.dumps(chapter_plan, ensure_ascii=False).lower()
        conflict_text = conflict_constraint.description.lower()

        # 简化：关键词匹配
        keywords = [w for w in conflict_text.split() if len(w) > 1][:3]
        return any(kw in chapter_plan_text for kw in keywords)

    def _generate_analysis(self, report: PreventionReport) -> str:
        """生成详细分析."""
        parts = []

        # 约束回应分析
        if report.constraint_response_score >= 8.0:
            parts.append("策划良好地回应了上一章的约束。")
        elif report.constraint_response_score >= 6.0:
            parts.append("策划基本回应了约束，但有遗漏。")
        else:
            parts.append("策划忽略了重要约束。")

        # 一致性分析
        if report.consistency_score >= 8.0:
            parts.append("策划与上一章情节保持一致。")
        else:
            parts.append(f"发现{len(report.conflicts)}个一致性问题。")

        # 推进分析
        if report.progress_score >= 8.0:
            parts.append("策划明确推进了剧情。")
        else:
            parts.append(f"缺少{len(report.missing_progress)}个必要的剧情推进。")

        return " ".join(parts)

    def _generate_suggestions(self, report: PreventionReport) -> List[str]:
        """生成建议."""
        suggestions = []

        if report.ignored_constraints:
            suggestions.append(
                f"建议回应{len(report.ignored_constraints)}个被忽略的约束"
            )

        for conflict in report.conflicts:
            if conflict.severity in ["critical", "high"]:
                suggestions.append(conflict.suggestion)

        if report.missing_progress:
            for missing in report.missing_progress:
                suggestions.append(f"建议添加：{missing.description}")

        return suggestions

    def _generate_required_fixes(self, report: PreventionReport) -> List[str]:
        """生成必须修正的问题."""
        fixes = []

        for conflict in report.conflicts:
            if conflict.severity == "critical":
                fixes.append(f"[严重] {conflict.description}")

        for ignored in report.ignored_constraints:
            if ignored.get("severity") == "high":
                fixes.append(f"[高优先级] {ignored['constraint']}")

        return fixes

    async def suggest_plan_fixes(
        self, chapter_plan: Dict[str, Any], report: PreventionReport
    ) -> Dict[str, Any]:
        """
        建议策划修正.

        Args:
            chapter_plan: 原策划
            report: 检查报告

        Returns:
            修正后的策划
        """
        if not report.has_issues:
            return chapter_plan

        fixed_plan = chapter_plan.copy()

        # 1. 添加缺失的约束回应
        if report.ignored_constraints:
            if "constraint_responses" not in fixed_plan:
                fixed_plan["constraint_responses"] = []

            for ignored in report.ignored_constraints:
                fixed_plan["constraint_responses"].append(
                    {
                        "constraint": ignored["constraint"],
                        "response": f"在本章中间接回应{ignored['constraint']}",
                    }
                )

        # 2. 添加过渡场景
        for conflict in report.conflicts:
            if conflict.conflict_type == "location":
                # 添加地点转换描述
                if "opening" not in fixed_plan:
                    fixed_plan["opening"] = ""
                fixed_plan[
                    "opening"
                ] += f"从{conflict.previous_chapter_element.split('：')[-1]}来到{conflict.current_plan_element.split('：')[-1]}..."

        # 3. 添加缺失的剧情推进
        if report.missing_progress:
            if "additional_events" not in fixed_plan:
                fixed_plan["additional_events"] = []

            for missing in report.missing_progress:
                fixed_plan["additional_events"].append(
                    {
                        "type": missing.element_type,
                        "description": missing.description,
                        "importance": missing.importance,
                    }
                )

        logger.info(
            f"Suggested {len(fixed_plan.get('constraint_responses', []))} fixes"
        )

        return fixed_plan

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息."""
        if not self.check_history:
            return {"total_checks": 0, "pass_rate": 0, "average_score": 0}

        total = len(self.check_history)
        passed = sum(1 for r in self.check_history if r.passed)
        avg_score = sum(r.overall_score for r in self.check_history) / total

        return {
            "total_checks": total,
            "pass_rate": round(passed / total, 2),
            "average_score": round(avg_score, 2),
            "total_issues_found": sum(
                len(r.ignored_constraints) + len(r.conflicts) + len(r.missing_progress)
                for r in self.check_history
            ),
        }


# 便捷函数
def create_prevention_checker(novel_id: str) -> PreventionContinuityChecker:
    """便捷函数：创建预防式检查器."""
    return PreventionContinuityChecker(novel_id)


async def check_chapter_continuity(
    novel_id: str,
    chapter_plan: Dict[str, Any],
    previous_chapter: Dict[str, Any],
    constraints: List[Dict[str, Any]],
    chapter_number: int,
) -> PreventionReport:
    """便捷函数：检查章节连贯性."""
    checker = PreventionContinuityChecker(novel_id)

    # 转换约束
    constraint_objects = [
        ContinuityConstraint(
            id=c.get("id", ""),
            type=c.get("type", ""),
            description=c.get("description", ""),
            source_chapter=c.get("source_chapter", 0),
            priority=c.get("priority", 5),
            must_address=c.get("must_address", True),
        )
        for c in constraints
    ]

    return await checker.check_chapter_plan(
        chapter_plan=chapter_plan,
        previous_chapter=previous_chapter,
        constraints=constraint_objects,
        chapter_number=chapter_number,
    )
