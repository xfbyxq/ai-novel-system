"""生成任务 API 端点"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.generation import (
    GenerationTaskCreate,
    GenerationTaskResponse,
    GenerationTaskListResponse,
)
from backend.services.generation_service import GenerationService
from core.models.generation_task import GenerationTask, TaskStatus, TaskType
from core.models.novel import Novel

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/tasks", response_model=GenerationTaskResponse, status_code=201)
async def create_generation_task(
    task_in: GenerationTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建生成任务（企划、单章写作或批量写作）。

    - task_type=planning: 执行企划阶段（世界观、角色、大纲）
    - task_type=writing: 执行单章写作（需在 input_data 中指定 chapter_number）
    - task_type=batch_writing: 执行批量写作（需指定 from_chapter 和 to_chapter）
    """
    # 检查小说是否存在
    novel_result = await db.execute(select(Novel).where(Novel.id == task_in.novel_id))
    novel = novel_result.scalar_one_or_none()
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {task_in.novel_id} 未找到")

    # 批量写作验证
    if task_in.task_type == "batch_writing":
        if not task_in.from_chapter or not task_in.to_chapter:
            raise HTTPException(
                status_code=400,
                detail="批量写作必须指定 from_chapter 和 to_chapter"
            )
        if task_in.from_chapter > task_in.to_chapter:
            raise HTTPException(
                status_code=400,
                detail="from_chapter 不能大于 to_chapter"
            )

    # 创建任务记录
    input_data = task_in.input_data or {}
    if task_in.task_type == "batch_writing":
        input_data["from_chapter"] = task_in.from_chapter
        input_data["to_chapter"] = task_in.to_chapter
        input_data["volume_number"] = task_in.volume_number or 1

    task = GenerationTask(
        novel_id=task_in.novel_id,
        task_type=task_in.task_type,
        phase=task_in.phase or task_in.task_type,
        input_data=input_data,
        status=TaskStatus.pending,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 在后台异步执行任务（立即返回，不阻塞）
    from fastapi import BackgroundTasks
    import asyncio
    from core.database import async_session_factory

    def _run_task_sync():
        """同步包装器，在新的事件循环中运行异步任务。"""
        async def _run_task():
            async with async_session_factory() as session:
                service = GenerationService(session)
                try:
                    if task_in.task_type == "planning":
                        await service.run_planning(task_in.novel_id, task.id)
                    elif task_in.task_type == "writing":
                        chapter_number = (task_in.input_data or {}).get("chapter_number", 1)
                        volume_number = (task_in.input_data or {}).get("volume_number", 1)
                        await service.run_chapter_writing(
                            task_in.novel_id, task.id, chapter_number, volume_number
                        )
                    elif task_in.task_type == "batch_writing":
                        await service.run_batch_writing(
                            task_in.novel_id,
                            task.id,
                            task_in.from_chapter,
                            task_in.to_chapter,
                            task_in.volume_number or 1,
                        )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Task {task.id} failed: {e}")

        # 在新线程中创建新的事件循环运行任务
        import threading
        thread = threading.Thread(target=lambda: asyncio.run(_run_task()))
        thread.daemon = True
        thread.start()

    # 立即启动后台任务
    _run_task_sync()

    return task


@router.get("/tasks", response_model=GenerationTaskListResponse)
async def list_generation_tasks(
    novel_id: Optional[UUID] = Query(None, description="按小说ID筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取生成任务列表。"""
    offset = (page - 1) * page_size

    query = select(GenerationTask)
    count_query = select(func.count()).select_from(GenerationTask)

    if novel_id:
        query = query.where(GenerationTask.novel_id == novel_id)
        count_query = count_query.where(GenerationTask.novel_id == novel_id)
    if status:
        query = query.where(GenerationTask.status == status)
        count_query = count_query.where(GenerationTask.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset(offset).limit(page_size).order_by(GenerationTask.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()

    return GenerationTaskListResponse(items=tasks, total=total)


@router.get("/tasks/{task_id}", response_model=GenerationTaskResponse)
async def get_generation_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取生成任务状态。"""
    result = await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")
    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_generation_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """取消生成任务。"""
    result = await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

    if task.status in (TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled):
        raise HTTPException(status_code=400, detail=f"任务已处于终态: {task.status.value}")

    task.status = TaskStatus.cancelled
    await db.commit()
    return {"message": "任务已取消", "task_id": str(task_id)}
