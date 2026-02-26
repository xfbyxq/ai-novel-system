"""
Chapter CRUD API endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.outline import (
    ChapterResponse,
    ChapterListResponse,
    ChapterUpdate,
)
from core.models.chapter import Chapter
from core.models.novel import Novel
from pydantic import BaseModel


class BatchDeleteRequest(BaseModel):
    chapter_numbers: list[int]

router = APIRouter(prefix="/novels/{novel_id}/chapters", tags=["chapters"])


@router.get("", response_model=ChapterListResponse)
async def list_chapters(
    novel_id: UUID,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="章节状态筛选"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定小说的章节列表(分页).
    
    - **page**: 页码,从1开始
    - **page_size**: 每页数量,最大100
    - **status**: 可选的状态筛选 (draft/reviewing/published)
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
    offset = (page - 1) * page_size
    
    # Build query
    query = select(Chapter).where(Chapter.novel_id == novel_id)
    if status:
        query = query.where(Chapter.status == status)
    
    # Get total count
    count_query = select(func.count()).select_from(Chapter).where(Chapter.novel_id == novel_id)
    if status:
        count_query = count_query.where(Chapter.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated chapters
    query = query.offset(offset).limit(page_size).order_by(Chapter.chapter_number)
    result = await db.execute(query)
    chapters = result.scalars().all()
    
    return ChapterListResponse(
        items=chapters,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{chapter_number}", response_model=ChapterResponse)
async def get_chapter_by_number(
    novel_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """
    根据章节号获取章节详情.
    """
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await db.execute(query)
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的第 {chapter_number} 章未找到"
        )
    
    return chapter


@router.patch("/{chapter_number}", response_model=ChapterResponse)
async def update_chapter(
    novel_id: UUID,
    chapter_number: int,
    chapter_in: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新章节内容.
    """
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await db.execute(query)
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的第 {chapter_number} 章未找到"
        )
    
    # Update only provided fields
    update_data = chapter_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chapter, field, value)
    
    # Update word count if content changed
    if "content" in update_data and chapter.content:
        chapter.word_count = len(chapter.content)
    
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.delete("/{chapter_number}", status_code=204)
async def delete_chapter(
    novel_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """
    删除章节.
    """
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await db.execute(query)
    chapters = result.scalars().all()
    
    if not chapters:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的第 {chapter_number} 章未找到"
        )
    
    for chapter in chapters:
        await db.delete(chapter)
    
    await db.commit()
    return None


@router.post("/batch-delete", status_code=204)
async def batch_delete_chapters(
    novel_id: UUID,
    request: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    批量删除章节.
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")
    
    # Delete chapters
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number.in_(request.chapter_numbers)
    )
    result = await db.execute(query)
    chapters = result.scalars().all()
    
    for chapter in chapters:
        await db.delete(chapter)
    
    await db.commit()
    return None
