"""活动日志记录器 - 记录规划活动日志."""

from typing import TYPE_CHECKING
from uuid import UUID

from core.logging_config import logger

if TYPE_CHECKING:
    from backend.services.agent_activity_recorder import AgentActivityRecorder


class ActivityLogger:
    """活动日志记录器，负责记录 Agent 活动摘要."""

    def __init__(self, activity_recorder: "AgentActivityRecorder"):
        """初始化活动日志记录器.

        Args:
            activity_recorder: Agent 活动记录器
        """
        self.activity_recorder = activity_recorder

    async def record_planning_activities(
        self,
        novel_id: UUID,
        task_id: UUID,
        planning_result: dict,
        cost_summary: dict,
        cost_records: list | None = None,
    ) -> None:
        """记录企划阶段的 Agent 活动摘要.

        Args:
            novel_id: 小说 ID
            task_id: 任务 ID
            planning_result: 企划结果
            cost_summary: 成本摘要
            cost_records: 可选的 token 消耗记录列表，用于按 Agent 分别统计
        """
        try:
            # 从 cost_records 中按 Agent 提取 token 消耗
            agent_costs = {}
            if cost_records:
                for record in cost_records:
                    agent_name = record.get("agent_name", "")
                    if agent_name not in agent_costs:
                        agent_costs[agent_name] = {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "cost": 0,
                        }
                    agent_costs[agent_name]["prompt_tokens"] += record.get("prompt_tokens", 0)
                    agent_costs[agent_name]["completion_tokens"] += record.get(
                        "completion_tokens", 0
                    )
                    agent_costs[agent_name]["total_tokens"] += record.get("total_tokens", 0)
                    agent_costs[agent_name]["cost"] += record.get("cost", 0)

            # 辅助函数：获取 Agent 的 token 消耗
            def get_agent_cost(agent_name: str) -> tuple[int, float]:
                if agent_name in agent_costs:
                    c = agent_costs[agent_name]
                    return c["total_tokens"], c["cost"]
                return 0, 0

            # 记录主题分析活动
            if "topic_analysis" in planning_result:
                tokens, cost = get_agent_cost("主题分析师")
                # 如果没找到，尝试从总成本中分配（兼容旧数据）
                if tokens == 0 and cost_summary.get("total_tokens", 0) > 0:
                    tokens = cost_summary.get("total_tokens", 0)
                    cost = cost_summary.get("total_cost", 0)
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="主题分析师",
                    agent_role="市场趋势分析和选题推荐",
                    activity_subtype="topic_analysis",
                    input_data={"genre": planning_result.get("genre")},
                    output_data=planning_result.get("topic_analysis", {}),
                    total_tokens=tokens,
                    cost=cost,
                )

            # 记录世界观构建活动
            if "world_setting" in planning_result:
                tokens, cost = get_agent_cost("世界观架构师")
                # 尝试多个可能的 Agent 名称
                if tokens == 0:
                    for name in ["世界观审查员", "世界观察审查员"]:
                        if name in agent_costs:
                            tokens, cost = get_agent_cost(name)
                            break
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="世界观架构师",
                    agent_role="世界观体系构建",
                    activity_subtype="world_building",
                    input_data={"topic_analysis": planning_result.get("topic_analysis")},
                    output_data=planning_result.get("world_setting", {}),
                    total_tokens=tokens,
                    cost=cost,
                )

            # 记录角色设计活动
            if "characters" in planning_result:
                tokens, cost = get_agent_cost("角色设计师")
                if tokens == 0:
                    for name in ["角色审查员", "角色审查"]:
                        if name in agent_costs:
                            tokens, cost = get_agent_cost(name)
                            break
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="角色设计师",
                    agent_role="主要角色设计",
                    activity_subtype="character_design",
                    input_data={"world_setting": planning_result.get("world_setting")},
                    output_data={"characters_count": len(planning_result.get("characters", []))},
                    total_tokens=tokens,
                    cost=cost,
                )

            # 记录情节架构活动
            if "plot_outline" in planning_result:
                tokens, cost = get_agent_cost("情节架构师")
                if tokens == 0:
                    for name in ["大纲审查员", "情节审查员", "PlotReview"]:
                        if name in agent_costs:
                            tokens, cost = get_agent_cost(name)
                            break
                await self.activity_recorder.record_planning_activity(
                    novel_id=novel_id,
                    task_id=task_id,
                    agent_name="情节架构师",
                    agent_role="整体情节架构规划",
                    activity_subtype="plot_architecture",
                    input_data={
                        "world_setting": planning_result.get("world_setting"),
                        "characters": planning_result.get("characters"),
                    },
                    output_data={
                        "structure_type": planning_result.get("plot_outline", {}).get(
                            "structure_type"
                        ),
                        "volumes_count": len(
                            planning_result.get("plot_outline", {}).get("volumes", [])
                        ),
                    },
                    total_tokens=tokens,
                    cost=cost,
                )

            logger.info("✅ 企划阶段 Agent 活动记录完成")
        except Exception as e:
            logger.error(f"记录企划阶段 Agent 活动失败：{e}")
