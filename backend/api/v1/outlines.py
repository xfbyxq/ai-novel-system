"""
WorldSetting and PlotOutline API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.outline import (
    PlotOutlineResponse,
    PlotOutlineUpdate,
    WorldSettingResponse,
    WorldSettingUpdate,
)
from core.models.novel import Novel
from core.models.plot_outline import PlotOutline
from core.models.world_setting import WorldSetting

router = APIRouter(prefix="/novels/{novel_id}", tags=["outlines"])


@router.get("/world-setting", response_model=WorldSettingResponse)
async def get_world_setting(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取小说世界观设定。

    返回小说的世界观设定信息，包括世界名称、类型、力量体系、地理、势力等。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Get world setting
    query = select(WorldSetting).where(WorldSetting.novel_id == novel_id)
    result = await db.execute(query)
    world_setting = result.scalar_one_or_none()

    if not world_setting:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的世界观设定未找到"
        )

    return world_setting


@router.patch("/world-setting", response_model=WorldSettingResponse)
async def update_world_setting(
    novel_id: UUID,
    world_setting_in: WorldSettingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新小说世界观设定（UPSERT模式）。

    - 如果世界观设定不存在，则自动创建
    - 如果已存在，则仅更新请求体中提供的字段
    """
    # Get world setting
    query = select(WorldSetting).where(WorldSetting.novel_id == novel_id)
    result = await db.execute(query)
    world_setting = result.scalar_one_or_none()

    if not world_setting:
        # Create new world setting if it doesn't exist
        novel_query = select(Novel).where(Novel.id == novel_id)
        novel_result = await db.execute(novel_query)
        novel = novel_result.scalar_one_or_none()

        if not novel:
            raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

        world_setting = WorldSetting(
            novel_id=novel_id,
            **world_setting_in.model_dump(exclude_unset=True)
        )
        db.add(world_setting)
    else:
        # Update existing world setting
        update_data = world_setting_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(world_setting, field, value)

    await db.commit()
    await db.refresh(world_setting)
    return world_setting


@router.get("/outline", response_model=PlotOutlineResponse)
async def get_plot_outline(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取小说情节大纲。

    返回小说的情节大纲信息，包括结构类型、卷/篇设定、主线/支线剧情、转折点等。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Get plot outline
    query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    result = await db.execute(query)
    plot_outline = result.scalar_one_or_none()

    if not plot_outline:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的情节大纲未找到"
        )

    return plot_outline


@router.patch("/outline", response_model=PlotOutlineResponse)
async def update_plot_outline(
    novel_id: UUID,
    plot_outline_in: PlotOutlineUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新小说情节大纲（UPSERT模式）。

    - 如果情节大纲不存在，则自动创建
    - 如果已存在，则仅更新请求体中提供的字段
    """
    # Get plot outline
    query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    result = await db.execute(query)
    plot_outline = result.scalar_one_or_none()

    if not plot_outline:
        # Create new plot outline if it doesn't exist
        novel_query = select(Novel).where(Novel.id == novel_id)
        novel_result = await db.execute(novel_query)
        novel = novel_result.scalar_one_or_none()

        if not novel:
            raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

        plot_outline = PlotOutline(
            novel_id=novel_id,
            **plot_outline_in.model_dump(exclude_unset=True)
        )
        db.add(plot_outline)
    else:
        # Update existing plot outline
        update_data = plot_outline_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plot_outline, field, value)

    await db.commit()
    await db.refresh(plot_outline)
    return plot_outline
