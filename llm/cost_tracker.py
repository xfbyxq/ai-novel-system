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

    def record(
        self,
        agent_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> dict:
        """记录一次 API 调用的 token 使用量并计算成本。"""
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
        }
        self.records.append(record)

        logger.info(
            f"[CostTracker] {agent_name}: {prompt_tokens}+{completion_tokens} tokens, "
            f"cost=¥{cost:.4f}, cumulative=¥{self.total_cost:.4f}"
        )
        return record

    def get_summary(self) -> dict:
        """获取成本汇总。"""
        return {
            "model": self.model,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost": float(self.total_cost),
            "call_count": len(self.records),
        }

    def reset(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = Decimal("0")
        self.records.clear()
