"""
章节连贯性保障系统的数据模型.

定义了连贯性约束、验证报告和章节过渡记录的数据结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class ContinuityConstraint:
    """
    连贯性约束的通用抽象.

    不预设具体内容，只定义结构：
    - constraint_type: 约束类型（由 LLM 推断）
    - description: 约束描述（自然语言）
    - priority: 优先级
    - source_context: 产生该约束的上下文
    - validation_hint: 验证提示（如何用自然语言描述违反此约束）

    Attributes:
        constraint_type: 约束类型，如 "logical"|"narrative"|"emotional"|"other"
        description: 自然语言描述，例如："场景转换需要提供过渡"
        priority: 优先级 1-10，数字越大优先级越高
        source_text: 触发该约束的原文片段
        validation_hint: 验证提示，例如："检查是否描述了时间流逝"
        inferred_at: 推断时间
        confidence: LLM 推断置信度 0-1
    """

    constraint_type: str
    description: str
    priority: int
    source_text: str
    validation_hint: str
    inferred_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.9

    def __post_init__(self):
        """验证数据有效性."""
        if not 1 <= self.priority <= 10:
            raise ValueError(f"Priority must be between 1 and 10, got {self.priority}")
        if not 0 <= self.confidence <= 1:
            raise ValueError(
                f"Confidence must be between 0 and 1, got {self.confidence}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "constraint_type": self.constraint_type,
            "description": self.description,
            "priority": self.priority,
            "source_text": self.source_text,
            "validation_hint": self.validation_hint,
            "inferred_at": self.inferred_at.isoformat(),
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContinuityConstraint":
        """从字典创建."""
        return cls(
            constraint_type=data.get("constraint_type", "other"),
            description=data.get("description", ""),
            priority=data.get("priority", 5),
            source_text=data.get("source_text", ""),
            validation_hint=data.get("validation_hint", ""),
            inferred_at=(
                datetime.fromisoformat(data["inferred_at"])
                if "inferred_at" in data
                else datetime.now()
            ),
            confidence=data.get("confidence", 0.9),
        )


@dataclass
class ValidationReport:
    """
    连贯性验证报告.

    包含 LLM 验证的结果，区分"连贯性问题"和"艺术性打破期待"。

    Attributes:
        overall_assessment: 整体评估 "通过"|"需改进"|"严重问题"
        satisfied_constraints: 已满足的约束列表
        unsatisfied_constraints: 未满足的约束列表
        artistic_breaking: 合理打破期待的情况
        needs_regeneration: 是否需要重新生成
        suggestions: 改进建议列表
        critical_issues: 严重问题列表
        quality_score: 质量评分 0-100
    """

    overall_assessment: str  # "通过"|"需改进"|"严重问题"
    satisfied_constraints: List[Dict[str, str]] = field(default_factory=list)
    unsatisfied_constraints: List[Dict[str, str]] = field(default_factory=list)
    artistic_breaking: List[Dict[str, str]] = field(default_factory=list)
    needs_regeneration: bool = False
    suggestions: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    quality_score: float = 0.0

    def __post_init__(self):
        """根据验证结果自动设置 needs_regeneration."""
        if self.overall_assessment == "严重问题":
            self.needs_regeneration = True
        elif self.overall_assessment == "需改进" and len(self.critical_issues) > 0:
            self.needs_regeneration = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "overall_assessment": self.overall_assessment,
            "satisfied_constraints": self.satisfied_constraints,
            "unsatisfied_constraints": self.unsatisfied_constraints,
            "artistic_breaking": self.artistic_breaking,
            "needs_regeneration": self.needs_regeneration,
            "suggestions": self.suggestions,
            "critical_issues": self.critical_issues,
            "quality_score": self.quality_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationReport":
        """从字典创建."""
        return cls(
            overall_assessment=data.get("overall_assessment", "需改进"),
            satisfied_constraints=data.get("satisfied_constraints", []),
            unsatisfied_constraints=data.get("unsatisfied_constraints", []),
            artistic_breaking=data.get("artistic_breaking", []),
            needs_regeneration=data.get("needs_regeneration", False),
            suggestions=data.get("suggestions", []),
            critical_issues=data.get("critical_issues", []),
            quality_score=data.get("quality_score", 0.0),
        )


@dataclass
class ChapterTransition:
    """
    章节过渡记录.

    记录每次章节过渡的决策过程，用于后续分析和系统优化。

    Attributes:
        novel_id: 小说 ID
        from_chapter: 起始章节号
        to_chapter: 目标章节号
        inferred_constraints: 推断的约束列表
        validation_report: 验证报告
        final_decision: 最终决策 "直接采用"|"修改后采用"|"重新生成"
        modification_notes: 修改说明
        created_at: 创建时间
    """

    novel_id: str
    from_chapter: int
    to_chapter: int
    inferred_constraints: List[ContinuityConstraint]
    validation_report: ValidationReport
    final_decision: str  # "直接采用"|"修改后采用"|"重新生成"
    modification_notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """验证最终决策的有效性."""
        valid_decisions = ["直接采用", "修改后采用", "重新生成"]
        if self.final_decision not in valid_decisions:
            raise ValueError(
                f"Invalid decision: {self.final_decision}. Must be one of {valid_decisions}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "novel_id": self.novel_id,
            "from_chapter": self.from_chapter,
            "to_chapter": self.to_chapter,
            "inferred_constraints": [c.to_dict() for c in self.inferred_constraints],
            "validation_report": self.validation_report.to_dict(),
            "final_decision": self.final_decision,
            "modification_notes": self.modification_notes,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterTransition":
        """从字典创建."""
        return cls(
            novel_id=data["novel_id"],
            from_chapter=data["from_chapter"],
            to_chapter=data["to_chapter"],
            inferred_constraints=[
                ContinuityConstraint.from_dict(c)
                for c in data.get("inferred_constraints", [])
            ],
            validation_report=ValidationReport.from_dict(data["validation_report"]),
            final_decision=data["final_decision"],
            modification_notes=data.get("modification_notes", ""),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else datetime.now()
            ),
        )


# 便捷类型别名
ConstraintList = List[ContinuityConstraint]
