"""市场分析API"""
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend.services.market_analysis_service import MarketAnalysisService
from core.database import get_db

router = APIRouter(prefix="/market-analysis", tags=["市场分析"])


@router.get("/market-data")
async def get_market_data(
    platform: str = Query("all", description="平台"),
    data_type: str = Query("all", description="数据类型"),
    days: int = Query(7, description="天数"),
    limit: int = Query(100, description="限制数量"),
    genre: str = Query(None, description="分类"),
    min_word_count: int = Query(None, description="最小字数"),
    max_word_count: int = Query(None, description="最大字数"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页大小"),
    db: AsyncSession = Depends(get_db),
):
    """获取市场数据"""
    service = MarketAnalysisService(db)
    data = await service.get_market_data(
        platform=platform,
        data_type=data_type,
        days=days,
        limit=limit,
        genre=genre,
        min_word_count=min_word_count,
        max_word_count=max_word_count,
        page=page,
        page_size=page_size,
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


@router.get("/genre-analysis/{genre}")
async def get_genre_analysis(
    genre: str,
    days: int = Query(30, description="天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取特定分类的详细分析"""
    service = MarketAnalysisService(db)
    data = await service.get_genre_analysis(
        genre=genre,
        days=days,
    )
    return {
        "success": True,
        "data": data,
        "genre": genre,
    }


@router.get("/platform-comparison")
async def get_platform_comparison(
    days: int = Query(30, description="天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取平台对比分析"""
    service = MarketAnalysisService(db)
    data = await service.get_platform_comparison(
        days=days,
    )
    return {
        "success": True,
        "data": data,
    }


@router.get("/trend-analysis")
async def get_trend_analysis(
    platform: str = Query("all", description="平台"),
    genre: str = Query("all", description="分类"),
    metric: str = Query("count", description="指标"),
    days: int = Query(90, description="历史天数"),
    forecast_days: int = Query(90, description="预测天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取趋势分析"""
    service = MarketAnalysisService(db)
    data = await service.get_trend_analysis(
        platform=platform,
        genre=genre,
        metric=metric,
        days=days,
        forecast_days=forecast_days,
    )
    return {
        "success": True,
        "data": data,
    }


@router.get("/genre-trend-comparison")
async def get_genre_trend_comparison(
    genres: list[str] = Query(..., description="分类列表"),
    days: int = Query(90, description="天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取分类趋势对比"""
    service = MarketAnalysisService(db)
    data = await service.get_genre_trend_comparison(
        genres=genres,
        days=days,
    )
    return {
        "success": True,
        "data": data,
    }


@router.get("/trend-report")
async def generate_trend_report(
    platform: str = Query("all", description="平台"),
    days: int = Query(90, description="历史天数"),
    forecast_days: int = Query(90, description="预测天数"),
    db: AsyncSession = Depends(get_db),
):
    """生成趋势报告"""
    service = MarketAnalysisService(db)
    report = await service.generate_trend_report(
        platform=platform,
        days=days,
        forecast_days=forecast_days,
    )
    return {
        "success": True,
        "data": report,
    }


@router.post("/analyze-sentiment")
async def analyze_sentiment(
    text: str = Body(..., description="要分析的文本"),
    db: AsyncSession = Depends(get_db),
):
    """分析文本情感"""
    service = MarketAnalysisService(db)
    result = await service.analyze_sentiment(text)
    return {
        "success": True,
        "data": result,
    }


@router.post("/analyze-comments-sentiment")
async def analyze_comments_sentiment(
    comments: List[str] = Body(..., description="评论列表"),
    db: AsyncSession = Depends(get_db),
):
    """分析评论情感"""
    service = MarketAnalysisService(db)
    result = await service.analyze_comments_sentiment(comments)
    return {
        "success": True,
        "data": result,
    }


@router.post("/analyze-market-text")
async def analyze_market_text(
    text: str = Body(..., description="要分析的文本"),
    analysis_type: str = Query("market", description="分析类型"),
    db: AsyncSession = Depends(get_db),
):
    """分析市场相关文本"""
    service = MarketAnalysisService(db)
    result = await service.analyze_market_text(text, analysis_type)
    return {
        "success": True,
        "data": result,
    }


@router.get("/ai-insights")
async def generate_ai_insights(
    platform: str = Query("all", description="平台"),
    days: int = Query(30, description="分析天数"),
    db: AsyncSession = Depends(get_db),
):
    """生成AI市场洞察"""
    service = MarketAnalysisService(db)
    # 获取市场数据
    market_data = await service.get_reader_preferences(
        platform=platform,
        days=days
    )
    # 获取趋势分析
    trend_analysis = await service.get_trend_analysis(
        platform=platform,
        days=days,
        forecast_days=30
    )
    # 生成AI洞察
    insights = await service.generate_ai_insights(
        market_data=market_data,
        trend_analysis=trend_analysis,
        platform=platform
    )
    return {
        "success": True,
        "data": insights,
    }


@router.get("/ai-market-report")
async def generate_ai_market_report(
    platform: str = Query("all", description="平台"),
    days: int = Query(30, description="分析天数"),
    db: AsyncSession = Depends(get_db),
):
    """生成AI市场报告"""
    service = MarketAnalysisService(db)
    report = await service.generate_ai_market_report(
        platform=platform,
        days=days
    )
    return {
        "success": True,
        "data": report,
    }
