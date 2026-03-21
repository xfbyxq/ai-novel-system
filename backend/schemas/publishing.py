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

    platform: str = Field(
        default="qidian",
        description="平台名称：qidian(起点中文网)、jjwxc(晋江文学城)、hongxiu(红袖添香)、zongheng(纵横文学)、17k(17K小说网)、fanqie(番茄小说)",
    )
    account_name: str = Field(
        ..., description="账号名称/昵称，用于标识", max_length=100
    )
    username: str = Field(..., description="平台登录用户名", max_length=100)
    password: str = Field(..., description="平台登录密码（系统会加密存储）")
    extra_credentials: Optional[dict] = Field(
        default=None,
        description="其他凭证信息，格式: {mobile: '手机号', device_id: '设备ID', ...}",
    )


class PlatformAccountUpdate(BaseModel):
    """更新平台账号的请求模型（仅更新提供的字段）"""

    account_name: Optional[str] = Field(default=None, description="账号名称/昵称")
    password: Optional[str] = Field(default=None, description="登录密码")
    extra_credentials: Optional[dict] = Field(default=None, description="其他凭证信息")
    status: Optional[str] = Field(
        default=None,
        description="账号状态：active(正常)、inactive(禁用)、expired(过期)",
    )


class PlatformAccountResponse(BaseModel):
    """平台账号响应模型"""

    id: UUID = Field(..., description="账号唯一标识符")
    platform: str = Field(..., description="平台名称")
    account_name: str = Field(..., description="账号名称/昵称")
    username: str = Field(..., description="登录用户名")
    status: str = Field(..., description="账号状态：active/inactive/expired")
    last_login_at: Optional[datetime] = Field(default=None, description="最后登录时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class PlatformAccountListResponse(BaseModel):
    """平台账号列表响应模型"""

    items: list[PlatformAccountResponse] = Field(..., description="账号列表")
    total: int = Field(..., description="符合条件的账号总数")


# ============================================================
# PublishTask Schemas
# ============================================================


class PublishTaskCreate(BaseModel):
    """创建发布任务的请求模型"""

    novel_id: UUID = Field(..., description="要发布的小说ID")
    account_id: UUID = Field(..., description="使用的平台账号ID")
    publish_type: str = Field(
        ...,
        description="发布类型：create_book(创建新书)、publish_chapter(发布单章)、batch_publish(批量发布多章)",
    )
    config: Optional[dict] = Field(default=None, description="发布配置，如章节范围等")
    # 批量发布专用字段
    from_chapter: Optional[int] = Field(
        default=None, description="批量发布起始章节号（含）"
    )
    to_chapter: Optional[int] = Field(
        default=None, description="批量发布结束章节号（含）"
    )


class PublishTaskResponse(BaseModel):
    """发布任务响应模型"""

    id: UUID = Field(..., description="任务唯一标识符")
    novel_id: UUID = Field(..., description="小说ID")
    account_id: UUID = Field(..., description="平台账号ID")
    publish_type: str = Field(..., description="发布类型")
    config: Optional[dict] = Field(default=None, description="发布配置")
    status: str = Field(
        ...,
        description="任务状态：pending(等待中)、running(执行中)、completed(已完成)、failed(失败)、cancelled(已取消)",
    )
    progress: Optional[dict] = Field(
        default=None, description="进度信息，如 {current: 5, total: 10}"
    )
    result_summary: Optional[dict] = Field(default=None, description="结果摘要")
    error_message: Optional[str] = Field(
        default=None, description="错误信息（仅失败时有值）"
    )
    platform_book_id: Optional[str] = Field(default=None, description="平台上的书籍ID")
    started_at: Optional[datetime] = Field(default=None, description="任务开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="任务完成时间")
    created_at: datetime = Field(..., description="任务创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class PublishTaskListResponse(BaseModel):
    """发布任务列表响应模型"""

    items: list[PublishTaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="符合条件的任务总数")


# ============================================================
# ChapterPublish Schemas
# ============================================================


class ChapterPublishResponse(BaseModel):
    """章节发布记录响应模型"""

    id: UUID = Field(..., description="记录唯一标识符")
    publish_task_id: UUID = Field(..., description="所属发布任务ID")
    chapter_id: UUID = Field(..., description="章节ID")
    chapter_number: int = Field(..., description="章节序号")
    status: str = Field(
        ..., description="发布状态：pending/publishing/published/failed"
    )
    platform_chapter_id: Optional[str] = Field(
        default=None, description="平台上的章节ID"
    )
    error_message: Optional[str] = Field(default=None, description="错误信息")
    published_at: Optional[datetime] = Field(default=None, description="发布成功时间")
    created_at: datetime = Field(..., description="记录创建时间")

    model_config = ConfigDict(from_attributes=True)


class ChapterPublishListResponse(BaseModel):
    """章节发布记录列表响应模型"""

    items: list[ChapterPublishResponse] = Field(..., description="发布记录列表")
    total: int = Field(..., description="符合条件的记录总数")


# ============================================================
# 发布预览 Schemas
# ============================================================


class PublishPreviewRequest(BaseModel):
    """发布预览请求"""

    novel_id: UUID = Field(..., description="小说ID")
    from_chapter: Optional[int] = Field(default=1, description="预览起始章节号")
    to_chapter: Optional[int] = Field(
        default=None, description="预览结束章节号（不指定则到最后一章）"
    )


class ChapterPreviewItem(BaseModel):
    """章节预览项"""

    chapter_number: int = Field(..., description="章节号")
    title: str = Field(..., description="章节标题")
    word_count: int = Field(..., description="章节字数")
    status: str = Field(..., description="章节状态")
    is_published: bool = Field(..., description="是否已发布到平台")
    published_at: Optional[datetime] = Field(default=None, description="发布时间")


class PublishPreviewResponse(BaseModel):
    """发布预览响应"""

    novel_id: UUID = Field(..., description="小说ID")
    novel_title: str = Field(..., description="小说标题")
    total_chapters: int = Field(..., description="总章节数")
    unpublished_count: int = Field(..., description="未发布章节数")
    chapters: list[ChapterPreviewItem] = Field(..., description="章节预览列表")
