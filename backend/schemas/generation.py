"""生成任务相关的 Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GenerationTaskCreate(BaseModel):
    """创建生成任务的请求模型."""

    novel_id: UUID = Field(..., description="所属小说ID")
    task_type: str = Field(
        ...,
        description=(
            "任务类型：planning(企划阶段，生成世界观/角色/大纲)、"
            "writing(单章写作)、batch_writing(批量章节写作)、"
            "outline_refinement(大纲完善)"
        ),
    )
    phase: Optional[str] = Field(
        default=None,
        description="生成阶段，通常与task_type一致，可选：planning、writing、batch_writing、outline_refinement",
    )
    input_data: Optional[dict] = Field(
        default=None,
        description="""输入数据，根据task_type不同格式不同：.
        - planning: {} (无需额外参数)
        - writing: {"chapter_number": 1, "volume_number": 1} (指定章节号和卷号)
        - batch_writing: 无需在此指定，使用 from_chapter/to_chapter 字段""",
    )
    # 批量写作专用字段
    from_chapter: Optional[int] = Field(default=None, description="批量写作起始章节号（含）")
    to_chapter: Optional[int] = Field(default=None, description="批量写作结束章节号（含）")
    volume_number: Optional[int] = Field(default=1, description="卷号，默认为1")


class GenerationTaskResponse(BaseModel):
    """生成任务响应模型."""

    id: UUID = Field(..., description="任务唯一标识符")
    novel_id: UUID = Field(..., description="所属小说ID")
    task_type: str = Field(..., description="任务类型：planning/writing/batch_writing")
    phase: Optional[str] = Field(default=None, description="生成阶段")
    status: str = Field(
        ...,
        description="任务状态：pending(等待中)、running(执行中)、completed(已完成)、failed(失败)、cancelled(已取消)",
    )
    input_data: Optional[dict] = Field(default=None, description="输入数据")
    output_data: Optional[dict] = Field(default=None, description="输出数据/生成结果")
    error_message: Optional[str] = Field(default=None, description="错误信息（仅失败时有值）")
    checkpoint_data: Optional[dict] = Field(
        default=None, description="断点数据（批量写作中断时保存）"
    )
    token_usage: int = Field(default=0, description="Token消耗量")
    cost: Optional[float] = Field(default=None, description="成本（元）")
    started_at: Optional[datetime] = Field(default=None, description="任务开始执行时间")
    completed_at: Optional[datetime] = Field(default=None, description="任务完成时间")
    created_at: datetime = Field(..., description="任务创建时间")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "novel_id": "550e8400-e29b-41d4-a716-446655440000",
                "task_type": "writing",
                "phase": "writing",
                "status": "completed",
                "input_data": {"chapter_number": 1, "volume_number": 1},
                "output_data": {"chapter_id": "...", "word_count": 3000},
                "error_message": None,
                "token_usage": 5000,
                "cost": 0.15,
                "started_at": "2024-03-01T10:00:00Z",
                "completed_at": "2024-03-01T10:05:00Z",
                "created_at": "2024-03-01T09:59:00Z",
            }
        },
    )


class GenerationTaskListResponse(BaseModel):
    """生成任务列表响应模型."""

    items: list[GenerationTaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="符合条件的任务总数")
