"""
Novel CRUD API endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.dependencies import get_db
from backend.schemas.novel import (
    NovelCreate,
    NovelUpdate,
    NovelResponse,
    NovelListResponse,
)
from core.models.novel import Novel

router = APIRouter(prefix="/novels", tags=["novels"])


@router.get("", response_model=NovelListResponse)
async def list_novels(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="小说状态筛选"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取小说列表(分页).
    
    - **page**: 页码,从1开始
    - **page_size**: 每页数量,最大100
    - **status**: 可选的状态筛选 (planning/writing/completed/published)
    """
    offset = (page - 1) * page_size
    
    # Build query
    query = select(Novel)
    if status:
        query = query.where(Novel.status == status)
    
    # Get total count
    count_query = select(func.count()).select_from(Novel)
    if status:
        count_query = count_query.where(Novel.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated novels
    query = query.offset(offset).limit(page_size).order_by(Novel.created_at.desc())
    result = await db.execute(query)
    novels = result.scalars().all()
    
    return NovelListResponse(
        items=novels,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=NovelResponse, status_code=201)
async def create_novel(
    novel_in: NovelCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建新小说.
    """
    novel = Novel(**novel_in.model_dump())
    db.add(novel)
    await db.commit()
    await db.refresh(novel)
    return novel


@router.get("/{novel_id}", response_model=NovelResponse)
async def get_novel(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取小说详情(包含世界观、角色数、章节数等).
    """
    query = (
        select(Novel)
        .where(Novel.id == novel_id)
        .options(
            selectinload(Novel.world_setting),
            selectinload(Novel.characters),
            selectinload(Novel.chapters),
        )
    )
    result = await db.execute(query)
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
    return novel


@router.patch("/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: UUID,
    novel_in: NovelUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新小说信息.
    """
    query = select(Novel).where(Novel.id == novel_id)
    result = await db.execute(query)
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
    # Update only provided fields
    update_data = novel_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(novel, field, value)
    
    await db.commit()
    await db.refresh(novel)
    return novel


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    删除小说(级联删除相关数据).
    """
    query = select(Novel).where(Novel.id == novel_id)
    result = await db.execute(query)
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
    await db.delete(novel)
    await db.commit()
