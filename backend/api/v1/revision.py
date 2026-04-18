"""修订和记忆管理 API 端点."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.services.revision_understanding_service import RevisionUnderstandingService
from backend.services.revision_execution_service import RevisionExecutionService
from backend.services.hindsight_service import HindsightService
from llm.qwen_client import QwenClient


router = APIRouter(prefix="/revision", tags=["revision"])


def get_understanding_service(
    db: AsyncSession = Depends(get_db),
) -> RevisionUnderstandingService:
    """获取修订理解服务实例."""
    # 使用共享的LLM客户端
    llm = QwenClient()
    return RevisionUnderstandingService(db=db, llm=llm)


def get_execution_service(
    db: AsyncSession = Depends(get_db),
) -> RevisionExecutionService:
    """获取修订执行服务实例."""
    return RevisionExecutionService(db=db)


def get_hindsight_service(
    db: AsyncSession = Depends(get_db),
) -> HindsightService:
    """获取Hindsight服务实例."""
    llm = QwenClient()
    return HindsightService(db=db, llm=llm)


# ==================== Request/Response Models ====================


class RevisionFeedbackRequest(BaseModel):
    """修订反馈请求."""

    novel_id: str
    feedback: str


class RevisionPlanResponse(BaseModel):
    """修订计划响应."""

    plan_id: str
    understood_intent: str
    confidence: float
    targets: list[dict]
    proposed_changes: list[dict]
    impact_assessment: dict
    display_text: str


class RevisionExecuteRequest(BaseModel):
    """修订执行请求."""

    plan_id: str
    confirmed: bool = True
    modifications: Optional[dict] = None


class ExecutionResultResponse(BaseModel):
    """执行结果响应."""

    success: bool
    message: str
    changes: list[dict]
    affected_chapters: list[int]


class LessonRequest(BaseModel):
    """获取经验请求."""

    novel_id: str
    task_type: str = "writing"
    chapter: int = 0
    limit: int = 5


class LessonResponse(BaseModel):
    """经验响应."""

    lessons: list[str]


class StrategyRequest(BaseModel):
    """策略请求."""

    novel_id: str
    dimension: Optional[str] = None
    limit: int = 5


class StrategyResponse(BaseModel):
    """策略响应."""

    recommendations: list[dict]


class PreferenceRecordRequest(BaseModel):
    """偏好记录请求."""

    user_id: str
    preference_type: str
    preference_key: str
    preference_value: Any
    source: str = "explicit"
    novel_id: Optional[str] = None
    confidence: float = 0.8


class PreferenceResponse(BaseModel):
    """偏好响应."""

    id: str
    preference_key: str
    preference_type: str
    confidence: float


# ==================== Revision Endpoints ====================


@router.post("/understand", response_model=RevisionPlanResponse)
async def understand_feedback(
    request: RevisionFeedbackRequest,
    service: RevisionUnderstandingService = Depends(get_understanding_service),
):
    """理解用户修订反馈，生成修订计划.

    请求:
    ```json
    {
        "novel_id": "xxx",
        "feedback": "第5章张三性格有问题，第3章是稳重型，第5章变成冲动了"
    }
    ```

    响应:
    ```json
    {
        "plan_id": "xxx",
        "understood_intent": "修改角色'张三'的性格设定",
        "confidence": 0.85,
        "targets": [...],
        "proposed_changes": [...],
        "impact_assessment": {...},
        "display_text": "我理解了您的反馈..."
    }
    ```
    """
    try:
        plan = await service.understand_feedback(
            user_feedback=request.feedback,
            novel_id=request.novel_id,
        )

        return RevisionPlanResponse(
            plan_id=str(plan.id),
            understood_intent=plan.understood_intent,
            confidence=plan.confidence,
            targets=plan.targets or [],
            proposed_changes=plan.proposed_changes or [],
            impact_assessment=plan.impact_assessment or {},
            display_text=service.format_plan_for_display(plan),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"理解反馈失败: {str(e)}")


@router.post("/execute", response_model=ExecutionResultResponse)
async def execute_revision(
    request: RevisionExecuteRequest,
    service: RevisionExecutionService = Depends(get_execution_service),
):
    """执行修订计划.

    请求:
    ```json
    {
        "plan_id": "xxx",
        "confirmed": true,
        "modifications": {"personality": "更稳重一些"}
    }
    ```

    响应:
    ```json
    {
        "success": true,
        "message": "已完成 2/2 项修改，标记章节 5-7 需复查",
        "changes": [...],
        "affected_chapters": [5, 6, 7]
    }
    ```
    """
    result = await service.execute_plan(
        plan_id=request.plan_id,
        confirmed=request.confirmed,
        modifications=request.modifications,
    )

    return ExecutionResultResponse(
        success=result.success,
        message=result.message,
        changes=result.changes,
        affected_chapters=result.affected_chapters,
    )


@router.get("/preview/{plan_id}")
async def preview_revision_plan(
    plan_id: str,
    service: RevisionExecutionService = Depends(get_execution_service),
):
    """预览修订计划的影响.

    查看修改会影响到哪些章节。
    """
    preview = await service.preview_plan(plan_id)
    if "error" in preview:
        raise HTTPException(status_code=404, detail=preview["error"])
    return preview


@router.get("/plans/{novel_id}")
async def list_revision_plans(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取小说的修订计划列表."""
    from core.models import RevisionPlan
    from sqlalchemy import select

    stmt = select(RevisionPlan).where(
        RevisionPlan.novel_id == UUID(novel_id)
    ).order_by(RevisionPlan.created_at.desc())

    result = await db.execute(stmt)
    plans = result.scalars().all()

    return {
        "plans": [
            {
                "id": str(p.id),
                "feedback_text": p.feedback_text,
                "understood_intent": p.understood_intent,
                "status": p.status,
                "confidence": p.confidence,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plans
        ]
    }


# ==================== Hindsight Endpoints ====================


@router.get("/lessons/{novel_id}", response_model=LessonResponse)
async def get_applicable_lessons(
    novel_id: str,
    task_type: str = "writing",
    chapter: int = 0,
    limit: int = 5,
    service: HindsightService = Depends(get_hindsight_service),
):
    """获取适用于当前任务的过往经验.

    用于注入到Agent prompt中。
    """
    lessons = await service.get_applicable_lessons(
        novel_id=novel_id,
        task_type=task_type,
        current_chapter=chapter,
        limit=limit,
    )

    return LessonResponse(lessons=lessons)


@router.get("/strategies/{novel_id}", response_model=StrategyResponse)
async def get_strategy_recommendations(
    novel_id: str,
    dimension: Optional[str] = None,
    limit: int = 5,
    service: HindsightService = Depends(get_hindsight_service),
):
    """获取策略建议 - 推荐最有效的修订策略."""
    recommendations = await service.get_strategy_recommendations(
        novel_id=novel_id,
        target_dimension=dimension,
        limit=limit,
    )

    return StrategyResponse(recommendations=recommendations)


@router.post("/strategies/record")
async def record_strategy_result(
    novel_id: str,
    strategy_name: str,
    strategy_type: str,
    target_dimension: str,
    effectiveness_score: float,
    service: HindsightService = Depends(get_hindsight_service),
):
    """记录策略应用结果.

    每次修订/优化后调用。
    """
    strategy = await service.record_strategy_result(
        novel_id=novel_id,
        strategy_name=strategy_name,
        strategy_type=strategy_type,
        target_dimension=target_dimension,
        effectiveness_score=effectiveness_score,
    )

    return {
        "strategy_name": strategy.strategy_name,
        "avg_effectiveness": strategy.avg_effectiveness,
        "application_count": strategy.application_count,
        "trend": strategy.trend,
    }


@router.post("/review")
async def execute_hindsight_review(
    novel_id: str,
    task_type: str,
    chapter_number: int = 0,
    initial_goal: Optional[str] = None,
    initial_plan: Optional[dict] = None,
    actual_result: Optional[str] = None,
    outcome_score: float = 0.0,
    applied_strategies: Optional[list[str]] = None,
    service: HindsightService = Depends(get_hindsight_service),
):
    """执行事后回顾.

    在每次写作/修订任务完成后调用。
    """
    experience = await service.execute_review(
        novel_id=novel_id,
        task_type=task_type,
        chapter_number=chapter_number,
        initial_goal=initial_goal,
        initial_plan=initial_plan,
        actual_result=actual_result,
        outcome_score=outcome_score,
        applied_strategies=applied_strategies,
    )

    return {
        "experience_id": str(experience.id),
        "lessons_learned": experience.lessons_learned,
        "successful_strategies": experience.successful_strategies,
        "failed_strategies": experience.failed_strategies,
        "recurring_pattern": experience.recurring_pattern,
    }


# ==================== Preference Endpoints ====================


@router.post("/preferences", response_model=PreferenceResponse)
async def record_preference(
    request: PreferenceRecordRequest,
    service: HindsightService = Depends(get_hindsight_service),
):
    """记录用户偏好."""
    preference = await service.record_user_preference(
        user_id=request.user_id,
        preference_type=request.preference_type,
        preference_key=request.preference_key,
        preference_value=request.preference_value,
        source=request.source,
        novel_id=request.novel_id,
        confidence=request.confidence,
    )

    return PreferenceResponse(
        id=str(preference.id),
        preference_key=preference.preference_key,
        preference_type=preference.preference_type,
        confidence=preference.confidence,
    )


@router.get("/preferences/{user_id}")
async def get_user_preferences(
    user_id: str,
    preference_types: Optional[str] = None,
    min_confidence: float = 0.5,
    service: HindsightService = Depends(get_hindsight_service),
):
    """获取用户偏好列表."""
    types = preference_types.split(",") if preference_types else None

    preferences = await service.get_user_preferences(
        user_id=user_id,
        preference_types=types,
        min_confidence=min_confidence,
    )

    return {
        "preferences": [
            {
                "id": str(p.id),
                "preference_type": p.preference_type,
                "preference_key": p.preference_key,
                "preference_value": p.preference_value,
                "confidence": p.confidence,
                "source": p.source,
            }
            for p in preferences
        ]
    }


@router.get("/preferences/{user_id}/context")
async def get_preference_context(
    user_id: str,
    service: HindsightService = Depends(get_hindsight_service),
):
    """获取偏好上下文文本.

    用于注入到Agent prompt中。
    """
    preferences = await service.get_user_preferences(
        user_id=user_id,
        min_confidence=0.5,
    )

    if not preferences:
        return {"context": ""}

    # 格式化偏好为prompt
    lines = ["【用户偏好提醒】"]
    for p in preferences:
        if p.preference_type == "ending" and p.preference_key == "hate_be":
            lines.append("- 用户不喜欢悲剧结局，请避免此类设计")
        elif p.preference_type == "character":
            lines.append(f"- 用户对{p.preference_key}有偏好")
        # 可以根据需要添加更多格式化规则

    return {"context": "\n".join(lines)}
