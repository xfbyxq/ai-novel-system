"""Agent 活动记录器 - 用于记录和管理 Agent 的详细活动"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import logger
from core.models.agent_activity import AgentActivity


class AgentActivityRecorder:
    """
    Agent 活动记录器

    用于记录 Agent 执行过程中的详细活动，包括：
    - 输入输出数据
    - Token 使用统计
    - 成本信息
    - 审查循环详情
    - 投票详情
    - 查询处理
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_activity(
        self,
        novel_id: UUID,
        task_id: UUID,
        agent_name: str,
        activity_type: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        raw_output: Optional[str] = None,
        agent_role: Optional[str] = None,
        phase: Optional[str] = None,
        step_number: Optional[int] = None,
        iteration_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        cost: float = 0,
        status: str = "success",
        error_message: Optional[str] = None,
        retry_count: int = 0,
    ) -> AgentActivity:
        """
        记录 Agent 活动

        Args:
            novel_id: 小说 ID
            task_id: 任务 ID
            agent_name: Agent 名称
            activity_type: 活动类型
            input_data: 输入数据
            output_data: 输出数据
            raw_output: 原始输出（非结构化）
            agent_role: Agent 角色描述
            phase: 所属阶段
            step_number: 步骤序号
            iteration_number: 迭代轮次
            metadata: 元数据
            prompt_tokens: 提示词 token 数
            completion_tokens: 完成 token 数
            total_tokens: 总 token 数
            cost: 成本
            status: 状态（success/failed/retry）
            error_message: 错误信息
            retry_count: 重试次数

        Returns:
            AgentActivity 实例
        """
        activity = AgentActivity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name=agent_name,
            agent_role=agent_role,
            activity_type=activity_type,
            phase=phase,
            step_number=step_number,
            iteration_number=iteration_number,
            input_data=input_data or {},
            output_data=output_data or {},
            raw_output=raw_output,
            activity_metadata=metadata or {},
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            status=status,
            error_message=error_message,
            retry_count=retry_count,
        )

        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)

        logger.debug(
            f"[AgentActivity] {agent_name}/{activity_type} recorded, "
            f"tokens={total_tokens}, cost={cost:.6f}"
        )

        return activity

    async def record_planning_activity(
        self,
        novel_id: UUID,
        task_id: UUID,
        agent_name: str,
        agent_role: str,
        activity_subtype: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        **kwargs,
    ) -> AgentActivity:
        """记录企划阶段的 Agent 活动"""
        return await self.record_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name=agent_name,
            activity_type=f"planning_{activity_subtype}",
            agent_role=agent_role,
            phase="planning",
            input_data=input_data,
            output_data=output_data,
            **kwargs,
        )

    async def record_writing_activity(
        self,
        novel_id: UUID,
        task_id: UUID,
        agent_name: str,
        agent_role: str,
        activity_subtype: str,
        chapter_number: int,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        raw_output: Optional[str] = None,
        **kwargs,
    ) -> AgentActivity:
        """记录写作阶段的 Agent 活动"""
        metadata = kwargs.pop("metadata", {})
        metadata["chapter_number"] = chapter_number

        return await self.record_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name=agent_name,
            activity_type=f"writing_{activity_subtype}",
            agent_role=agent_role,
            phase="writing",
            input_data=input_data,
            output_data=output_data,
            raw_output=raw_output,
            metadata=metadata,
            **kwargs,
        )

    async def record_review_activity(
        self,
        novel_id: UUID,
        task_id: UUID,
        agent_name: str,
        agent_role: str,
        review_type: str,
        iteration: int,
        score: float,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        suggestions: Optional[List[str]] = None,
        **kwargs,
    ) -> AgentActivity:
        """记录审查活动的 Agent 活动"""
        metadata = kwargs.pop("metadata", {})
        metadata.update(
            {
                "review_score": score,
                "iteration": iteration,
                "suggestions": suggestions or [],
            }
        )

        return await self.record_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name=agent_name,
            activity_type=f"review_{review_type}",
            agent_role=agent_role,
            iteration_number=iteration,
            input_data=input_data,
            output_data=output_data,
            metadata=metadata,
            **kwargs,
        )

    async def record_voting_activity(
        self,
        novel_id: UUID,
        task_id: UUID,
        agent_name: str,
        agent_role: str,
        topic: str,
        chosen_option: str,
        reasoning: str,
        confidence: float,
        **kwargs,
    ) -> AgentActivity:
        """记录投票活动的 Agent 活动"""
        metadata = kwargs.pop("metadata", {})
        metadata.update(
            {
                "voting_topic": topic,
                "chosen_option": chosen_option,
                "voting_reasoning": reasoning,
                "confidence": confidence,
            }
        )

        return await self.record_activity(
            novel_id=novel_id,
            task_id=task_id,
            agent_name=agent_name,
            activity_type="voting_vote_cast",
            agent_role=agent_role,
            input_data={"topic": topic},
            output_data={"chosen_option": chosen_option},
            metadata=metadata,
            **kwargs,
        )

    async def get_activities_by_task(
        self, task_id: UUID, limit: int = 100
    ) -> List[AgentActivity]:
        """获取指定任务的所有 Agent 活动"""
        result = await self.db.execute(
            select(AgentActivity)
            .where(AgentActivity.task_id == task_id)
            .order_by(AgentActivity.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_activities_by_novel(
        self, novel_id: UUID, limit: int = 200
    ) -> List[AgentActivity]:
        """获取指定小说的所有 Agent 活动"""
        result = await self.db.execute(
            select(AgentActivity)
            .where(AgentActivity.novel_id == novel_id)
            .order_by(AgentActivity.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_activities_by_agent(
        self, agent_name: str, novel_id: Optional[UUID] = None, limit: int = 100
    ) -> List[AgentActivity]:
        """获取指定 Agent 的活动记录"""
        query = select(AgentActivity).where(AgentActivity.agent_name == agent_name)

        if novel_id:
            query = query.where(AgentActivity.novel_id == novel_id)

        query = query.order_by(AgentActivity.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_activity_summary(self, task_id: UUID) -> Dict[str, Any]:
        """获取任务的活动摘要"""
        activities = await self.get_activities_by_task(task_id)

        if not activities:
            return {"total_activities": 0}

        total_tokens = sum(a.total_tokens for a in activities)
        total_cost = sum(float(a.cost) for a in activities)

        agent_stats = {}
        for activity in activities:
            if activity.agent_name not in agent_stats:
                agent_stats[activity.agent_name] = {
                    "count": 0,
                    "tokens": 0,
                    "cost": 0,
                }
            agent_stats[activity.agent_name]["count"] += 1
            agent_stats[activity.agent_name]["tokens"] += activity.total_tokens
            agent_stats[activity.agent_name]["cost"] += float(activity.cost)

        return {
            "total_activities": len(activities),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "agent_statistics": agent_stats,
            "activity_types": list(set(a.activity_type for a in activities)),
        }


def get_agent_activity_recorder(db: AsyncSession) -> AgentActivityRecorder:
    """获取 Agent 活动记录器实例"""
    return AgentActivityRecorder(db)
