"""Agent 活动 API 路由 - 查看 Agent 详细活动记录"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models.agent_activity import AgentActivity

router = APIRouter(prefix="/agents", tags=["Agent Activities"])


@router.get("/activities")
async def get_agent_activities(
    task_id: Optional[str] = Query(None, description="任务 ID"),
    novel_id: Optional[str] = Query(None, description="小说 ID"),
    agent_name: Optional[str] = Query(None, description="Agent 名称"),
    activity_type: Optional[str] = Query(None, description="活动类型"),
    limit: int = Query(100, ge=1, le=500, description="返回记录数限制"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    查询 Agent 活动记录

    支持多种查询条件：
    - task_id: 查询特定任务的所有 Agent 活动
    - novel_id: 查询特定小说的所有 Agent 活动
    - agent_name: 查询特定 Agent 的活动
    - activity_type: 查询特定类型的活动

    返回按创建时间倒序排列的活动记录
    """
    query = select(AgentActivity)

    # 应用过滤条件
    if task_id:
        try:
            task_uuid = UUID(task_id)
            query = query.where(AgentActivity.task_id == task_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的 task_id 格式")

    if novel_id:
        try:
            novel_uuid = UUID(novel_id)
            query = query.where(AgentActivity.novel_id == novel_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的 novel_id 格式")

    if agent_name:
        query = query.where(AgentActivity.agent_name == agent_name)

    if activity_type:
        query = query.where(AgentActivity.activity_type == activity_type)

    # 按创建时间倒序排序
    query = query.order_by(AgentActivity.created_at.desc()).limit(limit)

    result = await db.execute(query)
    activities = result.scalars().all()

    return {
        "count": len(activities),
        "activities": [activity.to_dict() for activity in activities],
    }


@router.get("/activities/{activity_id}")
async def get_agent_activity_detail(
    activity_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取特定 Agent 活动的详细信息"""
    try:
        activity_uuid = UUID(activity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的活动 ID 格式")

    result = await db.execute(
        select(AgentActivity).where(AgentActivity.id == activity_uuid)
    )
    activity = result.scalar_one_or_none()

    if not activity:
        raise HTTPException(status_code=404, detail="活动记录不存在")

    return activity.to_dict()


@router.get("/activities/task/{task_id}/summary")
async def get_task_activity_summary(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取任务的 Agent 活动摘要"""
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 task_id 格式")

    result = await db.execute(
        select(AgentActivity).where(AgentActivity.task_id == task_uuid)
    )
    activities = result.scalars().all()

    if not activities:
        return {
            "task_id": task_id,
            "total_activities": 0,
            "total_tokens": 0,
            "total_cost": 0,
            "agent_statistics": {},
        }

    # 计算统计信息
    total_tokens = sum(a.total_tokens for a in activities)
    total_cost = sum(float(a.cost) for a in activities)

    agent_stats = {}
    activity_types = set()

    for activity in activities:
        # Agent 统计
        if activity.agent_name not in agent_stats:
            agent_stats[activity.agent_name] = {
                "count": 0,
                "tokens": 0,
                "cost": 0.0,
            }
        agent_stats[activity.agent_name]["count"] += 1
        agent_stats[activity.agent_name]["tokens"] += activity.total_tokens
        agent_stats[activity.agent_name]["cost"] += float(activity.cost)

        # 活动类型统计
        activity_types.add(activity.activity_type)

    return {
        "task_id": task_id,
        "total_activities": len(activities),
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "agent_statistics": agent_stats,
        "activity_types": list(activity_types),
        "phases": list(set(a.phase for a in activities if a.phase)),
    }


@router.get("/activities/novel/{novel_id}/timeline")
async def get_novel_activity_timeline(
    novel_id: str,
    limit: int = Query(200, ge=1, le=1000, description="返回记录数限制"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取小说的 Agent 活动时间线"""
    try:
        novel_uuid = UUID(novel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 novel_id 格式")

    result = await db.execute(
        select(AgentActivity)
        .where(AgentActivity.novel_id == novel_uuid)
        .order_by(AgentActivity.created_at.desc())
        .limit(limit)
    )
    activities = result.scalars().all()

    # 按阶段分组
    phases = {}
    for activity in activities:
        phase = activity.phase or "unknown"
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(activity.to_dict())

    return {
        "novel_id": novel_id,
        "total_activities": len(activities),
        "phases": phases,
    }


@router.get("/agents/{agent_name}/statistics")
async def get_agent_statistics(
    agent_name: str,
    novel_id: Optional[str] = Query(None, description="小说 ID（可选）"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """获取特定 Agent 的统计信息"""
    query = select(AgentActivity).where(AgentActivity.agent_name == agent_name)

    if novel_id:
        try:
            novel_uuid = UUID(novel_id)
            query = query.where(AgentActivity.novel_id == novel_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的 novel_id 格式")

    result = await db.execute(query)
    activities = result.scalars().all()

    if not activities:
        return {
            "agent_name": agent_name,
            "total_activities": 0,
            "total_tokens": 0,
            "total_cost": 0,
            "activity_types": [],
        }

    # 计算统计
    total_tokens = sum(a.total_tokens for a in activities)
    total_cost = sum(float(a.cost) for a in activities)

    activity_type_counts = {}
    for activity in activities:
        activity_type_counts[activity.activity_type] = (
            activity_type_counts.get(activity.activity_type, 0) + 1
        )

    return {
        "agent_name": agent_name,
        "total_activities": len(activities),
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "average_tokens": total_tokens / len(activities) if activities else 0,
        "average_cost": total_cost / len(activities) if activities else 0,
        "activity_type_distribution": activity_type_counts,
        "success_rate": (
            sum(1 for a in activities if a.status == "success") / len(activities) * 100
            if activities
            else 0
        ),
    }
