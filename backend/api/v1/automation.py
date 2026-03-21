"""自动化API."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.automation_service import AutomationService
from core.database import get_db

router = APIRouter(prefix="/automation", tags=["自动化"])


@router.post("/novel-creation")
async def run_automated_novel_creation(
    novel_id: Optional[UUID] = Body(None, description="小说ID，如果为None则创建新小说"),
    config: Dict[str, Any] = Body(default={}, description="配置参数"),
    db: AsyncSession = Depends(get_db),
):
    """运行自动化小说创建流程."""
    service = AutomationService(db)
    result = await service.run_automated_novel_creation(
        novel_id=novel_id,
        config=config,
    )
    return {
        "success": result.get("status") == "completed",
        "data": result,
    }


@router.get("/workflow-status/{workflow_id}")
async def get_workflow_status(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取工作流状态."""
    service = AutomationService(db)
    status = await service.get_workflow_status(workflow_id)
    return {
        "success": True,
        "data": status,
    }


@router.post("/batch-automation")
async def run_batch_automation(
    batch_config: List[Dict[str, Any]] = Body(..., description="批量配置列表"),
    db: AsyncSession = Depends(get_db),
):
    """运行批量自动化任务."""
    service = AutomationService(db)
    result = await service.run_batch_automation(batch_config)
    return {
        "success": True,
        "data": result,
    }


@router.post("/initialize-agents")
async def initialize_agents(
    db: AsyncSession = Depends(get_db),
):
    """初始化所有代理."""
    service = AutomationService(db)
    await service.initialize_agents()
    return {
        "success": True,
        "message": "所有代理初始化完成",
    }


@router.get("/market-report")
async def generate_market_report(
    days: int = Query(7, description="分析天数"),
    platforms: List[str] = Query(None, description="包含的平台"),
    db: AsyncSession = Depends(get_db),
):
    """生成市场报告."""
    from backend.services.market_analysis_service import MarketAnalysisService

    service = MarketAnalysisService(db)
    report = await service.generate_market_report(
        days=days,
        include_platforms=platforms,
    )
    return {
        "success": True,
        "data": report,
    }
