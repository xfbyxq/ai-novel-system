"""
Chapter CRUD API endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.outline import (
    ChapterListResponse,
    ChapterResponse,
    ChapterUpdate,
)
from core.models.chapter import Chapter
from core.models.novel import Novel


class BatchDeleteRequest(BaseModel):
    """批量删除章节请求"""

    chapter_numbers: list[int] = Field(..., description="要删除的章节号列表")


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
    获取指定小说的章节列表（分页）。

    返回章节列表，按章节号正序排列。

    **状态筛选 (status)**:
    - `draft`: 草稿
    - `reviewing`: 审核中
    - `published`: 已发布
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
    count_query = (
        select(func.count()).select_from(Chapter).where(Chapter.novel_id == novel_id)
    )
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
    根据章节号获取章节详情。

    返回指定章节的完整内容。
    """
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await db.execute(query)
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=404, detail=f"小说 {novel_id} 的第 {chapter_number} 章未找到"
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
    更新章节内容。

    仅更新请求体中提供的字段。如果更新 content 字段，word_count 会自动重新计算，
    同时会同步更新小说的总字数统计。
    """
    # 查询小说
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # 查询章节
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await db.execute(query)
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=404, detail=f"小说 {novel_id} 的第 {chapter_number} 章未找到"
        )

    # 记录更新前的字数
    old_word_count = chapter.word_count or 0

    # Update only provided fields
    update_data = chapter_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chapter, field, value)

    # Update word count if content changed
    new_word_count = old_word_count
    if "content" in update_data and chapter.content:
        new_word_count = len(chapter.content)
        chapter.word_count = new_word_count

    # 同步更新小说总字数
    if "content" in update_data:
        word_count_diff = new_word_count - old_word_count
        novel.word_count = max(0, (novel.word_count or 0) + word_count_diff)

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
    删除章节。

    删除指定章节号的章节，不会影响其他章节的编号。
    删除后会自动更新小说的章节数和总字数统计。
    """
    # 查询小说
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # 查询章节
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await db.execute(query)
    chapters = result.scalars().all()

    if not chapters:
        raise HTTPException(
            status_code=404, detail=f"小说 {novel_id} 的第 {chapter_number} 章未找到"
        )

    # 计算被删除章节的字数总和
    deleted_word_count = sum(chapter.word_count or 0 for chapter in chapters)
    deleted_chapter_count = len(chapters)

    # 删除章节
    for chapter in chapters:
        await db.delete(chapter)

    # 更新小说统计信息
    novel.chapter_count = max(0, (novel.chapter_count or 0) - deleted_chapter_count)
    novel.word_count = max(0, (novel.word_count or 0) - deleted_word_count)

    await db.commit()
    return None


@router.post("/batch-delete", status_code=204)
async def batch_delete_chapters(
    novel_id: UUID,
    request: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    批量删除多个章节。

    一次性删除多个指定章节号的章节。不存在的章节号会被忽略。
    删除后会自动更新小说的章节数和总字数统计。
    """
    # 查询小说
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # 查询要删除的章节
    query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number.in_(request.chapter_numbers),
    )
    result = await db.execute(query)
    chapters = result.scalars().all()

    # 计算被删除章节的字数总和
    deleted_word_count = sum(chapter.word_count or 0 for chapter in chapters)
    deleted_chapter_count = len(chapters)

    # 删除章节
    for chapter in chapters:
        await db.delete(chapter)

    # 更新小说统计信息
    novel.chapter_count = max(0, (novel.chapter_count or 0) - deleted_chapter_count)
    novel.word_count = max(0, (novel.word_count or 0) - deleted_word_count)

    await db.commit()
    return None
