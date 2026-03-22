"""
WorldSetting and PlotOutline API endpoints.
"""

import logging
import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.dependencies import get_db
from backend.schemas.outline import (
    AIAssistRequest,
    AIAssistResponse,
    ChapterOutlineTaskResponse,
    EnhancementOptions,
    EnhancementPreviewResponse,
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
from core.models.plot_outline import PlotOutline
import logging

core_logger = logging.getLogger(__name__)
from core.models.novel import Novel
from core.models.plot_outline import PlotOutline
from core.models.plot_outline_version import PlotOutlineVersion
from core.models.world_setting import WorldSetting
from core.models.character import Character
from core.models.chapter import Chapter
from backend.services.outline_service import OutlineService

router = APIRouter(prefix="/novels/{novel_id}", tags=["outlines"])


@router.get("/world-setting", response_model=WorldSettingResponse)
async def get_world_setting(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取小说世界观设定.

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
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的世界观设定未找到")

    return world_setting


@router.patch("/world-setting", response_model=WorldSettingResponse)
async def update_world_setting(
    novel_id: UUID,
    world_setting_in: WorldSettingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新小说世界观设定（UPSERT模式）.

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
            novel_id=novel_id, **world_setting_in.model_dump(exclude_unset=True)
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
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的情节大纲未找到")

    # 修复数据格式：确保volumes中的每个卷都有number字段
    plot_outline = fix_plot_outline_volumes(plot_outline)

    return plot_outline


@router.patch("/outline", response_model=PlotOutlineResponse)
async def update_plot_outline(
    novel_id: UUID,
    plot_outline_in: PlotOutlineUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新小说情节大纲（UPSERT模式）.

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
            novel_id=novel_id, **plot_outline_in.model_dump(exclude_unset=True)
        )
        db.add(plot_outline)
    else:
        # Update existing plot outline
        update_data = plot_outline_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plot_outline, field, value)

    await db.commit()
    await db.refresh(plot_outline)

    # 修复数据格式：确保volumes中的每个卷都有number字段
    plot_outline = fix_plot_outline_volumes(plot_outline)

    return plot_outline


@router.post("/outline/generate", response_model=PlotOutlineResponse)
async def generate_complete_outline(
    novel_id: UUID,
    request: OutlineGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    生成小说完整大纲.

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
            detail=f"小说 {novel_id} 已存在大纲，请先删除或更新现有大纲",
        )

    # FIXME: 调用 AI Agent 生成大纲 - 跟踪于 GitHub Issue #23
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

    # 修复数据格式：确保volumes中的每个卷都有number字段
    plot_outline = fix_plot_outline_volumes(plot_outline)

    return plot_outline


@router.post("/outline/decompose", response_model=dict)
async def decompose_outline_to_chapters(
    novel_id: UUID,
    request: OutlineDecomposeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    将大纲拆分为章节配置.

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
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的情节大纲未找到")

    # Validate chapter range
    if request.chapter_start < 1 or request.chapter_end < request.chapter_start:
        raise HTTPException(
            status_code=400,
            detail="章节范围无效，chapter_start 必须 >= 1 且 chapter_end >= chapter_start",
        )

    # 调用服务层进行大纲分解
    outline_service = OutlineService(db)

    # 构建大纲数据
    outline_data = {
        "volumes": plot_outline.volumes or [],
        "main_plot": plot_outline.main_plot or {},
        "sub_plots": plot_outline.sub_plots or [],
        "key_turning_points": plot_outline.key_turning_points or [],
        "climax_chapter": plot_outline.climax_chapter,
    }

    # 执行分解
    decompose_result = await outline_service.decompose_outline(
        novel_id,
        outline_data,
        config={
            "volume_number": request.volume_number,
            "auto_split": True,
        },
    )

    # 持久化到章节表
    chapter_configs = decompose_result.get("chapter_configs", [])
    persisted_chapters = []

    for chapter_config in chapter_configs:
        chapter_num = chapter_config.get("chapter_number")
        if not chapter_num:
            continue

        # 查找或创建章节
        existing_chapter_query = select(Chapter).where(
            Chapter.novel_id == novel_id, Chapter.chapter_number == chapter_num
        )
        existing_result = await db.execute(existing_chapter_query)
        existing_chapter = existing_result.scalar_one_or_none()

        if existing_chapter:
            # 更新现有章节
            existing_chapter.outline_task = chapter_config
            existing_chapter.volume_number = chapter_config.get(
                "volume_number", request.volume_number
            )
            existing_chapter.outline_version = f"v{datetime.now().strftime('%Y%m%d%H%M%S')}"
            persisted_chapters.append(existing_chapter)
        else:
            # 创建新章节
            new_chapter = Chapter(
                novel_id=novel_id,
                chapter_number=chapter_num,
                volume_number=chapter_config.get("volume_number", request.volume_number),
                outline_task=chapter_config,
                outline_version=f"v{datetime.now().strftime('%Y%m%d%H%M%S')}",
                title=f"第{chapter_num}章",
                status="pending",
                word_count=0,
            )
            db.add(new_chapter)
            persisted_chapters.append(new_chapter)

    await db.commit()

    return {
        "novel_id": str(novel_id),
        "chapter_range": {"start": request.chapter_start, "end": request.chapter_end},
        "volume_number": request.volume_number,
        "decomposition_level": request.decomposition_level,
        "chapters": chapter_configs,
        "persisted_count": len(persisted_chapters),
        "decomposed_at": datetime.now(),
    }


@router.get("/chapters/{chapter_number}/outline-task", response_model=ChapterOutlineTaskResponse)
async def get_chapter_outline_task(
    novel_id: UUID,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定章节的大纲任务.

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
        Chapter.novel_id == novel_id, Chapter.chapter_number == chapter_number
    )
    chapter_result = await db.execute(chapter_query)
    chapter = chapter_result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的第{chapter_number}章未找到")

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
        updated_at=chapter.updated_at,
    )


@router.post(
    "/chapters/{chapter_number}/validate-outline",
    response_model=OutlineValidationResponse,
)
async def validate_chapter_outline(
    novel_id: UUID,
    chapter_number: int,
    request: OutlineValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    验证章节大纲的一致性.

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
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的情节大纲未找到")

    # 调用服务层进行验证
    outline_service = OutlineService(db)

    validation_report = await outline_service.validate_chapter_outline(
        novel_id, chapter_number, request.chapter_outline or {}
    )

    # 构建验证结果
    validation_results = {
        "completion": validation_report.get("completion", {}),
        "quality_score": validation_report.get("quality_score", 0),
        "passed": validation_report.get("passed", False),
    }

    # 构建问题列表
    issues = []
    missing_events = validation_report.get("completion", {}).get("missing_events", [])
    for event in missing_events:
        issues.append(
            {
                "type": "missing_event",
                "severity": "warning",
                "message": f"缺失事件：{event}",
                "event": event,
            }
        )

    return OutlineValidationResponse(
        is_valid=validation_report.get("passed", False),
        validation_results=validation_results,
        issues=issues,
        suggestions=validation_report.get("suggestions", []),
        consistency_score=validation_report.get("quality_score", 0) / 10,
        validated_at=datetime.now(),
    )


@router.post("/outline/ai-assist", response_model=AIAssistResponse)
async def ai_assist_outline_field(
    novel_id: UUID,
    request: AIAssistRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    AI辅助生成大纲字段内容.

    根据当前大纲上下文，为指定字段生成AI建议。
    """
    # Verify novel exists
    novel_query = select(Novel).where(Novel.id == novel_id)
    novel_result = await db.execute(novel_query)
    novel = novel_result.scalar_one_or_none()

    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

    # Get plot outline for context
    outline_query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    outline_result = await db.execute(outline_query)
    plot_outline = outline_result.scalar_one_or_none()

    # Get world setting for context
    world_query = select(WorldSetting).where(WorldSetting.novel_id == novel_id)
    world_result = await db.execute(world_query)
    world_setting = world_result.scalar_one_or_none()

    # Get characters for context
    char_query = select(Character).where(Character.novel_id == novel_id)
    char_result = await db.execute(char_query)
    characters = char_result.scalars().all()

    # Build context for AI
    context = request.current_context or {}

    # Add existing outline data to context
    if plot_outline:
        context.setdefault("outline", {})
        context["outline"]["structure_type"] = plot_outline.structure_type
        context["outline"]["volumes"] = plot_outline.volumes
        context["outline"]["main_plot"] = plot_outline.main_plot
        context["outline"]["sub_plots"] = plot_outline.sub_plots
        context["outline"]["climax_chapter"] = plot_outline.climax_chapter

    if world_setting:
        context["world_setting"] = {
            "world_name": world_setting.world_name,
            "world_type": world_setting.world_type,
            "power_system": world_setting.power_system,
        }

    if characters:
        context["characters"] = [
            {"name": c.name, "role": c.role, "archetype": c.archetype}
            for c in characters[:10]  # 限制数量避免上下文过长
        ]

    # Add novel info
    context["novel"] = {
        "title": novel.title,
        "genre": novel.genre,
        "target_word_count": novel.target_word_count,
    }

    # Call outline service to generate suggestion
    outline_service = OutlineService(db)

    suggestion_result = await outline_service.generate_field_suggestion(
        novel_id=novel_id,
        field_name=request.field_name,
        context=context,
        hints=request.additional_hints,
    )

    return AIAssistResponse(
        field_name=request.field_name,
        suggestion=suggestion_result.get("suggestion", ""),
        confidence=suggestion_result.get("confidence"),
        alternatives=suggestion_result.get("alternatives"),
        reasoning=suggestion_result.get("reasoning"),
        generated_at=datetime.now(),
    )


@router.get("/outline/versions", response_model=list[OutlineVersionInfo])
async def get_outline_versions(
    novel_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取大纲版本历史.

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
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的情节大纲未找到")

    versions_query = (
        select(PlotOutlineVersion)
        .where(PlotOutlineVersion.plot_outline_id == plot_outline.id)
        .order_by(PlotOutlineVersion.version_number.desc())
    )
    versions_result = await db.execute(versions_query)
    version_records = versions_result.scalars().all()

    if not version_records:
        versions = [
            OutlineVersionInfo(
                version_id=str(plot_outline.id),
                novel_id=novel_id,
                version_number=1,
                change_summary="初始版本",
                changes={"structure_type": "创建", "volumes": "创建", "main_plot": "创建"},
                created_by="system",
                created_at=plot_outline.created_at,
                is_current=True,
            )
        ]
    else:
        versions = [
            OutlineVersionInfo(
                version_id=str(v.id),
                novel_id=novel_id,
                version_number=v.version_number,
                change_summary=v.change_summary or "",
                changes=v.changes or {},
                created_by=v.created_by or "system",
                created_at=v.created_at,
                is_current=(v.version_number == plot_outline.version),
            )
            for v in version_records
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
    更新小说情节大纲（支持版本管理）.

    - 如果情节大纲不存在，则自动创建
    - 如果已存在，则仅更新请求体中提供的字段
    - 可选择是否创建新版本记录
    """
    # Get plot outline
    query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    result = await db.execute(query)
    plot_outline = result.scalar_one_or_none()

    if not plot_outline:
        novel_query = select(Novel).where(Novel.id == novel_id)
        novel_result = await db.execute(novel_query)
        novel = novel_result.scalar_one_or_none()

        if not novel:
            raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

        plot_outline = PlotOutline(
            novel_id=novel_id, **plot_outline_in.model_dump(exclude_unset=True)
        )
        db.add(plot_outline)
        await db.flush()

        if create_version:
            version_record = PlotOutlineVersion(
                plot_outline_id=plot_outline.id,
                version_number=1,
                version_data={
                    "structure_type": plot_outline.structure_type,
                    "volumes": plot_outline.volumes or [],
                    "main_plot": plot_outline.main_plot or {},
                    "sub_plots": plot_outline.sub_plots or [],
                    "key_turning_points": plot_outline.key_turning_points or [],
                },
                change_summary=version_summary or "初始版本",
                changes=plot_outline_in.model_dump(exclude_unset=True),
                created_by="system",
            )
            db.add(version_record)
            plot_outline.version = 1
    else:
        if create_version:
            version_count_query = select(PlotOutlineVersion).where(
                PlotOutlineVersion.plot_outline_id == plot_outline.id
            )
            version_count_result = await db.execute(version_count_query)
            existing_versions = version_count_result.scalars().all()
            new_version_number = max([v.version_number for v in existing_versions], default=0) + 1

            version_record = PlotOutlineVersion(
                plot_outline_id=plot_outline.id,
                version_number=new_version_number,
                version_data={
                    "structure_type": plot_outline.structure_type,
                    "volumes": plot_outline.volumes or [],
                    "main_plot": plot_outline.main_plot or {},
                    "sub_plots": plot_outline.sub_plots or [],
                    "key_turning_points": plot_outline.key_turning_points or [],
                },
                change_summary=version_summary,
                changes=plot_outline_in.model_dump(exclude_unset=True),
                created_by="system",
            )
            db.add(version_record)
            plot_outline.version = new_version_number

        update_data = plot_outline_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plot_outline, field, value)

    await db.commit()
    await db.refresh(plot_outline)

    # 修复数据格式：确保volumes中的每个卷都有number字段
    plot_outline = fix_plot_outline_volumes(plot_outline)

    return plot_outline


@router.post("/outline/enhance-preview", response_model=EnhancementPreviewResponse)
async def enhance_outline_preview(
    *,
    novel_id: UUID,
    options: EnhancementOptions,
    db: AsyncSession = Depends(get_db),
):
    """预览大纲智能完善结果（不修改数据库）."""
    try:
        logger.info(f"开始大纲完善预览: novel_id={novel_id}")

        # 获取小说信息
        novel_result = await db.execute(select(Novel).where(Novel.id == novel_id))
        novel = novel_result.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail=f"小说 {novel_id} 未找到")

        # 获取大纲
        outline_result = await db.execute(
            select(PlotOutline).where(PlotOutline.novel_id == novel_id)
        )
        plot_outline = outline_result.scalar_one_or_none()
        if not plot_outline:
            raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的情节大纲未找到")

        # 获取世界观设定
        world_result = await db.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )
        world_setting = world_result.scalar_one_or_none()

        # 获取角色信息
        characters_result = await db.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        characters = characters_result.scalars().all()

        # 初始化Agent管理器
        from backend.dependencies.agents import get_crew_manager, get_outline_evaluator

        crew_manager = get_crew_manager()
        evaluator = get_outline_evaluator()

        # 转换模型为字典
        initial_outline = model_to_dict(plot_outline)

        # 执行大纲完善
        start_time = time.time()
        enhancement_result = await crew_manager.refine_outline_comprehensive(
            outline=initial_outline,
            world_setting=model_to_dict(world_setting) if world_setting else {},
            characters=([model_to_dict(char) for char in characters] if characters else []),
            options=options.dict(),
            max_rounds=options.max_iterations,
        )

        # 评估质量对比
        original_quality = await evaluator.evaluate_outline_comprehensively(
            outline=model_to_dict(plot_outline),
            world_setting=model_to_dict(world_setting) if world_setting else {},
            characters=([model_to_dict(char) for char in characters] if characters else []),
        )

        enhanced_quality = await evaluator.evaluate_outline_comprehensively(
            outline=enhancement_result["enhancement_result"]["enhanced_outline"],
            world_setting=model_to_dict(world_setting) if world_setting else {},
            characters=([model_to_dict(char) for char in characters] if characters else []),
        )

        processing_time = time.time() - start_time
        cost_estimate = 0.0

        # 修复原始和增强大纲中的卷数据格式
        fixed_original_outline = initial_outline.copy() if initial_outline else {}
        if "volumes" in fixed_original_outline and fixed_original_outline["volumes"]:
            fixed_original_outline["volumes"] = [
                (
                    vol.copy()
                    if "number" in vol
                    else {**vol, "number": vol.get("volume_num", idx + 1)}
                )
                for idx, vol in enumerate(fixed_original_outline["volumes"])
            ]

        fixed_enhanced_outline = enhancement_result["enhancement_result"]["enhanced_outline"].copy()
        if "volumes" in fixed_enhanced_outline and fixed_enhanced_outline["volumes"]:
            fixed_enhanced_outline["volumes"] = [
                (
                    vol.copy()
                    if "number" in vol
                    else {**vol, "number": vol.get("volume_num", idx + 1)}
                )
                for idx, vol in enumerate(fixed_enhanced_outline["volumes"])
            ]

        return EnhancementPreviewResponse(
            original_outline=fixed_original_outline,
            enhanced_outline=fixed_enhanced_outline,
            quality_comparison={
                "original_score": original_quality.overall_score,
                "enhanced_score": enhanced_quality.overall_score,
                "improvement": enhanced_quality.overall_score - original_quality.overall_score,
                "dimension_improvements": {
                    dim: enhanced_quality.dimension_scores[dim]
                    - original_quality.dimension_scores[dim]
                    for dim in original_quality.dimension_scores.keys()
                },
            },
            improvements_made=enhancement_result["enhancement_result"].get("improvements_made", [])[
                :3
            ],  # 限制改进数量
            processing_time=processing_time,
            cost_estimate=cost_estimate,
        )

    except Exception as e:
        logger.error(f"大纲完善预览失败：{e}")
        raise HTTPException(status_code=500, detail=f"完善失败：{str(e)}")


@router.post("/outline/{outline_id}/apply-enhancement", response_model=dict)
async def apply_outline_enhancement(
    *,
    novel_id: UUID,
    outline_id: UUID,
    enhanced_outline: dict,
    db: AsyncSession = Depends(get_db),
):
    """应用大纲优化结果到数据库."""
    try:
        # 获取原大纲
        plot_outline = await db.execute(
            select(PlotOutline).where(
                PlotOutline.id == outline_id, PlotOutline.novel_id == novel_id
            )
        )
        plot_outline = plot_outline.scalar_one_or_none()

        if not plot_outline:
            raise HTTPException(status_code=404, detail=f"大纲 {outline_id} 未找到")

        # 更新大纲内容
        if "main_plot" in enhanced_outline:
            plot_outline.main_plot = enhanced_outline["main_plot"]
        if "sub_plots" in enhanced_outline:
            plot_outline.sub_plots = enhanced_outline["sub_plots"]
        if "key_turning_points" in enhanced_outline:
            plot_outline.key_turning_points = enhanced_outline["key_turning_points"]

        # 创建新版本
        # FIXME: 实现版本控制功能 - 跟踪于 GitHub Issue #26
        # await create_outline_version(db, novel_id, outline_id, "应用 AI 优化结果")

        await db.commit()

        return {"message": "优化结果已应用", "outline_id": str(outline_id)}

    except Exception as e:
        await db.rollback()
        logger.error(f"应用大纲优化失败：{e}")
        raise HTTPException(status_code=500, detail=f"应用优化失败：{str(e)}")


def fix_plot_outline_volumes(plot_outline):
    """修复情节大纲中的卷数据格式，确保volumes中的每个卷都有number字段."""
    if plot_outline.volumes:
        fixed_volumes = []
        for vol in plot_outline.volumes:
            # 如果没有number字段但有volume_num字段，则复制volume_num作为number
            if "number" not in vol and "volume_num" in vol:
                vol_copy = vol.copy()
                vol_copy["number"] = vol_copy["volume_num"]
                fixed_volumes.append(vol_copy)
            else:
                # 如果既有volume_num又有number，保持number优先
                vol_copy = vol.copy()
                if "volume_num" in vol_copy and "number" not in vol_copy:
                    vol_copy["number"] = vol_copy["volume_num"]
                fixed_volumes.append(vol_copy)
        plot_outline.volumes = fixed_volumes
    return plot_outline


def model_to_dict(model_instance):
    """将SQLAlchemy模型实例转换为字典."""
    if model_instance is None:
        return {}

    # 获取模型的所有列属性
    result = {}
    for column in model_instance.__table__.columns:
        value = getattr(model_instance, column.name)
        # 处理UUID类型
        if hasattr(value, "hex"):
            value = value.hex
        # 处理datetime类型
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        result[column.name] = value

    return result


__all__ = ["router"]


@router.post("/outline/versions/{version_id}/rollback", response_model=PlotOutlineResponse)
async def rollback_outline_version(
    novel_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    回滚大纲到指定版本.

    - 获取指定版本的完整大纲数据
    - 恢复到当前大纲
    - 创建新的版本记录
    """
    outline_query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
    outline_result = await db.execute(outline_query)
    plot_outline = outline_result.scalar_one_or_none()

    if not plot_outline:
        raise HTTPException(status_code=404, detail=f"小说 {novel_id} 的大纲未找到")

    version_query = select(PlotOutlineVersion).where(
        PlotOutlineVersion.id == version_id,
        PlotOutlineVersion.plot_outline_id == plot_outline.id,
    )
    version_result = await db.execute(version_query)
    version_record = version_result.scalar_one_or_none()

    if not version_record:
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 未找到")

    version_data = version_record.version_data
    if version_data:
        if "structure_type" in version_data:
            plot_outline.structure_type = version_data["structure_type"]
        if "volumes" in version_data:
            plot_outline.volumes = version_data["volumes"]
        if "main_plot" in version_data:
            plot_outline.main_plot = version_data["main_plot"]
        if "sub_plots" in version_data:
            plot_outline.sub_plots = version_data["sub_plots"]
        if "key_turning_points" in version_data:
            plot_outline.key_turning_points = version_data["key_turning_points"]

    version_count_query = select(PlotOutlineVersion).where(
        PlotOutlineVersion.plot_outline_id == plot_outline.id
    )
    version_count_result = await db.execute(version_count_query)
    existing_versions = version_count_result.scalars().all()
    new_version_number = max([v.version_number for v in existing_versions], default=0) + 1

    rollback_version = PlotOutlineVersion(
        plot_outline_id=plot_outline.id,
        version_number=new_version_number,
        version_data=version_data,
        change_summary=f"回滚到版本 {version_record.version_number}",
        changes={"action": "rollback", "rollback_from_version": version_record.version_number},
        created_by="system",
    )
    db.add(rollback_version)
    plot_outline.version = new_version_number

    await db.commit()
    await db.refresh(plot_outline)

    plot_outline = fix_plot_outline_volumes(plot_outline)

    return plot_outline
