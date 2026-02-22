"""生成任务相关的 Pydantic schemas"""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GenerationTaskCreate(BaseModel):
    """创建生成任务的请求模型"""
    novel_id: UUID = Field(..., description="所属小说ID")
    task_type: str = Field(..., description="任务类型: planning, writing, batch_writing")
    phase: Optional[str] = Field(default=None, description="生成阶段")
    input_data: Optional[dict] = Field(default=None, description="输入数据")
    # 批量写作专用字段
    from_chapter: Optional[int] = Field(default=None, description="批量生成起始章节号")
    to_chapter: Optional[int] = Field(default=None, description="批量生成结束章节号")
    volume_number: Optional[int] = Field(default=1, description="卷号")


class GenerationTaskResponse(BaseModel):
    """生成任务响应模型"""
    id: UUID = Field(..., description="任务ID")
    novel_id: UUID = Field(..., description="所属小说ID")
    task_type: str = Field(..., description="任务类型")
    phase: Optional[str] = Field(default=None, description="生成阶段")
    status: str = Field(..., description="任务状态")
    input_data: Optional[dict] = Field(default=None, description="输入数据")
    output_data: Optional[dict] = Field(default=None, description="输出数据")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    token_usage: int = Field(default=0, description="Token使用量")
    cost: Optional[float] = Field(default=None, description="成本")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    created_at: datetime = Field(..., description="创建时间")
    
    model_config = ConfigDict(from_attributes=True)


class GenerationTaskListResponse(BaseModel):
    """生成任务列表响应模型"""
    items: list[GenerationTaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数")
