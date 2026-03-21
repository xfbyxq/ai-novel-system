"""监控API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.monitoring_service import MonitoringService
from core.database import get_db

router = APIRouter(prefix="/monitoring", tags=["监控"])


@router.get("/system-status")
async def get_system_status(
    db: AsyncSession = Depends(get_db),
):
    """
    获取系统状态。

    返回系统运行状态概览，包括服务健康度、资源使用情况等。
    """
    service = MonitoringService(db)
    status = await service.get_system_status()
    return {
        "success": True,
        "data": status,
    }


@router.get("/performance-metrics")
async def get_performance_metrics(
    days: int = Query(7, ge=1, le=90, description="分析天数（1-90）"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取性能指标。

    返回指定时间范围内的性能数据，包括响应时间、吞吐量、错误率等。
    """
    service = MonitoringService(db)
    metrics = await service.get_performance_metrics(days=days)
    return {
        "success": True,
        "data": metrics,
    }


@router.get("/error-analysis")
async def get_error_analysis(
    days: int = Query(7, ge=1, le=90, description="分析天数（1-90）"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取错误分析。

    返回指定时间范围内的错误统计和分类，帮助定位问题。
    """
    service = MonitoringService(db)
    analysis = await service.get_error_analysis(days=days)
    return {
        "success": True,
        "data": analysis,
    }


@router.get("/auto-optimization")
async def get_auto_optimization_suggestions(
    db: AsyncSession = Depends(get_db),
):
    """
    获取自动调优建议。

    基于历史数据分析，返回系统优化建议。
    """
    service = MonitoringService(db)
    suggestions = await service.get_auto_optimization_suggestions()
    return {
        "success": True,
        "data": suggestions,
    }


@router.get("/health-check")
async def get_system_health_check(
    db: AsyncSession = Depends(get_db),
):
    """
    获取系统健康检查。

    检查各组件（数据库、Redis、外部服务等）的健康状态。
    """
    service = MonitoringService(db)
    health_check = await service.get_system_health_check()
    return {
        "success": True,
        "data": health_check,
    }


@router.get("/agent-status")
async def get_agent_status(
    db: AsyncSession = Depends(get_db),
):
    """
    获取Agent运行状态。

    返回所有AI Agent的当前状态，包括运行中的任务、资源占用等。
    """
    service = MonitoringService(db)
    agent_status = await service.get_agent_statuses()
    return {
        "success": True,
        "data": agent_status,
    }


@router.get("/agent-history/{agent_id}")
async def get_agent_history(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取Agent历史任务。

    返回指定Agent的历史执行记录。
    """
    service = MonitoringService(db)
    agent_history = await service.get_agent_history(agent_id)
    return agent_history
