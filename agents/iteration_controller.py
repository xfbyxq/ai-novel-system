"""迭代控制器 - 管理 Agent 间反馈循环的迭代次数与退出条件"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from core.logging_config import logger


@dataclass
class IterationRecord:
    """单轮迭代记录"""

    iteration: int
    score: float
    action: str  # "write" / "revise" / "fix" / "review"
    agent: str
    passed: bool
    cost_delta: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "score": self.score,
            "action": self.action,
            "agent": self.agent,
            "passed": self.passed,
            "cost_delta": self.cost_delta,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class IterationController:
    """控制反馈循环的迭代次数和退出条件

    支持三种退出条件：
    1. 质量达标（score >= threshold）
    2. 达到最大迭代次数
    3. 成本超限
    """

    def __init__(
        self,
        quality_threshold: float = 7.5,
        max_iterations: int = 3,
        cost_limit: Optional[float] = None,
    ):
        """
        Args:
            quality_threshold: 质量阈值，达标即停止迭代
            max_iterations: 最大迭代次数（硬上限）
            cost_limit: 本轮循环的成本上限（元），None 表示不限
        """
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations
        self.cost_limit = cost_limit

        self.history: List[IterationRecord] = []
        self.current_iteration: int = 0
        self.cumulative_cost: float = 0.0

    def should_continue(
        self,
        score: float,
        iteration: Optional[int] = None,
        cost_delta: float = 0.0,
    ) -> bool:
        """判断是否需要继续迭代

        Args:
            score: 当前迭代的质量分数
            iteration: 当前迭代次数（不传则使用内部计数）
            cost_delta: 本轮新增成本

        Returns:
            True 表示应继续迭代，False 表示应停止
        """
        it = iteration if iteration is not None else self.current_iteration
        self.cumulative_cost += cost_delta

        if score >= self.quality_threshold:
            logger.info(
                f"[IterationController] 质量达标 "
                f"(score={score:.1f} >= threshold={self.quality_threshold}), 停止迭代"
            )
            return False

        if it >= self.max_iterations:
            logger.warning(
                f"[IterationController] 达到最大迭代次数 ({self.max_iterations}), "
                f"当前 score={score:.1f}, 强制停止"
            )
            return False

        if self.cost_limit is not None and self.cumulative_cost >= self.cost_limit:
            logger.warning(
                f"[IterationController] 成本超限 "
                f"(cumulative={self.cumulative_cost:.4f} >= limit={self.cost_limit}), "
                f"当前 score={score:.1f}, 强制停止"
            )
            return False

        logger.info(
            f"[IterationController] 继续迭代 "
            f"(iteration={it}, score={score:.1f}, threshold={self.quality_threshold})"
        )
        return True

    def log_iteration(
        self,
        score: float,
        action: str,
        agent: str,
        passed: bool,
        cost_delta: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> IterationRecord:
        """记录一轮迭代"""
        self.current_iteration += 1
        self.cumulative_cost += cost_delta
        record = IterationRecord(
            iteration=self.current_iteration,
            score=score,
            action=action,
            agent=agent,
            passed=passed,
            cost_delta=cost_delta,
            details=details or {},
        )
        self.history.append(record)
        return record

    def get_summary(self) -> Dict[str, Any]:
        """获取迭代摘要"""
        scores = [r.score for r in self.history if r.score > 0]
        return {
            "total_iterations": self.current_iteration,
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "final_score": scores[-1] if scores else 0.0,
            "score_progression": scores,
            "cumulative_cost": round(self.cumulative_cost, 4),
            "converged": bool(scores and scores[-1] >= self.quality_threshold),
        }

    def reset(self):
        """重置控制器（用于下一章）"""
        self.history.clear()
        self.current_iteration = 0
        self.cumulative_cost = 0.0
