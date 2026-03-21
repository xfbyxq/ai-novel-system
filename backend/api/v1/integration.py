"""集成API"""

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.integration_service import IntegrationService
from core.database import get_db

router = APIRouter(prefix="/integration", tags=["集成"])


@router.post("/end-to-end-workflow")
async def run_end_to_end_workflow(
    config: Dict[str, Any] = Body(default={}, description="工作流配置"),
    novel_id: Optional[UUID] = Body(None, description="小说ID，如果为None则创建新小说"),
    db: AsyncSession = Depends(get_db),
):
    """运行端到端的自动化小说创作和发布工作流"""
    service = IntegrationService(db)
    result = await service.run_end_to_end_workflow(
        config=config,
        novel_id=novel_id,
    )
    return {
        "success": result.get("status") == "completed",
        "data": result,
    }


@router.get("/workflow-history")
async def get_workflow_history(
    limit: int = Query(10, description="限制数量"),
    offset: int = Query(0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """获取工作流历史记录"""
    service = IntegrationService(db)
    history = await service.get_workflow_history(
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "data": history,
    }


@router.get("/workflow-detail/{workflow_id}")
async def get_workflow_detail(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取工作流详情"""
    service = IntegrationService(db)
    detail = await service.get_workflow_detail(workflow_id)
    return {
        "success": True,
        "data": detail,
    }
