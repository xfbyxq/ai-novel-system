"""市场分析API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.market_analysis_service import MarketAnalysisService
from core.database import get_db

router = APIRouter(prefix="/market-analysis", tags=["市场分析"])


@router.get("/market-data")
async def get_market_data(
    platform: str = Query("all", description="平台"),
    data_type: str = Query("all", description="数据类型"),
    days: int = Query(7, description="天数"),
    limit: int = Query(100, description="限制数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取市场数据"""
    service = MarketAnalysisService(db)
    data = await service.get_market_data(
        platform=platform,
        data_type=data_type,
        days=days,
        limit=limit,
    )
    return {
        "success": True,
        "data": data,
        "platform": platform,
        "days": days,
    }


@router.get("/reader-preferences")
async def get_reader_preferences(
    platform: str = Query("all", description="平台"),
    genre: str = Query("all", description="分类"),
    days: int = Query(30, description="天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取读者偏好数据"""
    service = MarketAnalysisService(db)
    data = await service.get_reader_preferences(
        platform=platform,
        genre=genre,
        days=days,
    )
    return {
        "success": True,
        "data": data,
    }


@router.get("/trending-topics")
async def get_trending_topics(
    platform: str = Query("all", description="平台"),
    limit: int = Query(20, description="限制数量"),
    days: int = Query(7, description="天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取热门话题"""
    service = MarketAnalysisService(db)
    data = await service.get_trending_topics(
        platform=platform,
        limit=limit,
        days=days,
    )
    return {
        "success": True,
        "data": data,
        "platform": platform,
        "days": days,
    }


@router.get("/recommended-genres")
async def get_recommended_genres(
    platform: str = Query("all", description="平台"),
    days: int = Query(30, description="天数"),
    limit: int = Query(10, description="限制数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取推荐分类"""
    service = MarketAnalysisService(db)
    data = await service.get_recommended_genres(
        platform=platform,
        days=days,
        limit=limit,
    )
    return {
        "success": True,
        "data": data,
        "platform": platform,
    }


@router.get("/trending-tags")
async def get_trending_tags(
    platform: str = Query("all", description="平台"),
    days: int = Query(14, description="天数"),
    limit: int = Query(30, description="限制数量"),
    db: AsyncSession = Depends(get_db),
):
    """获取热门标签"""
    service = MarketAnalysisService(db)
    data = await service.get_trending_tags(
        platform=platform,
        days=days,
        limit=limit,
    )
    return {
        "success": True,
        "data": data,
        "platform": platform,
    }


@router.get("/market-report")
async def generate_market_report(
    days: int = Query(7, description="天数"),
    platforms: list[str] = Query(None, description="包含的平台"),
    db: AsyncSession = Depends(get_db),
):
    """生成市场报告"""
    service = MarketAnalysisService(db)
    report = await service.generate_market_report(
        days=days,
        include_platforms=platforms,
    )
    return {
        "success": True,
        "data": report,
    }
