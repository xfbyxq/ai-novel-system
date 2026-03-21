"""发布系统 API 端点."""

import asyncio
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.schemas.common import (
    DeleteResponse,
    TaskCancelResponse,
    VerifyAccountResponse,
)
from core.utils.enum_utils import safe_enum_value
from backend.schemas.publishing import (
    ChapterPreviewItem,
    ChapterPublishListResponse,
    PlatformAccountCreate,
    PlatformAccountListResponse,
    PlatformAccountResponse,
    PlatformAccountUpdate,
    PublishPreviewRequest,
    PublishPreviewResponse,
    PublishTaskCreate,
    PublishTaskListResponse,
    PublishTaskResponse,
)
from backend.services.publishing_service import PublishingService
from core.models.chapter_publish import ChapterPublish
from core.models.platform_account import AccountStatus, PlatformAccount
from core.models.publish_task import PublishTask, PublishTaskStatus, PublishType

router = APIRouter(prefix="/publishing", tags=["publishing"])


# ============================================================
# 平台账号管理
# ============================================================


@router.post("/accounts", response_model=PlatformAccountResponse, status_code=201)
async def create_platform_account(
    account_in: PlatformAccountCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建平台账号。

    支持的平台：qidian、jjwxc、hongxiu、zongheng、17k、fanqie 等。
    """
    service = PublishingService(db)
    account = await service.create_account(
        platform=account_in.platform,
        account_name=account_in.account_name,
        username=account_in.username,
        password=account_in.password,
        extra_credentials=account_in.extra_credentials,
    )
    return account


@router.get("/accounts", response_model=PlatformAccountListResponse)
async def list_platform_accounts(
    platform: Optional[str] = Query(None, description="按平台筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    获取平台账号列表。

    支持按平台和状态筛选。
    """
    offset = (page - 1) * page_size

    query = select(PlatformAccount)
    count_query = select(func.count()).select_from(PlatformAccount)

    if platform:
        query = query.where(PlatformAccount.platform == platform)
        count_query = count_query.where(PlatformAccount.platform == platform)
    if status:
        query = query.where(PlatformAccount.status == status)
        count_query = count_query.where(PlatformAccount.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = (
        query.offset(offset)
        .limit(page_size)
        .order_by(PlatformAccount.created_at.desc())
    )
    result = await db.execute(query)
    accounts = result.scalars().all()

    return PlatformAccountListResponse(items=accounts, total=total)


@router.get("/accounts/{account_id}", response_model=PlatformAccountResponse)
async def get_platform_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取平台账号详情."""
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 未找到")
    return account


@router.patch("/accounts/{account_id}", response_model=PlatformAccountResponse)
async def update_platform_account(
    account_id: UUID,
    account_in: PlatformAccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新平台账号."""
    service = PublishingService(db)
    account = await service.update_account(
        account_id=account_id,
        account_name=account_in.account_name,
        password=account_in.password,
        extra_credentials=account_in.extra_credentials,
        status=account_in.status,
    )
    if not account:
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 未找到")
    return account


@router.delete("/accounts/{account_id}", response_model=DeleteResponse)
async def delete_platform_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    删除平台账号。

    删除后，使用此账号的发布任务将无法继续执行。
    """
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail=f"账号 {account_id} 未找到")

    await db.delete(account)
    await db.commit()
    return {"message": "账号已删除", "account_id": str(account_id)}


@router.post("/accounts/{account_id}/verify", response_model=VerifyAccountResponse)
async def verify_platform_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    验证平台账号。

    检查账号凭证是否有效，可正常登录平台。
    """
    service = PublishingService(db)
    success = await service.verify_account(account_id)
    return {
        "success": success,
        "message": "账号验证成功" if success else "账号验证失败",
    }


# ============================================================
# 发布任务管理
# ============================================================


@router.post("/tasks", response_model=PublishTaskResponse, status_code=201)
async def create_publish_task(
    task_in: PublishTaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建发布任务。

    **发布类型 (publish_type)**:
    - `create_book`: 在平台创建新书
    - `publish_chapter`: 发布单个章节
    - `batch_publish`: 批量发布多个章节（需指定 from_chapter 和 to_chapter）
    """
    # 验证发布类型
    valid_types = [t.value for t in PublishType]
    if task_in.publish_type not in valid_types:
        raise HTTPException(
            status_code=400, detail=f"无效的发布类型。可选: {', '.join(valid_types)}"
        )

    # 验证账号存在
    account_result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == task_in.account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="平台账号不存在")

    if account.status != AccountStatus.active:
        raise HTTPException(status_code=400, detail="平台账号状态异常，无法发布")

    # 构建配置
    config = task_in.config or {}
    if task_in.from_chapter:
        config["from_chapter"] = task_in.from_chapter
    if task_in.to_chapter:
        config["to_chapter"] = task_in.to_chapter

    # 如果是批量发布，检查是否有平台书籍ID
    if task_in.publish_type in ["publish_chapter", "batch_publish"]:
        # 查找已有的 platform_book_id
        existing_task = await db.execute(
            select(PublishTask)
            .where(
                PublishTask.novel_id == task_in.novel_id,
                PublishTask.account_id == task_in.account_id,
                PublishTask.platform_book_id.isnot(None),
            )
            .order_by(PublishTask.created_at.desc())
            .limit(1)
        )
        existing = existing_task.scalar_one_or_none()
        platform_book_id = existing.platform_book_id if existing else None
    else:
        platform_book_id = None

    # 创建任务
    task = PublishTask(
        novel_id=task_in.novel_id,
        account_id=task_in.account_id,
        publish_type=PublishType(task_in.publish_type),
        config=config,
        status=PublishTaskStatus.pending,
        platform_book_id=platform_book_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 异步执行任务
    async def _run_task():
        from core.database import async_session_factory

        async with async_session_factory() as session:
            service = PublishingService(session)
            await service.run_publish_task(task.id)

    asyncio.create_task(_run_task())

    return task


@router.get("/tasks", response_model=PublishTaskListResponse)
async def list_publish_tasks(
    novel_id: Optional[UUID] = Query(None, description="按小说ID筛选"),
    account_id: Optional[UUID] = Query(None, description="按账号ID筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取发布任务列表."""
    offset = (page - 1) * page_size

    query = select(PublishTask)
    count_query = select(func.count()).select_from(PublishTask)

    if novel_id:
        query = query.where(PublishTask.novel_id == novel_id)
        count_query = count_query.where(PublishTask.novel_id == novel_id)
    if account_id:
        query = query.where(PublishTask.account_id == account_id)
        count_query = count_query.where(PublishTask.account_id == account_id)
    if status:
        query = query.where(PublishTask.status == status)
        count_query = count_query.where(PublishTask.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = (
        query.offset(offset).limit(page_size).order_by(PublishTask.created_at.desc())
    )
    result = await db.execute(query)
    tasks = result.scalars().all()

    return PublishTaskListResponse(items=tasks, total=total)


@router.get("/tasks/{task_id}", response_model=PublishTaskResponse)
async def get_publish_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取发布任务详情."""
    result = await db.execute(select(PublishTask).where(PublishTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")
    return task


@router.post("/tasks/{task_id}/cancel", response_model=TaskCancelResponse)
async def cancel_publish_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    取消发布任务。

    只能取消处于 pending 或 running 状态的任务。
    """
    result = await db.execute(select(PublishTask).where(PublishTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

    # 获取状态值（支持String列和Enum）
    task_status_value = (
        task.status.value if hasattr(task.status, "value") else task.status
    )

    terminal_statuses = (
        (
            PublishTaskStatus.completed.value
            if hasattr(PublishTaskStatus.completed, "value")
            else PublishTaskStatus.completed
        ),
        (
            PublishTaskStatus.failed.value
            if hasattr(PublishTaskStatus.failed, "value")
            else PublishTaskStatus.failed
        ),
        (
            PublishTaskStatus.cancelled.value
            if hasattr(PublishTaskStatus.cancelled, "value")
            else PublishTaskStatus.cancelled
        ),
    )
    if task_status_value in terminal_statuses:
        raise HTTPException(
            status_code=400, detail=f"任务已处于终态: {task_status_value}"
        )

    task.status = (
        PublishTaskStatus.cancelled.value
        if hasattr(PublishTaskStatus.cancelled, "value")
        else PublishTaskStatus.cancelled
    )
    await db.commit()
    return {"message": "任务已取消", "task_id": str(task_id)}


@router.get("/tasks/{task_id}/chapters", response_model=ChapterPublishListResponse)
async def get_task_chapter_publishes(
    task_id: UUID,
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取发布任务的章节发布记录."""
    # 检查任务存在
    task_result = await db.execute(select(PublishTask).where(PublishTask.id == task_id))
    if not task_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 未找到")

    offset = (page - 1) * page_size

    query = select(ChapterPublish).where(ChapterPublish.publish_task_id == task_id)
    count_query = (
        select(func.count())
        .select_from(ChapterPublish)
        .where(ChapterPublish.publish_task_id == task_id)
    )

    if status:
        query = query.where(ChapterPublish.status == status)
        count_query = count_query.where(ChapterPublish.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = (
        query.offset(offset).limit(page_size).order_by(ChapterPublish.chapter_number)
    )
    result = await db.execute(query)
    records = result.scalars().all()

    return ChapterPublishListResponse(items=records, total=total)


# ============================================================
# 发布预览
# ============================================================


@router.post("/preview", response_model=PublishPreviewResponse)
async def get_publish_preview(
    preview_in: PublishPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    获取发布预览。

    预览指定章节范围的发布情况，包括已发布/未发布状态。
    """
    service = PublishingService(db)
    preview = await service.get_publish_preview(
        novel_id=preview_in.novel_id,
        from_chapter=preview_in.from_chapter or 1,
        to_chapter=preview_in.to_chapter,
    )

    if "error" in preview:
        raise HTTPException(status_code=404, detail=preview["error"])

    return PublishPreviewResponse(
        novel_id=preview["novel_id"],
        novel_title=preview["novel_title"],
        total_chapters=preview["total_chapters"],
        unpublished_count=preview["unpublished_count"],
        chapters=[ChapterPreviewItem(**ch) for ch in preview["chapters"]],
    )
