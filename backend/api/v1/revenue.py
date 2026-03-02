"""收益分析API"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.revenue_analysis_service import RevenueAnalysisService
from core.database import get_db

router = APIRouter(prefix="/revenue", tags=["收益分析"])


@router.get("/novel-performance/{novel_id}")
async def analyze_novel_performance(
    novel_id: UUID,
    days: int = Query(30, description="分析天数"),
    db: AsyncSession = Depends(get_db),
):
    """分析小说的性能数据"""
    service = RevenueAnalysisService(db)
    result = await service.analyze_novel_performance(
        novel_id=novel_id,
        days=days,
    )
    return {
        "success": "error" not in result,
        "data": result,
    }


@router.get("/platform-performance/{platform}")
async def analyze_platform_performance(
    platform: str,
    days: int = Query(30, description="分析天数"),
    db: AsyncSession = Depends(get_db),
):
    """分析平台的性能数据"""
    service = RevenueAnalysisService(db)
    result = await service.analyze_platform_performance(
        platform=platform,
        days=days,
    )
    return {
        "success": True,
        "data": result,
    }


@router.get("/revenue-forecast/{novel_id}")
async def generate_revenue_forecast(
    novel_id: UUID,
    days: int = Query(30, description="预测天数"),
    db: AsyncSession = Depends(get_db),
):
    """生成小说的收益预测"""
    service = RevenueAnalysisService(db)
    result = await service.generate_revenue_forecast(
        novel_id=novel_id,
        days=days,
    )
    return {
        "success": "error" not in result,
        "data": result,
    }


@router.get("/content-optimization/{novel_id}")
async def get_content_optimization_suggestions(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取内容优化建议"""
    service = RevenueAnalysisService(db)
    result = await service.get_content_optimization_suggestions(
        novel_id=novel_id,
    )
    return {
        "success": "error" not in result,
        "data": result,
    }
