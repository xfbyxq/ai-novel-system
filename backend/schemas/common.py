"""通用响应 Schema"""

from typing import Optional

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """通用消息响应"""

    message: str = Field(..., description="操作结果消息")


class TaskCancelResponse(BaseModel):
    """任务取消响应"""

    message: str = Field(..., description="取消结果消息")
    task_id: str = Field(..., description="被取消的任务ID")


class VerifyAccountResponse(BaseModel):
    """账号验证响应"""

    success: bool = Field(..., description="验证是否成功")
    message: str = Field(..., description="验证结果消息")


class DeleteResponse(BaseModel):
    """删除操作响应"""

    message: str = Field(..., description="删除结果消息")
    account_id: Optional[str] = Field(default=None, description="被删除的账号ID")
