"""
Novel CRUD API endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.dependencies import get_db
from backend.schemas.novel import (
    NovelCreate,
    NovelListResponse,
    NovelResponse,
    NovelUpdate,
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
    获取小说列表（分页）.

    返回所有小说的分页列表，按创建时间倒序排列。

    **状态筛选 (status)**:
    - `planning`: 企划中
    - `writing`: 写作中
    - `completed`: 已完成
    - `published`: 已发布
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

    创建一个新的小说项目，初始状态为 `planning`（企划中）。
    创建后可执行企划任务生成世界观、角色、大纲等内容。
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
    获取小说详情.

    返回小说的完整信息，包括关联的世界观设定、角色列表、章节列表等。
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

    仅更新请求体中提供的字段，未提供的字段保持不变。
    当状态改为"企划中"(planning)时，会自动重置所有统计信息（字数、章节数、Token成本等）。
    """
    from core.models.novel import NovelStatus
    from decimal import Decimal

    query = select(Novel).where(Novel.id == novel_id)
    result = await db.execute(query)
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Update only provided fields
    update_data = novel_in.model_dump(exclude_unset=True)

    # 检查是否将状态改为 planning（企划中）
    is_reset_to_planning = (
        update_data.get("status") == NovelStatus.planning.value
        and novel.status != NovelStatus.planning
    )

    for field, value in update_data.items():
        setattr(novel, field, value)

    # 如果重置为企划中状态，清空所有统计信息
    if is_reset_to_planning:
        novel.word_count = 0
        novel.chapter_count = 0
        novel.token_cost = Decimal("0")
        novel.estimated_revenue = Decimal("0")
        novel.actual_revenue = Decimal("0")
        # 可选：同时删除所有章节数据
        # 注意：这里通过 cascade="all, delete-orphan" 关联会自动删除

    await db.commit()
    await db.refresh(novel)
    return novel


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    删除小说.

    **警告**：此操作会级联删除小说的所有关联数据，包括：
    - 世界观设定
    - 所有角色
    - 所有章节
    - 剧情大纲
    - 生成任务记录
    """
    query = select(Novel).where(Novel.id == novel_id)
    result = await db.execute(query)
    novel = result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    await db.delete(novel)
    await db.commit()
