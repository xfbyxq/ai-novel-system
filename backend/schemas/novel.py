"""小说相关的 Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NovelCreate(BaseModel):
    """创建小说的请求模型."""

    title: str = Field(..., description="小说标题", examples=["仙侠大陆"])
    genre: str = Field(
        ...,
        description="小说类型，如：仙侠、都市、科幻、悬疑、武侠、言情、历史、游戏等",
        examples=["仙侠", "都市", "科幻"],
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="标签列表，用于分类和推荐",
        examples=[["升级", "战斗", "冒险"]],
    )
    synopsis: Optional[str] = Field(default=None, description="简介/大纲描述")
    target_platform: str = Field(
        default="番茄小说",
        description="目标发布平台，如：番茄小说、起点中文网、晋江文学城等",
    )
    length_type: str = Field(
        default="medium",
        description="小说篇幅类型：short(短文/5万字以下)、medium(中篇/5-30万字)、long(长篇/30万字以上)",
    )


class NovelUpdate(BaseModel):
    """更新小说的请求模型（仅更新提供的字段）."""

    title: Optional[str] = Field(default=None, description="小说标题")
    genre: Optional[str] = Field(default=None, description="小说类型")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    synopsis: Optional[str] = Field(default=None, description="简介")
    status: Optional[str] = Field(
        default=None,
        description="小说状态：planning(企划中)、writing(写作中)、completed(已完成)、published(已发布)",
    )
    cover_url: Optional[str] = Field(default=None, description="封面图片URL")
    target_platform: Optional[str] = Field(default=None, description="目标发布平台")
    length_type: Optional[str] = Field(
        default=None, description="小说篇幅类型：short(短文)、medium(中篇)、long(长篇)"
    )


class NovelResponse(BaseModel):
    """小说响应模型."""

    id: UUID = Field(..., description="小说唯一标识符")
    title: str = Field(..., description="小说标题")
    author: str = Field(..., description="作者名称")
    genre: str = Field(..., description="小说类型")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    status: str = Field(
        ...,
        description="小说状态：planning(企划中)、writing(写作中)、completed(已完成)、published(已发布)",
    )
    length_type: str = Field(..., description="小说篇幅类型：short/medium/long")
    word_count: int = Field(..., description="当前总字数")
    chapter_count: int = Field(..., description="当前章节数")
    cover_url: Optional[str] = Field(default=None, description="封面图片URL")
    synopsis: Optional[str] = Field(default=None, description="简介/大纲描述")
    target_platform: str = Field(..., description="目标发布平台")
    estimated_revenue: float = Field(..., description="预估收益（元）")
    actual_revenue: float = Field(..., description="实际收益（元）")
    token_cost: float = Field(..., description="AI生成消耗的Token成本（元）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "仙侠大陆",
                "author": "系统生成",
                "genre": "仙侠",
                "tags": ["升级", "战斗", "冒险"],
                "status": "writing",
                "length_type": "long",
                "word_count": 150000,
                "chapter_count": 50,
                "cover_url": "https://example.com/cover.jpg",
                "synopsis": "主角获得奇遇，踏上修仙之路...",
                "target_platform": "番茄小说",
                "estimated_revenue": 10000.0,
                "actual_revenue": 5000.0,
                "token_cost": 250.0,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-03-01T12:00:00Z",
            }
        },
    )


class NovelListResponse(BaseModel):
    """小说列表响应模型（分页）."""

    items: list[NovelResponse] = Field(..., description="小说列表")
    total: int = Field(..., description="符合条件的小说总数")
    page: Optional[int] = Field(default=None, description="当前页码")
    page_size: Optional[int] = Field(default=None, description="每页数量")
