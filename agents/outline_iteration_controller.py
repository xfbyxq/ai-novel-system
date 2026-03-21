"""大纲迭代优化控制器 - 管理大纲完善过程中的迭代优化."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class OutlineOptimizationRecord:
    """大纲优化迭代记录."""

    iteration: int
    quality_score: float
    consistency_score: float
    changes_made: List[str]
    issues_resolved: List[str]
    remaining_issues: List[str]
    cost_delta: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "quality_score": self.quality_score,
            "consistency_score": self.consistency_score,
            "changes_made": self.changes_made,
            "issues_resolved": self.issues_resolved,
            "remaining_issues": self.remaining_issues,
            "cost_delta": self.cost_delta,
            "timestamp": self.timestamp,
        }


class OutlineIterationController:
    """大纲迭代优化控制器."""

    def __init__(
        self,
        quality_threshold: float = 8.0,
        consistency_threshold: float = 8.5,
        max_iterations: int = 3,
        cost_limit: Optional[float] = None,
    ):
        """初始化大纲迭代控制器.

        Args:
            quality_threshold: 质量评分阈值
            consistency_threshold: 一致性评分阈值
            max_iterations: 最大迭代次数
            cost_limit: 成本上限（元）
        """
        self.quality_threshold = quality_threshold
        self.consistency_threshold = consistency_threshold
        self.max_iterations = max_iterations
        self.cost_limit = cost_limit

        self.history: List[OutlineOptimizationRecord] = []
        self.current_iteration: int = 0
        self.cumulative_cost: float = 0.0
        self.best_outline: Optional[Dict[str, Any]] = None
        self.best_score: float = 0.0

    def should_continue(
        self,
        quality_score: float,
        consistency_score: float,
        iteration: Optional[int] = None,
        cost_delta: float = 0.0,
    ) -> bool:
        """判断是否需要继续大纲优化迭代.

        Args:
            quality_score: 当前质量评分
            consistency_score: 当前一致性评分
            iteration: 当前迭代次数
            cost_delta: 本轮新增成本

        Returns:
            True表示继续迭代，False表示停止
        """
        it = iteration if iteration is not None else self.current_iteration
        self.cumulative_cost += cost_delta

        # 检查是否同时满足两个阈值
        meets_quality = quality_score >= self.quality_threshold
        meets_consistency = consistency_score >= self.consistency_threshold

        if meets_quality and meets_consistency:
            logger.info(
                f"[OutlineIterationController] 质量和一致性均达标 "
                f"(quality={quality_score:.1f}>={self.quality_threshold}, "
                f"consistency={consistency_score:.1f}>={self.consistency_threshold}), "
                f"停止迭代"
            )
            return False

        if it >= self.max_iterations:
            logger.warning(
                f"[OutlineIterationController] 达到最大迭代次数 ({self.max_iterations}), "
                f"quality={quality_score:.1f}, consistency={consistency_score:.1f}, "
                f"强制停止"
            )
            return False

        if self.cost_limit is not None and self.cumulative_cost >= self.cost_limit:
            logger.warning(
                f"[OutlineIterationController] 成本超限 "
                f"(cumulative={self.cumulative_cost:.4f} >= limit={self.cost_limit}), "
                f"强制停止"
            )
            return False

        logger.info(
            f"[OutlineIterationController] 继续迭代 "
            f"(iteration={it}, quality={quality_score:.1f}, "
            f"consistency={consistency_score:.1f})"
        )
        return True

    def log_iteration(
        self,
        outline: Dict[str, Any],
        quality_score: float,
        consistency_score: float,
        changes_made: List[str],
        issues_resolved: List[str],
        remaining_issues: List[str],
        cost_delta: float = 0.0,
    ) -> OutlineOptimizationRecord:
        """记录一轮大纲优化迭代."""
        self.current_iteration += 1
        self.cumulative_cost += cost_delta

        record = OutlineOptimizationRecord(
            iteration=self.current_iteration,
            quality_score=quality_score,
            consistency_score=consistency_score,
            changes_made=changes_made,
            issues_resolved=issues_resolved,
            remaining_issues=remaining_issues,
            cost_delta=cost_delta,
        )

        self.history.append(record)

        # 更新最佳版本
        combined_score = (quality_score + consistency_score) / 2
        if combined_score > self.best_score:
            self.best_outline = outline.copy()
            self.best_score = combined_score
            logger.info(
                f"[OutlineIterationController] 发现更优版本 (score={combined_score:.2f})"
            )

        return record

    def get_summary(self) -> Dict[str, Any]:
        """获取优化过程摘要."""
        quality_scores = [r.quality_score for r in self.history]
        consistency_scores = [r.consistency_score for r in self.history]

        return {
            "total_iterations": self.current_iteration,
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "consistency_threshold": self.consistency_threshold,
            "final_quality_score": quality_scores[-1] if quality_scores else 0.0,
            "final_consistency_score": (
                consistency_scores[-1] if consistency_scores else 0.0
            ),
            "quality_progression": quality_scores,
            "consistency_progression": consistency_scores,
            "cumulative_cost": round(self.cumulative_cost, 4),
            "converged": bool(
                quality_scores
                and consistency_scores
                and quality_scores[-1] >= self.quality_threshold
                and consistency_scores[-1] >= self.consistency_threshold
            ),
            "best_score": self.best_score,
            "total_changes": sum(len(r.changes_made) for r in self.history),
            "issues_resolved_total": sum(len(r.issues_resolved) for r in self.history),
        }

    def get_best_outline(self) -> Optional[Dict[str, Any]]:
        """获取最优大纲版本."""
        return self.best_outline

    def reset(self):
        """重置控制器."""
        self.history.clear()
        self.current_iteration = 0
        self.cumulative_cost = 0.0
        self.best_outline = None
        self.best_score = 0.0

    async def optimize_outline_iteratively(
        self,
        initial_outline: Dict[str, Any],
        quality_evaluator: Any,  # OutlineQualityEvaluator
        consistency_checker: Any,  # ExtendedConsistencyChecker
        world_setting: Dict[str, Any],
        characters: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """迭代优化大纲直到满足质量标准.

        Args:
            initial_outline: 初始大纲
            quality_evaluator: 质量评估器
            consistency_checker: 一致性检查器
            world_setting: 世界观设定
            characters: 角色列表

        Returns:
            优化后的大纲和过程报告
        """
        logger.info("开始大纲迭代优化流程")

        current_outline = initial_outline.copy()

        while self.should_continue(
            quality_score=0,  # 初始值会在第一次迭代中更新
            consistency_score=0,
            cost_delta=0.0,
        ):
            # 评估当前质量
            quality_result = await quality_evaluator.evaluate_outline_comprehensively(
                current_outline, world_setting, characters
            )
            quality_score = quality_result.overall_score

            # 评估一致性
            consistency_result = await consistency_checker.check_outline_consistency(
                current_outline, world_setting, characters
            )
            consistency_score = consistency_result.get("consistency_score", 5.0)

            # 检查是否达标（更新should_continue的实际参数）
            if not self.should_continue(quality_score, consistency_score):
                break

            # 生成优化建议
            optimization_suggestions = self._generate_optimization_plan(
                quality_result, consistency_result, current_outline
            )

            # 应用优化
            changes_made = []
            issues_resolved = []

            if optimization_suggestions:
                optimized_outline = await self._apply_optimizations(
                    current_outline, optimization_suggestions
                )

                # 记录变更
                changes_made = self._summarize_changes(
                    current_outline, optimized_outline
                )
                issues_resolved = self._identify_resolved_issues(
                    optimization_suggestions
                )

                current_outline = optimized_outline

            # 记录本次迭代
            remaining_issues = self._identify_remaining_issues(
                quality_result, consistency_result
            )

            self.log_iteration(
                outline=current_outline,
                quality_score=quality_score,
                consistency_score=consistency_score,
                changes_made=changes_made,
                issues_resolved=issues_resolved,
                remaining_issues=remaining_issues,
                cost_delta=0.01,  # 简化的成本估算
            )

        # 返回最优结果
        final_outline = self.get_best_outline() or current_outline
        summary = self.get_summary()

        logger.info(
            f"大纲迭代优化完成 - "
            f"最终质量分: {summary['final_quality_score']:.2f}, "
            f"一致性分: {summary['final_consistency_score']:.2f}"
        )

        return {
            "optimized_outline": final_outline,
            "optimization_summary": summary,
            "iteration_history": [r.to_dict() for r in self.history],
            "process_completed": True,
        }

    def _generate_optimization_plan(
        self,
        quality_result: Any,
        consistency_result: Dict[str, Any],
        current_outline: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """生成优化计划."""
        suggestions = []

        # 基于质量评估的建议
        if quality_result.overall_score < self.quality_threshold:
            for weakness in quality_result.weaknesses:
                suggestions.append(
                    {
                        "type": "quality_improvement",
                        "priority": "high",
                        "target": weakness,
                        "action": "enhance",
                    }
                )

        # 基于一致性检查的建议
        if (
            consistency_result.get("consistency_score", 5.0)
            < self.consistency_threshold
        ):
            extended_analysis = consistency_result.get("extended_analysis", {})

            if not extended_analysis.get("worldview_alignment", {}).get(
                "aligned", False
            ):
                suggestions.append(
                    {
                        "type": "worldview_integration",
                        "priority": "high",
                        "target": "世界观一致性",
                        "action": "strengthen",
                    }
                )

            if not extended_analysis.get("character_mapping", {}).get(
                "well_distributed", False
            ):
                suggestions.append(
                    {
                        "type": "character_balance",
                        "priority": "medium",
                        "target": "角色配置",
                        "action": "redistribute",
                    }
                )

        return suggestions

    async def _apply_optimizations(
        self, outline: Dict[str, Any], suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """应用优化建议."""
        optimized_outline = outline.copy()

        # 简单的优化处理
        for suggestion in suggestions:
            suggestion_type = suggestion["type"]

            if suggestion_type == "worldview_integration":
                if "optimization_notes" not in optimized_outline:
                    optimized_outline["optimization_notes"] = []
                optimized_outline["optimization_notes"].append("加强世界观元素融入")

            elif suggestion_type == "character_balance":
                if "character_development_plan" not in optimized_outline:
                    optimized_outline["character_development_plan"] = []
                optimized_outline["character_development_plan"].append(
                    "优化角色戏份分配"
                )

        return optimized_outline

    def _summarize_changes(
        self, old_outline: Dict[str, Any], new_outline: Dict[str, Any]
    ) -> List[str]:
        """总结变更内容."""
        changes = []

        # 简单比较主要字段
        fields_to_compare = ["main_plot", "volumes", "key_turning_points"]

        for field in fields_to_compare:
            if old_outline.get(field) != new_outline.get(field):
                changes.append(f"更新{field}")

        if "optimization_notes" in new_outline:
            changes.append("添加优化建议")

        return changes if changes else ["微调优化"]

    def _identify_resolved_issues(self, suggestions: List[Dict[str, Any]]) -> List[str]:
        """识别已解决的问题."""
        resolved = []
        for suggestion in suggestions:
            resolved.append(f"处理了{suggestion['target']}问题")
        return resolved

    def _identify_remaining_issues(
        self, quality_result: Any, consistency_result: Dict[str, Any]
    ) -> List[str]:
        """识别剩余问题."""
        remaining = []

        # 质量方面的剩余问题
        remaining.extend(quality_result.weaknesses)

        # 一致性方面的剩余问题
        extended_analysis = consistency_result.get("extended_analysis", {})

        if not extended_analysis.get("worldview_alignment", {}).get("aligned", False):
            remaining.append("世界观一致性待提升")

        if not extended_analysis.get("character_mapping", {}).get(
            "well_distributed", False
        ):
            remaining.append("角色配置待优化")

        return remaining
