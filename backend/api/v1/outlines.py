"""
WorldSetting and PlotOutline API endpoints.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.outline import (
    ChapterOutlineTaskResponse,
    OutlineDecomposeRequest,
    OutlineGenerateRequest,
    OutlineValidationRequest,
    OutlineValidationResponse,
    OutlineVersionInfo,
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


@router.post("/outline/generate", response_model=PlotOutlineResponse)
async def generate_complete_outline(
    novel_id: UUID,
    request: OutlineGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    生成小说完整大纲。

    根据请求参数生成小说的完整大纲，包括结构类型、卷设定、主线/支线剧情、转折点等。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Check if outline already exists
    outline_query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    outline_result = await db.execute(outline_query)
    existing_outline = outline_result.scalar_one_or_none()

    if existing_outline:
        raise HTTPException(
            status_code=409,
            detail=f"小说 {novel_id} 已存在大纲，请先删除或更新现有大纲"
        )

    # TODO: 调用 AI Agent 生成大纲
    # 这里应该调用大纲生成服务
    # 现在创建一个空的大纲记录
    plot_outline = PlotOutline(
        novel_id=novel_id,
        structure_type=request.structure_type,
        volumes=[],
        main_plot={},
        sub_plots=[],
        key_turning_points=[],
    )
    
    db.add(plot_outline)
    await db.commit()
    await db.refresh(plot_outline)
    
    return plot_outline


@router.post("/outline/decompose", response_model=dict)
async def decompose_outline_to_chapters(
    novel_id: UUID,
    request: OutlineDecomposeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    将大纲拆分为章节配置。

    根据指定的章节范围和分解粒度，将大纲分解为各章节的详细任务。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Verify plot outline exists
    outline_query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    outline_result = await db.execute(outline_query)
    plot_outline = outline_result.scalar_one_or_none()

    if not plot_outline:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的情节大纲未找到"
        )

    # Validate chapter range
    if request.chapter_start < 1 or request.chapter_end < request.chapter_start:
        raise HTTPException(
            status_code=400,
            detail="章节范围无效，chapter_start 必须 >= 1 且 chapter_end >= chapter_start"
        )

    # TODO: 调用 AI Agent 分解大纲
    # 这里应该调用大纲分解服务
    # 现在返回一个示例响应
    decomposed_chapters = []
    for chapter_num in range(request.chapter_start, request.chapter_end + 1):
        chapter_task = {
            "chapter_number": chapter_num,
            "volume_number": request.volume_number,
            "outline_task": {
                "main_goal": f"第{chapter_num}章的主要目标",
                "key_events": ["事件 1", "事件 2"],
                "character_development": "角色发展要点"
            },
            "decomposition_level": request.decomposition_level
        }
        decomposed_chapters.append(chapter_task)

    return {
        "novel_id": str(novel_id),
        "chapter_range": {
            "start": request.chapter_start,
            "end": request.chapter_end
        },
        "volume_number": request.volume_number,
        "decomposition_level": request.decomposition_level,
        "chapters": decomposed_chapters,
        "decomposed_at": datetime.now()
    }


@router.get("/chapters/{chapter_number}/outline-task", response_model=ChapterOutlineTaskResponse)
async def get_chapter_outline_task(
    novel_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定章节的大纲任务。

    返回章节的详细大纲任务，包括主要剧情点、角色发展弧线、伏笔要求等。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Import Chapter model here to avoid circular imports
    from core.models.chapter import Chapter
    
    # Check if chapter exists
    chapter_query = select(Chapter).where(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number == chapter_number
    )
    chapter_result = await db.execute(chapter_query)
    chapter = chapter_result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的第{chapter_number}章未找到"
        )

    # Return chapter outline task
    outline_task = chapter.outline_task or {}
    
    return ChapterOutlineTaskResponse(
        chapter_number=chapter.chapter_number,
        volume_number=chapter.volume_number,
        title=chapter.title,
        outline_task=outline_task,
        main_plot_points=outline_task.get("main_plot_points", []),
        character_arcs=outline_task.get("character_arcs", []),
        foreshadowing_requirements=outline_task.get("foreshadowing_requirements", []),
        consistency_checks=outline_task.get("consistency_checks", []),
        created_at=chapter.created_at,
        updated_at=chapter.updated_at
    )


@router.post("/chapters/{chapter_number}/validate-outline", response_model=OutlineValidationResponse)
async def validate_chapter_outline(
    novel_id: UUID,
    chapter_number: int,
    request: OutlineValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    验证章节大纲的一致性。

    检查章节大纲与整体大纲、角色设定、世界观设定等的一致性。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Verify plot outline exists
    outline_query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    outline_result = await db.execute(outline_query)
    plot_outline = outline_result.scalar_one_or_none()

    if not plot_outline:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的情节大纲未找到"
        )

    # TODO: 调用 AI Agent 验证大纲
    # 这里应该调用大纲验证服务
    # 现在返回一个示例响应
    validation_results = {
        "character_consistency": {"passed": True, "details": "角色设定一致"},
        "plot_continuity": {"passed": True, "details": "剧情连贯"},
        "world_setting": {"passed": True, "details": "世界观设定一致"},
        "timeline": {"passed": True, "details": "时间线正确"}
    }
    
    issues = []
    suggestions = []
    consistency_score = 0.95

    return OutlineValidationResponse(
        is_valid=len(issues) == 0,
        validation_results=validation_results,
        issues=issues,
        suggestions=suggestions,
        consistency_score=consistency_score,
        validated_at=datetime.now()
    )


@router.get("/outline/versions", response_model=list[OutlineVersionInfo])
async def get_outline_versions(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取大纲版本历史。

    返回小说大纲的所有版本信息，支持版本对比和回滚。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Verify plot outline exists
    outline_query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    outline_result = await db.execute(outline_query)
    plot_outline = outline_result.scalar_one_or_none()

    if not plot_outline:
        raise HTTPException(
            status_code=404,
            detail=f"小说 {novel_id} 的情节大纲未找到"
        )

    # TODO: 从版本历史表中获取版本信息
    # 目前返回一个示例版本列表
    # 实际实现需要创建 PlotOutlineVersion 模型来存储版本历史
    versions = [
        OutlineVersionInfo(
            version_id="v1.0.0",
            novel_id=novel_id,
            version_number=1,
            change_summary="初始版本",
            changes={
                "structure_type": "创建",
                "volumes": "创建",
                "main_plot": "创建"
            },
            created_by="system",
            created_at=plot_outline.created_at,
            is_current=True
        )
    ]

    return versions


@router.patch("/outline", response_model=PlotOutlineResponse)
async def update_plot_outline_with_version(
    novel_id: UUID,
    plot_outline_in: PlotOutlineUpdate,
    create_version: bool = True,
    version_summary: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    更新小说情节大纲（支持版本管理）。

    - 如果情节大纲不存在，则自动创建
    - 如果已存在，则仅更新请求体中提供的字段
    - 可选择是否创建新版本记录
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

    # TODO: 创建版本历史记录
    # if create_version and plot_outline.id:
    #     version_record = PlotOutlineVersion(
    #         plot_outline_id=plot_outline.id,
    #         version_data=plot_outline.__dict__,
    #         change_summary=version_summary,
    #         changes=update_data
    #     )
    #     db.add(version_record)

    await db.commit()
    await db.refresh(plot_outline)
    return plot_outline
