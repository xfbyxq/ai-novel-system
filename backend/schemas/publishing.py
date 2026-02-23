"""发布系统相关的 Pydantic schemas"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# PlatformAccount Schemas
# ============================================================

class PlatformAccountCreate(BaseModel):
    """创建平台账号的请求模型"""
    platform: str = Field(default="qidian", description="平台名称")
    account_name: str = Field(..., description="账号名称/昵称", max_length=100)
    username: str = Field(..., description="登录用户名", max_length=100)
    password: str = Field(..., description="登录密码")
    extra_credentials: Optional[dict] = Field(default=None, description="其他凭证信息")


class PlatformAccountUpdate(BaseModel):
    """更新平台账号的请求模型"""
    account_name: Optional[str] = Field(default=None, description="账号名称/昵称")
    password: Optional[str] = Field(default=None, description="登录密码")
    extra_credentials: Optional[dict] = Field(default=None, description="其他凭证信息")
    status: Optional[str] = Field(default=None, description="账号状态")


class PlatformAccountResponse(BaseModel):
    """平台账号响应模型"""
    id: UUID = Field(..., description="账号ID")
    platform: str = Field(..., description="平台名称")
    account_name: str = Field(..., description="账号名称")
    username: str = Field(..., description="登录用户名")
    status: str = Field(..., description="账号状态")
    last_login_at: Optional[datetime] = Field(default=None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class PlatformAccountListResponse(BaseModel):
    """平台账号列表响应模型"""
    items: list[PlatformAccountResponse] = Field(..., description="账号列表")
    total: int = Field(..., description="总数")


# ============================================================
# PublishTask Schemas
# ============================================================

class PublishTaskCreate(BaseModel):
    """创建发布任务的请求模型"""
    novel_id: UUID = Field(..., description="小说ID")
    account_id: UUID = Field(..., description="使用的平台账号ID")
    publish_type: str = Field(..., description="发布类型: create_book, publish_chapter, batch_publish")
    config: Optional[dict] = Field(default=None, description="发布配置")
    # 批量发布专用字段
    from_chapter: Optional[int] = Field(default=None, description="起始章节号")
    to_chapter: Optional[int] = Field(default=None, description="结束章节号")


class PublishTaskResponse(BaseModel):
    """发布任务响应模型"""
    id: UUID = Field(..., description="任务ID")
    novel_id: UUID = Field(..., description="小说ID")
    account_id: UUID = Field(..., description="账号ID")
    publish_type: str = Field(..., description="发布类型")
    config: Optional[dict] = Field(default=None, description="发布配置")
    status: str = Field(..., description="任务状态")
    progress: Optional[dict] = Field(default=None, description="进度信息")
    result_summary: Optional[dict] = Field(default=None, description="结果摘要")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    platform_book_id: Optional[str] = Field(default=None, description="平台书籍ID")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class PublishTaskListResponse(BaseModel):
    """发布任务列表响应模型"""
    items: list[PublishTaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数")


# ============================================================
# ChapterPublish Schemas
# ============================================================

class ChapterPublishResponse(BaseModel):
    """章节发布记录响应模型"""
    id: UUID = Field(..., description="记录ID")
    publish_task_id: UUID = Field(..., description="发布任务ID")
    chapter_id: UUID = Field(..., description="章节ID")
    chapter_number: int = Field(..., description="章节序号")
    status: str = Field(..., description="发布状态")
    platform_chapter_id: Optional[str] = Field(default=None, description="平台章节ID")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    published_at: Optional[datetime] = Field(default=None, description="发布时间")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class ChapterPublishListResponse(BaseModel):
    """章节发布记录列表响应模型"""
    items: list[ChapterPublishResponse] = Field(..., description="记录列表")
    total: int = Field(..., description="总数")


# ============================================================
# 发布预览 Schemas
# ============================================================

class PublishPreviewRequest(BaseModel):
    """发布预览请求"""
    novel_id: UUID = Field(..., description="小说ID")
    from_chapter: Optional[int] = Field(default=1, description="起始章节")
    to_chapter: Optional[int] = Field(default=None, description="结束章节")


class ChapterPreviewItem(BaseModel):
    """章节预览项"""
    chapter_number: int = Field(..., description="章节号")
    title: str = Field(..., description="章节标题")
    word_count: int = Field(..., description="字数")
    status: str = Field(..., description="章节状态")
    is_published: bool = Field(..., description="是否已发布")
    published_at: Optional[datetime] = Field(default=None, description="发布时间")


class PublishPreviewResponse(BaseModel):
    """发布预览响应"""
    novel_id: UUID = Field(..., description="小说ID")
    novel_title: str = Field(..., description="小说标题")
    total_chapters: int = Field(..., description="总章节数")
    unpublished_count: int = Field(..., description="未发布章节数")
    chapters: list[ChapterPreviewItem] = Field(..., description="章节列表")
