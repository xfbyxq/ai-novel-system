"""审查结果基类

提供所有审查循环共享的结果数据结构。
支持不同类型的最终输出（字符串/字典/列表）。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, TypeVar

from agents.base.quality_report import (
    BaseQualityReport,
    ChapterQualityReport,
    CharacterQualityReport,
    PlotQualityReport,
    WorldQualityReport,
)

# 泛型类型变量，用于支持不同类型的最终输出
T = TypeVar("T")
R = TypeVar("R", bound=BaseQualityReport)


@dataclass
class BaseReviewResult(Generic[T, R]):
    """审查循环结果基类

    使用泛型支持不同类型的输出：
    - T: 最终内容类型（str/Dict/List）
    - R: 质量报告类型

    属性：
        final_output: 最终审查通过的内容
        final_score: 最终评分
        total_iterations: 总迭代次数
        converged: 是否在阈值内收敛
        iterations: 迭代历史记录
        quality_report: 最终的质量报告
    """

    # 最终输出内容（子类指定具体类型）
    final_output: Optional[T] = None

    # 最终评分
    final_score: float = 0.0

    # 总迭代次数
    total_iterations: int = 0

    # 是否收敛（达到质量阈值）
    converged: bool = False

    # 迭代历史记录
    # 每轮迭代包含：iteration, score, passed, issue_count, dimension_scores
    iterations: List[Dict[str, Any]] = field(default_factory=list)

    # 最终的质量报告
    quality_report: Optional[R] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含结果摘要的字典
        """
        return {
            "final_score": self.final_score,
            "total_iterations": self.total_iterations,
            "converged": self.converged,
            "iterations": self.iterations,
        }

    def add_iteration(
        self,
        iteration: int,
        score: float,
        passed: bool,
        issue_count: int = 0,
        dimension_scores: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> None:
        """添加迭代记录

        Args:
            iteration: 迭代轮次
            score: 本轮评分
            passed: 是否通过
            issue_count: 问题数量
            dimension_scores: 各维度评分
            **kwargs: 其他自定义字段
        """
        record = {
            "iteration": iteration,
            "score": score,
            "passed": passed,
            "issue_count": issue_count,
            "dimension_scores": dimension_scores or {},
        }
        record.update(kwargs)
        self.iterations.append(record)

    def get_score_progression(self) -> List[float]:
        """获取评分变化趋势

        Returns:
            各轮迭代的评分列表
        """
        return [it.get("score", 0) for it in self.iterations]

    def get_improvement(self) -> float:
        """计算评分提升幅度

        Returns:
            最终评分与初始评分的差值
        """
        scores = self.get_score_progression()
        if len(scores) < 2:
            return 0.0
        return scores[-1] - scores[0]

    def is_improved(self) -> bool:
        """判断是否有改进

        Returns:
            评分是否提升
        """
        return self.get_improvement() > 0


@dataclass
class ReviewLoopResult(BaseReviewResult[str, ChapterQualityReport]):
    """章节审查循环结果

    最终输出为字符串（章节内容）。
    """

    # 章节内容使用 final_content 别名（向后兼容）
    final_content: str = ""

    # Editor 效果统计
    editor_stats: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if self.final_content and not self.final_output:
            self.final_output = self.final_content
        elif self.final_output and not self.final_content:
            self.final_content = self.final_output

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        # 添加内容长度信息
        data["content_length"] = len(self.final_content) if self.final_content else 0
        # 添加 Editor 统计信息
        if self.editor_stats:
            data["editor_stats"] = self.editor_stats
        return data


@dataclass
class WorldReviewResult(BaseReviewResult[Dict[str, Any], WorldQualityReport]):
    """世界观审查循环结果

    最终输出为字典（世界观设定）。
    """

    # 世界观设定使用 final_world_setting 别名（向后兼容）
    final_world_setting: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if self.final_world_setting and not self.final_output:
            self.final_output = self.final_world_setting
        elif self.final_output and not self.final_world_setting:
            self.final_world_setting = self.final_output

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        # 添加世界观名称
        if self.final_world_setting:
            data["world_name"] = self.final_world_setting.get("world_name", "")
        return data


@dataclass
class CharacterReviewResult(
    BaseReviewResult[List[Dict[str, Any]], CharacterQualityReport]
):
    """角色审查循环结果

    最终输出为列表（角色列表）。
    """

    # 角色列表使用 final_characters 别名（向后兼容）
    final_characters: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """初始化后处理"""
        if self.final_characters and not self.final_output:
            self.final_output = self.final_characters
        elif self.final_output and not self.final_characters:
            self.final_characters = self.final_output

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["character_count"] = len(self.final_characters)
        return data

    def get_character_names(self) -> List[str]:
        """获取所有角色名称"""
        return [char.get("name", "未知") for char in self.final_characters]


@dataclass
class PlotReviewResult(BaseReviewResult[Dict[str, Any], PlotQualityReport]):
    """情节审查循环结果

    最终输出为字典（情节大纲）。
    """

    # 情节大纲使用 final_plot_outline 别名（向后兼容）
    final_plot_outline: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if self.final_plot_outline and not self.final_output:
            self.final_output = self.final_plot_outline
        elif self.final_output and not self.final_plot_outline:
            self.final_plot_outline = self.final_output

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        # 添加卷数信息
        if self.final_plot_outline:
            volumes = self.final_plot_outline.get("volumes", [])
            data["volume_count"] = len(volumes) if isinstance(volumes, list) else 0
        return data
