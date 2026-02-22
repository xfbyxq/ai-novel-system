"""
WorldSetting and PlotOutline API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.outline import (
    WorldSettingResponse,
    WorldSettingUpdate,
    PlotOutlineResponse,
    PlotOutlineUpdate,
)
from core.models.novel import Novel
from core.models.world_setting import WorldSetting
from core.models.plot_outline import PlotOutline

router = APIRouter(prefix="/novels/{novel_id}", tags=["outlines"])


@router.get("/world-setting", response_model=WorldSettingResponse)
async def get_world_setting(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取小说世界观设定.
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
    更新小说世界观设定.
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
    获取小说情节大纲.
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
    更新小说情节大纲.
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
