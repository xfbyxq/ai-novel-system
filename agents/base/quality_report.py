"""质量报告基类

提供所有审查循环共享的质量评估报告基础结构。
各子类可以通过添加额外字段来扩展特定领域的分析。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe_extract_score(data: Dict[str, Any], quality_threshold: float) -> float:
    """从 LLM 响应中安全提取 overall_score，字段缺失时降级处理。

    降级策略：
    1. 优先使用 overall_score 字段
    2. 若缺失，使用 dimension_scores 的平均值
    3. 若均缺失，使用 quality_threshold 作为保守估计
    """
    if "overall_score" in data:
        try:
            return float(data["overall_score"])
        except (ValueError, TypeError):
            pass

    dim_scores = data.get("dimension_scores", {})
    if dim_scores and isinstance(dim_scores, dict):
        try:
            values = [float(v) for v in dim_scores.values()]
            avg = sum(values) / len(values)
            logger.warning(f"overall_score缺失，使用维度平均分: {avg:.1f}")
            return avg
        except (ValueError, TypeError):
            pass

    logger.warning(
        f"overall_score和dimension_scores均缺失，使用阈值: {quality_threshold}"
    )
    return quality_threshold


@dataclass
class BaseQualityReport:
    """质量评估报告基类

    所有审查循环的质量报告都继承自此类，包含：
    - overall_score: 综合评分 (1-10)
    - dimension_scores: 各维度评分
    - passed: 是否通过质量阈值
    - issues: 发现的问题列表
    - summary: 评估摘要

    子类可以添加特定领域的分析字段，如：
    - WorldQualityReport: consistency_analysis (一致性分析)
    - CharacterQualityReport: uniqueness_analysis (独特性分析)
    - PlotQualityReport: structure_analysis (结构分析)

    使用示例：
        report = BaseQualityReport(
            overall_score=8.5,
            dimension_scores={"fluency": 9.0, "logic": 8.0},
            passed=True,
            summary="质量良好"
        )
    """

    # 综合评分 (1-10)
    overall_score: float = 0.0

    # 各维度评分，键为维度名称，值为分数
    dimension_scores: Dict[str, float] = field(default_factory=dict)

    # 是否通过质量阈值
    passed: bool = False

    # 发现的问题列表
    # 每个问题是一个字典，包含 area, issue, severity, suggestion 等字段
    issues: List[Dict[str, Any]] = field(default_factory=list)

    # 评估摘要
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        子类应覆盖此方法以包含额外字段。

        Returns:
            包含所有报告字段的字典
        """
        return {
            "overall_score": self.overall_score,
            "dimension_scores": self.dimension_scores,
            "passed": self.passed,
            "issues": self.issues,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseQualityReport":
        """从字典创建报告

        Args:
            data: 包含报告数据的字典

        Returns:
            BaseQualityReport 实例
        """
        return cls(
            overall_score=float(data.get("overall_score", 0)),
            dimension_scores=data.get("dimension_scores", {}),
            passed=data.get("passed", False),
            issues=data.get("issues", []),
            summary=data.get("summary", ""),
        )

    @classmethod
    def from_llm_response(
        cls, data: Dict[str, Any], quality_threshold: float = 7.0
    ) -> "BaseQualityReport":
        """从 LLM 响应创建报告

        自动计算 passed 状态。

        Args:
            data: LLM 返回的评估数据
            quality_threshold: 质量阈值

        Returns:
            BaseQualityReport 实例
        """
        score = _safe_extract_score(data, quality_threshold)
        return cls(
            overall_score=score,
            dimension_scores=data.get("dimension_scores", {}),
            passed=score >= quality_threshold,
            issues=data.get("critical_issues", data.get("issues", [])),
            summary=data.get("summary", ""),
        )

    def get_issue_count(self, severity: Optional[str] = None) -> int:
        """获取问题数量

        Args:
            severity: 可选的严重程度筛选 (high/medium/low)

        Returns:
            问题数量
        """
        if severity is None:
            return len(self.issues)
        return sum(
            1
            for issue in self.issues
            if issue.get("severity", "").lower() == severity.lower()
        )

    def get_high_severity_issues(self) -> List[Dict[str, Any]]:
        """获取高严重度问题"""
        return [
            issue
            for issue in self.issues
            if issue.get("severity", "").lower() == "high"
        ]

    def get_dimension_average(self) -> float:
        """计算维度评分平均值"""
        if not self.dimension_scores:
            return 0.0
        return sum(self.dimension_scores.values()) / len(self.dimension_scores)

    def merge_issues(self, other: "BaseQualityReport") -> None:
        """合并另一个报告的问题

        用于在多轮迭代中追踪所有发现的问题。

        Args:
            other: 另一个质量报告
        """
        existing_issues = {
            (issue.get("area", ""), issue.get("issue", "")) for issue in self.issues
        }
        for issue in other.issues:
            key = (issue.get("area", ""), issue.get("issue", ""))
            if key not in existing_issues:
                self.issues.append(issue)


@dataclass
class WorldQualityReport(BaseQualityReport):
    """世界观质量评估报告

    在基类基础上添加一致性分析。
    """

    # 一致性分析
    consistency_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["consistency_analysis"] = self.consistency_analysis
        return data

    @classmethod
    def from_llm_response(
        cls, data: Dict[str, Any], quality_threshold: float = 7.0
    ) -> "WorldQualityReport":
        score = _safe_extract_score(data, quality_threshold)
        return cls(
            overall_score=score,
            dimension_scores=data.get("dimension_scores", {}),
            passed=score >= quality_threshold,
            issues=data.get("critical_issues", []),
            summary=data.get("summary", ""),
            consistency_analysis=data.get("consistency_analysis", {}),
        )


@dataclass
class CharacterQualityReport(BaseQualityReport):
    """角色质量评估报告

    在基类基础上添加独特性分析。
    """

    # 独特性分析
    uniqueness_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["uniqueness_analysis"] = self.uniqueness_analysis
        return data

    @classmethod
    def from_llm_response(
        cls, data: Dict[str, Any], quality_threshold: float = 7.0
    ) -> "CharacterQualityReport":
        score = _safe_extract_score(data, quality_threshold)
        return cls(
            overall_score=score,
            dimension_scores=data.get("dimension_scores", {}),
            passed=score >= quality_threshold,
            issues=data.get("critical_issues", []),
            summary=data.get("summary", ""),
            uniqueness_analysis=data.get("uniqueness_analysis", {}),
        )


@dataclass
class PlotQualityReport(BaseQualityReport):
    """情节质量评估报告

    在基类基础上添加结构分析。
    """

    # 结构分析
    structure_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["structure_analysis"] = self.structure_analysis
        return data

    @classmethod
    def from_llm_response(
        cls, data: Dict[str, Any], quality_threshold: float = 7.0
    ) -> "PlotQualityReport":
        score = _safe_extract_score(data, quality_threshold)
        return cls(
            overall_score=score,
            dimension_scores=data.get("dimension_scores", {}),
            passed=score >= quality_threshold,
            issues=data.get("critical_issues", []),
            summary=data.get("summary", ""),
            structure_analysis=data.get("structure_analysis", {}),
        )


@dataclass
class ChapterQualityReport(BaseQualityReport):
    """章节质量评估报告

    在基类基础上添加修订建议和加权总分计算。
    权重设计：爽感设计 30%，其他维度共 70%
    """

    # 修订建议列表
    suggestions: List[Dict[str, Any]] = field(default_factory=list)

    # 维度权重配置
    _weights: Dict[str, float] = field(
        default_factory=lambda: {
            "fluency": 0.15,
            "plot_logic": 0.20,
            "character_consistency": 0.20,
            "pacing": 0.15,
            "satisfaction_design": 0.30,  # 爽感设计权重最高
        }
    )

    @property
    def weighted_score(self) -> float:
        """计算加权总分

        Returns:
            加权后的总分（0-10）
        """
        if not self.dimension_scores:
            return 0.0

        weighted_sum = 0.0
        for dim, score in self.dimension_scores.items():
            weight = self._weights.get(dim, 0.0)
            weighted_sum += score * weight

        return weighted_sum

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["suggestions"] = self.suggestions
        data["weighted_score"] = self.weighted_score
        data["weights"] = self._weights
        return data

    @classmethod
    def from_llm_response(
        cls, data: Dict[str, Any], quality_threshold: float = 7.5
    ) -> "ChapterQualityReport":
        score = _safe_extract_score(data, quality_threshold)
        return cls(
            overall_score=score,
            dimension_scores=data.get("dimension_scores", {}),
            passed=score >= quality_threshold,
            issues=data.get("critical_issues", []),
            summary=data.get("summary", ""),
            suggestions=data.get("revision_suggestions", []),
        )
