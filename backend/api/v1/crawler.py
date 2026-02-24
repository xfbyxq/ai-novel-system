"""爬虫任务 API 端点"""

import asyncio
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.crawler import (
    CrawlerTaskCreate,
    CrawlerTaskResponse,
    CrawlerTaskListResponse,
    CrawlResultResponse,
    CrawlResultListResponse,
    MarketDataItem,
    MarketDataResponse,
    ReaderPreferenceResponse,
    ReaderPreferenceListResponse,
)
from backend.services.crawler_service import CrawlerService
from core.models.crawler_task import CrawlerTask, CRAWL_TYPES, CrawlTaskStatus
from core.models.crawl_result import CrawlResult
from core.models.reader_preference import ReaderPreference

router = APIRouter(prefix="/crawler", tags=["crawler"])


@router.post("/tasks", response_model=CrawlerTaskResponse, status_code=201)
async def create_crawler_task(
    task_in: CrawlerTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建爬虫任务。

    - crawl_type=ranking: 爬取排行榜（月票、畅销、阅读指数等）
    - crawl_type=trending_tags: 爬取热门标签
    - crawl_type=book_metadata: 爬取书籍详情（需在 config 中指定 book_ids）
    - crawl_type=genre_list: 爬取分类列表
    """
    # 验证爬取类型
    valid_types = list(CRAWL_TYPES.keys())
    if task_in.crawl_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的爬取类型。可选: {', '.join(valid_types)}"
        )

    # 创建任务记录
    task = CrawlerTask(
        task_name=task_in.task_name,
        platform=task_in.platform,
        crawl_type=task_in.crawl_type,  # 直接使用字符串类型
        config=task_in.config,
        status=CrawlTaskStatus.pending,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 异步执行任务
    async def _run_task():
        """在后台执行爬虫任务。"""
        from core.database import async_session_factory

        async with async_session_factory() as session:
            service = CrawlerService(session)
            await service.run_crawler_task(task.id)

    # 在后台启动任务
    asyncio.create_task(_run_task())

    return task


@router.get("/tasks", response_model=CrawlerTaskListResponse)
async def list_crawler_tasks(
    platform: Optional[str] = Query(None, description="按平台筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    crawl_type: Optional[str] = Query(None, description="按爬取类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取爬虫任务列表。"""
    offset = (page - 1) * page_size

    query = select(CrawlerTask)
    count_query = select(func.count()).select_from(CrawlerTask)

    if platform:
        query = query.where(CrawlerTask.platform == platform)
        count_query = count_query.where(CrawlerTask.platform == platform)
    if status:
        query = query.where(CrawlerTask.status == status)
        count_query = count_query.where(CrawlerTask.status == status)
    if crawl_type:
        query = query.where(CrawlerTask.crawl_type == crawl_type)
        count_query = count_query.where(CrawlerTask.crawl_type == crawl_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset(offset).limit(page_size).order_by(CrawlerTask.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()

    return CrawlerTaskListResponse(items=tasks, total=total)


@router.get("/tasks/{task_id}", response_model=CrawlerTaskResponse)
async def get_crawler_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取爬虫任务详情。"""
    result = await db.execute(
        select(CrawlerTask).where(CrawlerTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")
    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_crawler_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """取消爬虫任务。"""
    result = await db.execute(
        select(CrawlerTask).where(CrawlerTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

    if task.status in (CrawlTaskStatus.completed, CrawlTaskStatus.failed, CrawlTaskStatus.cancelled):
        raise HTTPException(status_code=400, detail=f"任务已处于终态: {task.status.value}")

    task.status = CrawlTaskStatus.cancelled
    await db.commit()
    return {"message": "任务已取消", "task_id": str(task_id)}


@router.get("/tasks/{task_id}/results", response_model=CrawlResultListResponse)
async def get_crawler_task_results(
    task_id: UUID,
    data_type: Optional[str] = Query(None, description="按数据类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取爬虫任务的爬取结果。"""
    # 检查任务是否存在
    task_result = await db.execute(
        select(CrawlerTask).where(CrawlerTask.id == task_id)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

    offset = (page - 1) * page_size

    query = select(CrawlResult).where(CrawlResult.crawler_task_id == task_id)
    count_query = select(func.count()).select_from(CrawlResult).where(
        CrawlResult.crawler_task_id == task_id
    )

    if data_type:
        query = query.where(CrawlResult.data_type == data_type)
        count_query = count_query.where(CrawlResult.data_type == data_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset(offset).limit(page_size).order_by(CrawlResult.created_at.desc())
    result = await db.execute(query)
    results = result.scalars().all()

    return CrawlResultListResponse(items=results, total=total)


@router.get("/market-data", response_model=MarketDataResponse)
async def get_market_data(
    platform: Optional[str] = Query("qidian", description="平台"),
    genre: Optional[str] = Query(None, description="类型"),
    min_word_count: Optional[int] = Query(None, description="最小字数"),
    max_word_count: Optional[int] = Query(None, description="最大字数"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取市场数据（聚合的爬取结果）。"""
    offset = (page - 1) * page_size

    query = select(ReaderPreference).where(ReaderPreference.source == platform)
    count_query = select(func.count()).select_from(ReaderPreference).where(
        ReaderPreference.source == platform
    )

    if genre:
        query = query.where(ReaderPreference.genre == genre)
        count_query = count_query.where(ReaderPreference.genre == genre)
    if min_word_count:
        query = query.where(ReaderPreference.word_count >= min_word_count)
        count_query = count_query.where(ReaderPreference.word_count >= min_word_count)
    if max_word_count:
        query = query.where(ReaderPreference.word_count <= max_word_count)
        count_query = count_query.where(ReaderPreference.word_count <= max_word_count)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset(offset).limit(page_size).order_by(ReaderPreference.created_at.desc())
    result = await db.execute(query)
    preferences = result.scalars().all()

    # 转换为 MarketDataItem
    items = []
    for pref in preferences:
        items.append(MarketDataItem(
            book_id=pref.book_id,
            book_title=pref.book_title,
            author_name=pref.author_name,
            genre=pref.genre,
            tags=pref.tags,
            rating=pref.rating,
            word_count=pref.word_count,
            trend_score=pref.trend_score,
            source=pref.source,
            data_date=str(pref.data_date) if pref.data_date else None,
        ))

    return MarketDataResponse(items=items, total=total)


@router.get("/preferences", response_model=ReaderPreferenceListResponse)
async def list_reader_preferences(
    source: Optional[str] = Query(None, description="数据来源"),
    genre: Optional[str] = Query(None, description="类型"),
    crawler_task_id: Optional[UUID] = Query(None, description="关联爬虫任务ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取读者偏好数据列表。"""
    offset = (page - 1) * page_size

    query = select(ReaderPreference)
    count_query = select(func.count()).select_from(ReaderPreference)

    if source:
        query = query.where(ReaderPreference.source == source)
        count_query = count_query.where(ReaderPreference.source == source)
    if genre:
        query = query.where(ReaderPreference.genre == genre)
        count_query = count_query.where(ReaderPreference.genre == genre)
    if crawler_task_id:
        query = query.where(ReaderPreference.crawler_task_id == crawler_task_id)
        count_query = count_query.where(ReaderPreference.crawler_task_id == crawler_task_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset(offset).limit(page_size).order_by(ReaderPreference.created_at.desc())
    result = await db.execute(query)
    preferences = result.scalars().all()

    return ReaderPreferenceListResponse(items=preferences, total=total)
