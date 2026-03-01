"""Token 使用量和成本追踪"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# 通义千问定价 (元/1000 tokens) - qwen-plus 为例
PRICING = {
    "qwen-plus": {"input": Decimal("0.004"), "output": Decimal("0.012")},
    "qwen-turbo": {"input": Decimal("0.002"), "output": Decimal("0.006")},
    "qwen-max": {"input": Decimal("0.02"), "output": Decimal("0.06")},
}


class CostTracker:
    """追踪 LLM API 调用的 token 使用量和成本。"""

    def __init__(self, model: str = "qwen-plus"):
        self.model = model
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = Decimal("0")
        self.records: list[dict] = []
        # 按章节、按类别追踪成本
        self.chapter_costs: dict[int, dict[str, Decimal]] = {}

    def record(
        self,
        agent_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        chapter_number: int = 0,
        cost_category: str = "base",
    ) -> dict:
        """记录一次 API 调用的 token 使用量并计算成本。

        Args:
            agent_name: Agent 名称
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            chapter_number: 章节号（0 表示非章节维度）
            cost_category: 成本类别 (base/iteration/query/vote)
        """
        pricing = PRICING.get(self.model, PRICING["qwen-plus"])
        cost = (
            Decimal(prompt_tokens) * pricing["input"] / 1000
            + Decimal(completion_tokens) * pricing["output"] / 1000
        )

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost += cost

        record = {
            "agent_name": agent_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": float(cost),
            "chapter_number": chapter_number,
            "cost_category": cost_category,
        }
        self.records.append(record)

        # 按章节追踪
        if chapter_number > 0:
            if chapter_number not in self.chapter_costs:
                self.chapter_costs[chapter_number] = {
                    "base": Decimal("0"),
                    "iteration": Decimal("0"),
                    "query": Decimal("0"),
                    "vote": Decimal("0"),
                }
            category_key = cost_category if cost_category in self.chapter_costs[chapter_number] else "base"
            self.chapter_costs[chapter_number][category_key] += cost

        logger.info(
            f"[CostTracker] {agent_name}: {prompt_tokens}+{completion_tokens} tokens, "
            f"cost=¥{cost:.4f}, cumulative=¥{self.total_cost:.4f}"
        )
        return record

    def get_chapter_cost(self, chapter_number: int) -> float:
        """获取某章的总成本（元）"""
        costs = self.chapter_costs.get(chapter_number, {})
        return float(sum(costs.values()))

    def check_chapter_limit(self, chapter_number: int, limit: float) -> bool:
        """检查某章成本是否超限

        Returns:
            True 表示未超限，False 表示已超限
        """
        return self.get_chapter_cost(chapter_number) < limit

    def get_summary(self) -> dict:
        """获取成本汇总。"""
        chapter_breakdown = {}
        for ch, costs in self.chapter_costs.items():
            chapter_breakdown[ch] = {k: float(v) for k, v in costs.items()}
            chapter_breakdown[ch]["total"] = float(sum(costs.values()))

        return {
            "model": self.model,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost": float(self.total_cost),
            "call_count": len(self.records),
            "chapter_breakdown": chapter_breakdown,
        }

    def reset(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = Decimal("0")
        self.records.clear()
        self.chapter_costs.clear()
