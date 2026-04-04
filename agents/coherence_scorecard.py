"""
统一连贯性评分体系.

提供六维度连贯性评分卡，从各检查器结果中提取并汇聚分数，
支持跨章节趋势分析和薄弱维度识别。

六维度：
- 情节连贯性 (plot_coherence): 权重 0.25
- 角色一致性 (character_consistency): 权重 0.25
- 世界观一致性 (world_consistency): 权重 0.20
- 时间线连贯性 (timeline_consistency): 权重 0.10
- 空间连贯性 (spatial_consistency): 权重 0.10
- 伏笔完整性 (foreshadowing_integrity): 权重 0.10
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Tuple, cast

from core.logging_config import logger


@dataclass
class DimensionDetail:
    """
    单个维度的详细评估信息.

    记录某个连贯性维度的评分、问题、建议和证据。

    Attributes:
        score: 维度分数 0-10
        issues: 该维度的问题列表，每个问题为包含描述、严重程度等的字典
        suggestions: 改进建议列表
        evidence: 评分依据/证据列表
    """

    score: float = 0.0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self):
        """验证分数范围."""
        if not 0 <= self.score <= 10:
            raise ValueError(f"Score must be between 0 and 10, got {self.score}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典.

        Returns:
            包含所有字段的字典
        """
        return {
            "score": self.score,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DimensionDetail":
        """从字典创建.

        Args:
            data: 包含维度详情的字典

        Returns:
            DimensionDetail 实例
        """
        return cls(
            score=data.get("score", 0.0),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            evidence=data.get("evidence", []),
        )


@dataclass
class TrendReport:
    """
    跨章节趋势报告.

    分析多个章节评分卡的变化趋势，识别改进和退步的维度。

    Attributes:
        chapter_range: 章节范围 (起始章, 结束章)
        dimension_trends: 各维度分数趋势，键为维度名，值为分数列表
        overall_trend: 总分趋势列表
        improving_dimensions: 改进中的维度列表
        declining_dimensions: 退步中的维度列表
        analysis: 趋势分析文本
    """

    chapter_range: Tuple[int, int] = (0, 0)
    dimension_trends: Dict[str, List[float]] = field(default_factory=dict)
    overall_trend: List[float] = field(default_factory=list)
    improving_dimensions: List[str] = field(default_factory=list)
    declining_dimensions: List[str] = field(default_factory=list)
    analysis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典.

        Returns:
            包含所有字段的字典
        """
        return {
            "chapter_range": self.chapter_range,
            "dimension_trends": self.dimension_trends,
            "overall_trend": self.overall_trend,
            "improving_dimensions": self.improving_dimensions,
            "declining_dimensions": self.declining_dimensions,
            "analysis": self.analysis,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrendReport":
        """从字典创建.

        Args:
            data: 包含趋势报告的字典

        Returns:
            TrendReport 实例
        """
        return cls(
            chapter_range=tuple(data.get("chapter_range", (0, 0))),
            dimension_trends=data.get("dimension_trends", {}),
            overall_trend=data.get("overall_trend", []),
            improving_dimensions=data.get("improving_dimensions", []),
            declining_dimensions=data.get("declining_dimensions", []),
            analysis=data.get("analysis", ""),
        )


@dataclass
class CoherenceScorecard:
    """
    六维度统一连贯性评分卡.

    汇聚各检查器的评估结果，提供统一的连贯性评分视图。

    Attributes:
        chapter_number: 章节号
        plot_coherence: 情节连贯性分数 (权重 0.25)
        character_consistency: 角色一致性分数 (权重 0.25)
        world_consistency: 世界观一致性分数 (权重 0.20)
        timeline_consistency: 时间线连贯性分数 (权重 0.10)
        spatial_consistency: 空间连贯性分数 (权重 0.10)
        foreshadowing_integrity: 伏笔完整性分数 (权重 0.10)
        dimension_details: 各维度详细信息字典
        created_at: 创建时间 ISO 格式字符串
    """

    chapter_number: int
    plot_coherence: float = 0.0
    character_consistency: float = 0.0
    world_consistency: float = 0.0
    timeline_consistency: float = 0.0
    spatial_consistency: float = 0.0
    foreshadowing_integrity: float = 0.0
    dimension_details: Dict[str, DimensionDetail] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 维度权重常量
    WEIGHTS: ClassVar[Dict[str, float]] = {
        "plot_coherence": 0.25,
        "character_consistency": 0.25,
        "world_consistency": 0.20,
        "timeline_consistency": 0.10,
        "spatial_consistency": 0.10,
        "foreshadowing_integrity": 0.10,
    }

    # 维度中文名映射
    DIMENSION_NAMES: ClassVar[Dict[str, str]] = {
        "plot_coherence": "情节连贯性",
        "character_consistency": "角色一致性",
        "world_consistency": "世界观一致性",
        "timeline_consistency": "时间线连贯性",
        "spatial_consistency": "空间连贯性",
        "foreshadowing_integrity": "伏笔完整性",
    }

    @property
    def overall_score(self) -> float:
        """计算加权平均总分 (0-10).

        Returns:
            加权平均分数
        """
        scores = {
            "plot_coherence": self.plot_coherence,
            "character_consistency": self.character_consistency,
            "world_consistency": self.world_consistency,
            "timeline_consistency": self.timeline_consistency,
            "spatial_consistency": self.spatial_consistency,
            "foreshadowing_integrity": self.foreshadowing_integrity,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for dim, score in scores.items():
            weight = self.WEIGHTS.get(dim, 0.0)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def get_weak_dimensions(self, threshold: float = 6.0) -> List[str]:
        """获取低于阈值的薄弱维度.

        Args:
            threshold: 分数阈值，低于此值视为薄弱维度

        Returns:
            薄弱维度名称列表
        """
        scores = {
            "plot_coherence": self.plot_coherence,
            "character_consistency": self.character_consistency,
            "world_consistency": self.world_consistency,
            "timeline_consistency": self.timeline_consistency,
            "spatial_consistency": self.spatial_consistency,
            "foreshadowing_integrity": self.foreshadowing_integrity,
        }

        return [dim for dim, score in scores.items() if score < threshold]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典.

        Returns:
            包含所有评分卡信息的字典
        """
        return {
            "chapter_number": self.chapter_number,
            "scores": {
                "plot_coherence": self.plot_coherence,
                "character_consistency": self.character_consistency,
                "world_consistency": self.world_consistency,
                "timeline_consistency": self.timeline_consistency,
                "spatial_consistency": self.spatial_consistency,
                "foreshadowing_integrity": self.foreshadowing_integrity,
            },
            "overall_score": self.overall_score,
            "weights": self.WEIGHTS,
            "dimension_details": {k: v.to_dict() for k, v in self.dimension_details.items()},
            "weak_dimensions": self.get_weak_dimensions(),
            "created_at": self.created_at,
        }

    def to_report(self) -> str:
        """生成可读的文本报告.

        Returns:
            格式化的中文评分报告
        """
        lines = [
            f"【第{self.chapter_number}章连贯性评分报告】",
            "",
            "=== 维度评分 ===",
        ]

        scores = {
            "plot_coherence": self.plot_coherence,
            "character_consistency": self.character_consistency,
            "world_consistency": self.world_consistency,
            "timeline_consistency": self.timeline_consistency,
            "spatial_consistency": self.spatial_consistency,
            "foreshadowing_integrity": self.foreshadowing_integrity,
        }

        for dim, score in scores.items():
            name = self.DIMENSION_NAMES.get(dim, dim)
            weight = self.WEIGHTS.get(dim, 0.0)
            lines.append(f"- {name}: {score:.1f}/10 (权重 {weight:.0%})")

        lines.extend(
            [
                "",
                f"=== 加权总分: {self.overall_score:.2f}/10 ===",
            ]
        )

        weak = self.get_weak_dimensions()
        if weak:
            lines.extend(
                [
                    "",
                    "=== 薄弱维度 ===",
                ]
            )
            for dim in weak:
                name = self.DIMENSION_NAMES.get(dim, dim)
                detail = self.dimension_details.get(dim)
                lines.append(f"- {name}")
                if detail and detail.issues:
                    for issue in detail.issues[:3]:
                        lines.append(f"  • {issue.get('description', str(issue))}")
                if detail and detail.suggestions:
                    lines.append(f"  建议: {detail.suggestions[0]}")
        else:
            lines.append("\n所有维度均达标，无明显薄弱项。")

        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoherenceScorecard":
        """从字典创建.

        Args:
            data: 包含评分卡数据的字典

        Returns:
            CoherenceScorecard 实例
        """
        scores = data.get("scores", {})
        dimension_details = {
            k: DimensionDetail.from_dict(v) for k, v in data.get("dimension_details", {}).items()
        }

        return cls(
            chapter_number=data.get("chapter_number", 0),
            plot_coherence=scores.get("plot_coherence", 0.0),
            character_consistency=scores.get("character_consistency", 0.0),
            world_consistency=scores.get("world_consistency", 0.0),
            timeline_consistency=scores.get("timeline_consistency", 0.0),
            spatial_consistency=scores.get("spatial_consistency", 0.0),
            foreshadowing_integrity=scores.get("foreshadowing_integrity", 0.0),
            dimension_details=dimension_details,
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


class CoherenceScorecardBuilder:
    """
    连贯性评分卡构建器.

    从各检查器结果中提取并汇聚分数，构建统一的评分卡。

    支持的输入类型：
    - review_result: ReviewLoopHandler 的审查结果
    - continuity_result: ContinuityIntegrationResult 对象或字典
    - character_validations: 角色验证结果字典
    - timeline_report: TimelineValidationReport 对象或字典
    - foreshadowing_report: ForeshadowingReport 对象或字典
    - world_review_result: 世界观审查结果字典
    - spatial_issues: 空间问题列表

    使用示例：
        builder = CoherenceScorecardBuilder()
        scorecard = builder.build_scorecard(
            chapter_number=1,
            review_result=review_result,
            continuity_result=continuity_result,
        )
    """

    # 默认分数（无数据时使用）
    DEFAULT_SCORE: float = 7.0

    def __init__(self):
        """初始化构建器."""
        self.logger = logger

    def build_scorecard(
        self,
        chapter_number: int,
        review_result: Optional[Dict[str, Any]] = None,
        continuity_result: Optional[Any] = None,
        character_validations: Optional[Dict[str, Any]] = None,
        timeline_report: Optional[Any] = None,
        foreshadowing_report: Optional[Any] = None,
        world_review_result: Optional[Dict[str, Any]] = None,
        spatial_issues: Optional[List[Any]] = None,
    ) -> CoherenceScorecard:
        """从各检查器结果构建评分卡.

        Args:
            chapter_number: 章节号
            review_result: ReviewLoopHandler 的审查结果，包含多维度评分
            continuity_result: ContinuityIntegrationResult 对象或字典
            character_validations: 角色验证结果 Dict[角色名, ConsistencyValidation]
            timeline_report: TimelineValidationReport 对象或字典
            foreshadowing_report: ForeshadowingReport 对象或字典
            world_review_result: 世界观审查结果字典
            spatial_issues: 空间问题列表

        Returns:
            构建好的 CoherenceScorecard 实例
        """
        self.logger.info(f"开始构建第{chapter_number}章连贯性评分卡")

        # 提取各维度分数
        plot_score, plot_detail = self._extract_plot_score(review_result, continuity_result)
        char_score, char_detail = self._extract_character_score(character_validations)
        world_score, world_detail = self._extract_world_score(
            world_review_result, continuity_result
        )
        timeline_score, timeline_detail = self._extract_timeline_score(timeline_report)
        spatial_score, spatial_detail = self._extract_spatial_score(spatial_issues)
        foreshadow_score, foreshadow_detail = self._extract_foreshadowing_score(
            foreshadowing_report
        )

        # 构建评分卡
        scorecard = CoherenceScorecard(
            chapter_number=chapter_number,
            plot_coherence=plot_score,
            character_consistency=char_score,
            world_consistency=world_score,
            timeline_consistency=timeline_score,
            spatial_consistency=spatial_score,
            foreshadowing_integrity=foreshadow_score,
            dimension_details={
                "plot_coherence": plot_detail,
                "character_consistency": char_detail,
                "world_consistency": world_detail,
                "timeline_consistency": timeline_detail,
                "spatial_consistency": spatial_detail,
                "foreshadowing_integrity": foreshadow_detail,
            },
        )

        self.logger.info(f"第{chapter_number}章评分卡构建完成，总分: {scorecard.overall_score:.2f}")
        return scorecard

    def _extract_plot_score(
        self,
        review_result: Optional[Dict[str, Any]],
        continuity_result: Optional[Any],
    ) -> Tuple[float, DimensionDetail]:
        """从审查结果提取情节连贯性分数.

        优先从 review_result 的维度评分中提取，其次从 continuity_result 提取。

        Args:
            review_result: 审查结果字典
            continuity_result: 连贯性集成结果

        Returns:
            (分数, 维度详情) 元组
        """
        score = self.DEFAULT_SCORE
        issues: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        evidence: List[str] = []

        # 尝试从 review_result 提取
        if review_result:
            # 从维度评分中提取情节相关分数
            dim_scores = review_result.get("dimension_scores", {})
            if dim_scores:
                # 情节逻辑分数
                plot_logic = dim_scores.get("plot_logic", 0.0)
                # 伏笔分数也可作为参考
                foreshadow = dim_scores.get("foreshadowing", 0.0)
                if plot_logic > 0:
                    score = plot_logic
                    evidence.append(f"情节逻辑评分: {plot_logic:.1f}")
                if foreshadow > 0:
                    evidence.append(f"伏笔设计评分: {foreshadow:.1f}")

            # 提取问题
            critical_issues = review_result.get("critical_issues", [])
            for issue in critical_issues:
                area = issue.get("area", "")
                if any(kw in area.lower() for kw in ["情节", "plot", "逻辑", "logic"]):
                    issues.append(issue)
                    if issue.get("suggestion"):
                        suggestions.append(issue["suggestion"])

            # 使用最终评分
            final_score = review_result.get("final_score", 0.0)
            if final_score > 0 and score == self.DEFAULT_SCORE:
                score = final_score / 10.0 if final_score > 10 else final_score
                evidence.append(f"审查最终评分: {final_score:.1f}")

        # 尝试从 continuity_result 提取
        if continuity_result:
            cont_dict = self._to_dict(continuity_result)
            quality_score = cont_dict.get("quality_score", 0.0)
            if quality_score > 0:
                # 转换为 0-10 分制
                normalized = quality_score / 10.0 if quality_score > 10 else quality_score
                if score == self.DEFAULT_SCORE:
                    score = normalized
                evidence.append(f"连贯性质量评分: {quality_score:.1f}")

            # 提取约束违反问题
            constraints = cont_dict.get("constraints_applied", 0)
            if constraints > 0:
                evidence.append(f"应用了 {constraints} 个连贯性约束")

        return score, DimensionDetail(
            score=score, issues=issues, suggestions=suggestions, evidence=evidence
        )

    def _extract_character_score(
        self,
        character_validations: Optional[Dict[str, Any]],
    ) -> Tuple[float, DimensionDetail]:
        """从角色验证结果提取角色一致性分数.

        Args:
            character_validations: 角色验证结果字典

        Returns:
            (分数, 维度详情) 元组
        """
        score = self.DEFAULT_SCORE
        issues: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        evidence: List[str] = []

        if not character_validations:
            evidence.append("无角色验证数据，使用默认分数")
            return score, DimensionDetail(
                score=score, issues=issues, suggestions=suggestions, evidence=evidence
            )

        # 统计验证结果
        total_characters = len(character_validations)
        consistent_count = 0
        issue_count = 0

        for char_name, validation in character_validations.items():
            val_dict = self._to_dict(validation)

            # 检查一致性
            is_consistent = val_dict.get("is_consistent", True)
            if is_consistent:
                consistent_count += 1
            else:
                issue_count += 1
                # 提取问题详情
                inconsistencies = val_dict.get("inconsistencies", [])
                for inc in inconsistencies:
                    issues.append(
                        {
                            "character": char_name,
                            "description": inc.get("description", str(inc)),
                            "severity": inc.get("severity", "medium"),
                        }
                    )
                    if inc.get("suggestion"):
                        suggestions.append(f"[{char_name}] {inc['suggestion']}")

        # 计算分数
        if total_characters > 0:
            consistency_rate = consistent_count / total_characters
            # 一致性率映射到 0-10 分
            score = consistency_rate * 10.0
            evidence.append(
                f"角色一致性率: {consistency_rate:.1%} " f"({consistent_count}/{total_characters})"
            )

        if issue_count > 0:
            evidence.append(f"发现 {issue_count} 个角色一致性问题")

        return score, DimensionDetail(
            score=score, issues=issues, suggestions=suggestions, evidence=evidence
        )

    def _extract_world_score(
        self,
        world_review_result: Optional[Dict[str, Any]],
        continuity_result: Optional[Any],
    ) -> Tuple[float, DimensionDetail]:
        """从世界观审查结果提取世界观一致性分数.

        Args:
            world_review_result: 世界观审查结果字典
            continuity_result: 连贯性集成结果

        Returns:
            (分数, 维度详情) 元组
        """
        score = self.DEFAULT_SCORE
        issues: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        evidence: List[str] = []

        # 优先从 world_review_result 提取
        if world_review_result:
            # 提取总分
            overall = world_review_result.get("overall_score", 0.0)
            if overall > 0:
                score = overall
                evidence.append(f"世界观审查总分: {overall:.1f}")

            # 提取维度评分
            dim_scores = world_review_result.get("dimension_scores", {})
            if dim_scores:
                # 设定一致性分数
                setting_score = dim_scores.get("setting_consistency", 0.0)
                if setting_score > 0:
                    evidence.append(f"设定一致性评分: {setting_score:.1f}")

            # 提取问题
            for issue in world_review_result.get("issues", []):
                area = issue.get("area", "")
                if any(kw in area.lower() for kw in ["世界", "world", "设定", "setting"]):
                    issues.append(issue)
                    if issue.get("suggestion"):
                        suggestions.append(issue["suggestion"])

        # 从 continuity_result 补充
        if continuity_result:
            cont_dict = self._to_dict(continuity_result)
            validation_report = cont_dict.get("validation_report", {})
            if validation_report:
                # 检查是否有设定相关问题
                unsatisfied = validation_report.get("unsatisfied_constraints", [])
                for constraint in unsatisfied:
                    if "设定" in constraint.get("description", ""):
                        issues.append(
                            {
                                "description": constraint.get("description", ""),
                                "severity": "medium",
                            }
                        )

        if not evidence:
            evidence.append("无世界观审查数据，使用默认分数")

        return score, DimensionDetail(
            score=score, issues=issues, suggestions=suggestions, evidence=evidence
        )

    def _extract_timeline_score(
        self,
        timeline_report: Optional[Any],
    ) -> Tuple[float, DimensionDetail]:
        """从时间线报告提取时间线一致性分数.

        Args:
            timeline_report: TimelineValidationReport 对象或字典

        Returns:
            (分数, 维度详情) 元组
        """
        score = self.DEFAULT_SCORE
        issues: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        evidence: List[str] = []

        if not timeline_report:
            evidence.append("无时间线验证数据，使用默认分数")
            return score, DimensionDetail(
                score=score, issues=issues, suggestions=suggestions, evidence=evidence
            )

        report_dict = self._to_dict(timeline_report)

        # 检查是否有效
        is_valid = report_dict.get("is_valid", True)
        inconsistencies = report_dict.get("inconsistencies", [])

        if is_valid and not inconsistencies:
            score = 10.0
            evidence.append("时间线验证通过，无一致性问题")
        else:
            # 根据问题数量和严重程度计算分数
            high_severity = sum(1 for i in inconsistencies if i.get("severity") == "high")
            medium_severity = sum(1 for i in inconsistencies if i.get("severity") == "medium")
            low_severity = sum(1 for i in inconsistencies if i.get("severity") == "low")

            # 扣分计算
            penalty = high_severity * 3.0 + medium_severity * 1.5 + low_severity * 0.5
            score = max(0.0, 10.0 - penalty)

            evidence.append(
                f"时间线问题: 高严重度 {high_severity}, "
                f"中严重度 {medium_severity}, 低严重度 {low_severity}"
            )

            # 提取问题详情
            for inc in inconsistencies:
                issues.append(
                    {
                        "description": inc.get("description", ""),
                        "severity": inc.get("severity", "medium"),
                        "chapter": inc.get("chapter_number"),
                    }
                )
                if inc.get("suggestion"):
                    suggestions.append(inc["suggestion"])

        # 记录追踪信息
        chapters_tracked = report_dict.get("total_chapters_tracked", 0)
        if chapters_tracked > 0:
            evidence.append(f"已追踪 {chapters_tracked} 个章节的时间线")

        return score, DimensionDetail(
            score=score, issues=issues, suggestions=suggestions, evidence=evidence
        )

    def _extract_spatial_score(
        self,
        spatial_issues: Optional[List[Any]],
    ) -> Tuple[float, DimensionDetail]:
        """从空间问题列表提取空间一致性分数.

        Args:
            spatial_issues: 空间问题列表

        Returns:
            (分数, 维度详情) 元组
        """
        score = self.DEFAULT_SCORE
        issues: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        evidence: List[str] = []

        if not spatial_issues:
            evidence.append("无空间问题数据，使用默认分数")
            return score, DimensionDetail(
                score=score, issues=issues, suggestions=suggestions, evidence=evidence
            )

        # 统计问题
        high_severity = 0
        medium_severity = 0
        low_severity = 0

        for issue in spatial_issues:
            issue_dict = self._to_dict(issue)
            severity = issue_dict.get("severity", "medium")
            if severity == "high":
                high_severity += 1
            elif severity == "medium":
                medium_severity += 1
            else:
                low_severity += 1

            issues.append(
                {
                    "description": issue_dict.get("description", str(issue)),
                    "severity": severity,
                }
            )
            if issue_dict.get("suggestion"):
                suggestions.append(issue_dict["suggestion"])

        # 计算分数
        total_issues = len(spatial_issues)
        if total_issues == 0:
            score = 10.0
            evidence.append("无空间一致性问题")
        else:
            penalty = high_severity * 3.0 + medium_severity * 1.5 + low_severity * 0.5
            score = max(0.0, 10.0 - penalty)
            evidence.append(
                f"空间问题: 高严重度 {high_severity}, "
                f"中严重度 {medium_severity}, 低严重度 {low_severity}"
            )

        return score, DimensionDetail(
            score=score, issues=issues, suggestions=suggestions, evidence=evidence
        )

    def _extract_foreshadowing_score(
        self,
        foreshadowing_report: Optional[Any],
    ) -> Tuple[float, DimensionDetail]:
        """从伏笔报告提取伏笔完整性分数.

        Args:
            foreshadowing_report: ForeshadowingReport 对象或字典

        Returns:
            (分数, 维度详情) 元组
        """
        score = self.DEFAULT_SCORE
        issues: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        evidence: List[str] = []

        if not foreshadowing_report:
            evidence.append("无伏笔报告数据，使用默认分数")
            return score, DimensionDetail(
                score=score, issues=issues, suggestions=suggestions, evidence=evidence
            )

        report_dict = self._to_dict(foreshadowing_report)

        # 提取统计信息
        statistics = report_dict.get("statistics", {})
        if statistics:
            total = statistics.get("total", 0)
            resolved = statistics.get("resolved", 0)
            pending = statistics.get("pending", 0)
            abandoned = statistics.get("abandoned", 0)
            resolution_rate = statistics.get("resolution_rate", 0.0)

            if total > 0:
                # 基于回收率计算分数
                score = resolution_rate * 10.0
                evidence.append(
                    f"伏笔统计: 总计 {total}, 已回收 {resolved}, "
                    f"待回收 {pending}, 已放弃 {abandoned}"
                )
                evidence.append(f"回收率: {resolution_rate:.1%}")

                # 检查超期伏笔
                overdue = report_dict.get("overdue_foreshadowings", [])
                if overdue:
                    issues.append(
                        {
                            "description": f"有 {len(overdue)} 个伏笔超期未回收",
                            "severity": "medium",
                        }
                    )
                    suggestions.append("建议优先处理超期未回收的伏笔")

        # 从待回收伏笔提取建议
        pending_list = report_dict.get("pending_foreshadowings", [])
        high_importance_pending = [f for f in pending_list if f.get("importance", 0) >= 7]
        if high_importance_pending:
            issues.append(
                {
                    "description": f"有 {len(high_importance_pending)} 个高重要性伏笔待回收",
                    "severity": "low",
                }
            )

        return score, DimensionDetail(
            score=score, issues=issues, suggestions=suggestions, evidence=evidence
        )

    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        """将对象转换为字典.

        支持字典、有 to_dict 方法的对象、以及 Pydantic 模型。

        Args:
            obj: 任意对象

        Returns:
            字典表示
        """
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "to_dict"):
            return cast(Dict[str, Any], obj.to_dict())
        if hasattr(obj, "model_dump"):
            return cast(Dict[str, Any], obj.model_dump())
        if hasattr(obj, "__dict__"):
            return cast(Dict[str, Any], obj.__dict__)
        return {}

    def compare_scorecards(self, cards: List[CoherenceScorecard]) -> TrendReport:
        """跨章节趋势分析.

        分析多个评分卡的变化趋势，识别改进和退步的维度。

        Args:
            cards: 评分卡列表，按章节顺序排列

        Returns:
            TrendReport 趋势报告
        """
        if len(cards) < 2:
            self.logger.warning("评分卡数量不足，无法进行趋势分析")
            return TrendReport(
                chapter_range=(cards[0].chapter_number, cards[0].chapter_number)
                if cards
                else (0, 0),
                analysis="评分卡数量不足，无法进行趋势分析",
            )

        # 按章节号排序
        sorted_cards = sorted(cards, key=lambda c: c.chapter_number)

        # 收集各维度分数趋势
        dimension_trends: Dict[str, List[float]] = {
            dim: [] for dim in CoherenceScorecard.WEIGHTS.keys()
        }
        overall_trend: List[float] = []

        for card in sorted_cards:
            dimension_trends["plot_coherence"].append(card.plot_coherence)
            dimension_trends["character_consistency"].append(card.character_consistency)
            dimension_trends["world_consistency"].append(card.world_consistency)
            dimension_trends["timeline_consistency"].append(card.timeline_consistency)
            dimension_trends["spatial_consistency"].append(card.spatial_consistency)
            dimension_trends["foreshadowing_integrity"].append(card.foreshadowing_integrity)
            overall_trend.append(card.overall_score)

        # 分析趋势方向
        improving: List[str] = []
        declining: List[str] = []

        for dim, scores in dimension_trends.items():
            if len(scores) >= 2:
                # 计算变化趋势：比较后半段和前半段平均值
                mid = len(scores) // 2
                first_half_avg = sum(scores[:mid]) / mid if mid > 0 else scores[0]
                second_half_avg = sum(scores[mid:]) / (len(scores) - mid)

                # 变化超过 0.5 分视为显著变化
                if second_half_avg - first_half_avg > 0.5:
                    improving.append(dim)
                elif first_half_avg - second_half_avg > 0.5:
                    declining.append(dim)

        # 生成分析文本
        analysis_lines = [
            f"分析范围：第{sorted_cards[0].chapter_number}章 "
            f"至 第{sorted_cards[-1].chapter_number}章",
            f"总章节数：{len(sorted_cards)}",
            "",
            "=== 总分趋势 ===",
        ]

        if overall_trend:
            first_score = overall_trend[0]
            last_score = overall_trend[-1]
            change = last_score - first_score
            direction = "上升" if change > 0 else "下降" if change < 0 else "稳定"
            analysis_lines.append(
                f"总分从 {first_score:.2f} {direction}至 {last_score:.2f} " f"(变化 {change:+.2f})"
            )

        if improving:
            analysis_lines.extend(
                [
                    "",
                    "=== 改进维度 ===",
                ]
            )
            for dim in improving:
                name = CoherenceScorecard.DIMENSION_NAMES.get(dim, dim)
                scores = dimension_trends[dim]
                analysis_lines.append(f"- {name}: {scores[0]:.1f} → {scores[-1]:.1f}")

        if declining:
            analysis_lines.extend(
                [
                    "",
                    "=== 退步维度 ===",
                ]
            )
            for dim in declining:
                name = CoherenceScorecard.DIMENSION_NAMES.get(dim, dim)
                scores = dimension_trends[dim]
                analysis_lines.append(f"- {name}: {scores[0]:.1f} → {scores[-1]:.1f}")

        trend_report = TrendReport(
            chapter_range=(sorted_cards[0].chapter_number, sorted_cards[-1].chapter_number),
            dimension_trends=dimension_trends,
            overall_trend=overall_trend,
            improving_dimensions=improving,
            declining_dimensions=declining,
            analysis="\n".join(analysis_lines),
        )

        self.logger.info(f"趋势分析完成: 改进 {len(improving)} 项, 退步 {len(declining)} 项")
        return trend_report
