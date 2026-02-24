"""监控API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from backend.services.monitoring_service import MonitoringService
from core.database import get_db

router = APIRouter(prefix="/monitoring", tags=["监控"])


@router.get("/system-status")
async def get_system_status(
    db: AsyncSession = Depends(get_db),
):
    """获取系统状态"""
    service = MonitoringService(db)
    status = await service.get_system_status()
    return {
        "success": True,
        "data": status,
    }


@router.get("/performance-metrics")
async def get_performance_metrics(
    days: int = Query(7, description="分析天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取性能指标"""
    service = MonitoringService(db)
    metrics = await service.get_performance_metrics(days=days)
    return {
        "success": True,
        "data": metrics,
    }


@router.get("/error-analysis")
async def get_error_analysis(
    days: int = Query(7, description="分析天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取错误分析"""
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
    """获取自动调优建议"""
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
    """获取系统健康检查"""
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
    """获取Agent运行状态"""
    service = MonitoringService(db)
    agent_status = await service.get_agent_statuses()
    return {
        "success": True,
        "data": agent_status,
    }
