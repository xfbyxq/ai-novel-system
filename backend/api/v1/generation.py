"""生成任务 API 端点."""

from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.common import TaskCancelResponse
from backend.schemas.generation import (
    GenerationTaskCreate,
    GenerationTaskListResponse,
    GenerationTaskResponse,
)
from backend.services.generation_service import GenerationService
from core.models.generation_task import GenerationTask, TaskStatus
from core.models.novel import Novel

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/tasks", response_model=GenerationTaskResponse, status_code=201)
async def create_generation_task(
    task_in: GenerationTaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """创建生成任务（企划、单章写作、批量写作或大纲完善）.

    - task_type=planning: 执行企划阶段（世界观、角色、大纲）
    - task_type=writing: 执行单章写作（需在 input_data 中指定 chapter_number）
    - task_type=batch_writing: 执行批量写作（需指定 from_chapter 和 to_chapter）
    - task_type=outline_refinement: 执行大纲完善（优化现有大纲结构和内容）
    """
    # 检查小说是否存在
    novel_result = await db.execute(select(Novel).where(Novel.id == task_in.novel_id))
    novel = novel_result.scalar_one_or_none()
    if not novel:
        raise HTTPException(status_code=404, detail=f"小说 {task_in.novel_id} 未找到")

    # 企划任务并发控制：同一小说只能有一个企划任务在运行
    if task_in.task_type == "planning":
        running_planning_task = await db.execute(
            select(GenerationTask)
            .where(
                GenerationTask.novel_id == task_in.novel_id,
                GenerationTask.task_type == "planning",
                GenerationTask.status.in_(["pending", "running"]),
            )
            .order_by(GenerationTask.created_at.desc())
        )
        existing_task = running_planning_task.scalar_one_or_none()
        if existing_task:
            raise HTTPException(
                status_code=400,
                detail=f"该小说已有企划任务在运行中 (Task ID: {existing_task.id}), 请等待完成后在创建新的企划任务",
            )

    # 批量写作验证
    if task_in.task_type == "batch_writing":
        if not task_in.from_chapter or not task_in.to_chapter:
            raise HTTPException(
                status_code=400, detail="批量写作必须指定 from_chapter 和 to_chapter"
            )
        if task_in.from_chapter > task_in.to_chapter:
            raise HTTPException(status_code=400, detail="from_chapter 不能大于 to_chapter")

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

    # 使用 BackgroundTasks 在后台执行任务
    async def run_task():
        """在后台执行生成任务."""
        from core.database import async_session_factory

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
                elif task_in.task_type == "outline_refinement":
                    await service.run_outline_refinement(task_in.novel_id, task.id)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Task {task.id} failed: {e}", exc_info=True)

    # 添加后台任务
    background_tasks.add_task(run_task)

    return task


@router.get("/tasks", response_model=GenerationTaskListResponse)
async def list_generation_tasks(
    novel_id: Optional[UUID] = Query(None, description="按小说ID筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取生成任务列表."""
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

    query = (
        query.offset(offset).limit(page_size).order_by(GenerationTask.created_at.desc())
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    return GenerationTaskListResponse(items=tasks, total=total)


@router.get("/tasks/{task_id}", response_model=GenerationTaskResponse)
async def get_generation_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取生成任务状态."""
    result = await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=TaskCancelResponse)
async def cancel_generation_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    取消生成任务。

    只能取消处于 pending（等待中）或 running（执行中）状态的任务。
    已完成、已失败或已取消的任务无法再次取消。
    """
    result = await db.execute(
        select(GenerationTask).where(GenerationTask.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

    # 获取状态字符串值
    status_value = task.status.value if hasattr(task.status, "value") else task.status

    if status_value in (
        TaskStatus.completed.value,
        TaskStatus.failed.value,
        TaskStatus.cancelled.value,
    ):
        raise HTTPException(status_code=400, detail=f"任务已处于终态: {status_value}")

    task.status = (
        TaskStatus.cancelled.value
        if hasattr(TaskStatus.cancelled, "value")
        else TaskStatus.cancelled
    )
    await db.commit()
    return {"message": "任务已取消", "task_id": str(task_id)}
