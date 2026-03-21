"""小说相关的 Pydantic schemas（带输入验证）."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, HttpUrl


class NovelCreate(BaseModel):
    """创建小说的请求模型（带输入验证）."""

    title: str = Field(
        ...,
        description="小说标题",
        examples=["仙侠大陆"],
        min_length=1,
        max_length=100,
    )
    genre: str = Field(
        ...,
        description="小说类型，如：仙侠、都市、科幻、悬疑、武侠、言情、历史、游戏等",
        examples=["仙侠", "都市", "科幻"],
        min_length=1,
        max_length=50,
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="标签列表，用于分类和推荐",
        examples=[["升级", "战斗", "冒险"]],
        max_length=20,
    )
    synopsis: Optional[str] = Field(
        default=None,
        description="简介/大纲描述",
        max_length=5000,
    )
    target_platform: str = Field(
        default="番茄小说",
        description="目标发布平台，如：番茄小说、起点中文网、晋江文学城等",
        min_length=1,
        max_length=100,
    )
    length_type: str = Field(
        default="medium",
        description="小说篇幅类型：short(短文/5 万字以下)、medium(中篇/5-30 万字)、long(长篇/30 万字以上)",
        pattern="^(short|medium|long)$",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题：不能只包含空白字符，不能包含特殊字符."""
        if not v.strip():
            raise ValueError("标题不能为空或只包含空白字符")
        # 禁止特殊字符（允许中英文、数字、常见标点）
        if re.search(r'[<>{}|\\^`]', v):
            raise ValueError("标题包含非法字符")
        return v.strip()

    @field_validator("genre")
    @classmethod
    def validate_genre(cls, v: str) -> str:
        """验证类型：不能只包含空白字符."""
        if not v.strip():
            raise ValueError("小说类型不能为空")
        return v.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """验证标签：每个标签不能为空，不能有重复."""
        if v is None:
            return v
        # 过滤空标签
        cleaned_tags = [tag.strip() for tag in v if tag and tag.strip()]
        # 检查重复
        if len(cleaned_tags) != len(set(cleaned_tags)):
            raise ValueError("标签列表包含重复项")
        # 验证每个标签长度
        for tag in cleaned_tags:
            if len(tag) > 50:
                raise ValueError(f"标签 '{tag}' 长度超过 50 字符限制")
        return cleaned_tags


class NovelUpdate(BaseModel):
    """更新小说的请求模型（仅更新提供的字段，带输入验证）."""

    title: Optional[str] = Field(
        default=None,
        description="小说标题",
        min_length=1,
        max_length=100,
    )
    genre: Optional[str] = Field(
        default=None,
        description="小说类型",
        min_length=1,
        max_length=50,
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="标签列表",
        max_length=20,
    )
    synopsis: Optional[str] = Field(
        default=None,
        description="简介",
        max_length=5000,
    )
    status: Optional[str] = Field(
        default=None,
        description="小说状态：planning(企划中)、writing(写作中)、completed(已完成)、published(已发布)",
        pattern="^(planning|writing|completed|published)$",
    )
    cover_url: Optional[str] = Field(
        default=None,
        description="封面图片 URL",
        max_length=500,
    )
    target_platform: Optional[str] = Field(
        default=None,
        description="目标发布平台",
        min_length=1,
        max_length=100,
    )
    length_type: Optional[str] = Field(
        default=None,
        description="小说篇幅类型：short(短文)、medium(中篇)、long(长篇)",
        pattern="^(short|medium|long)$",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """验证标题."""
        if v is not None:
            if not v.strip():
                raise ValueError("标题不能为空或只包含空白字符")
            if re.search(r'[<>{}|\\^`]', v):
                raise ValueError("标题包含非法字符")
            return v.strip()
        return v

    @field_validator("cover_url")
    @classmethod
    def validate_cover_url(cls, v: Optional[str]) -> Optional[str]:
        """验证封面 URL 格式."""
        if v is not None and v.strip():
            # 简单验证 URL 格式
            if not re.match(r'^https?://', v):
                raise ValueError("封面 URL 必须以 http://或 https://开头")
            if len(v) > 500:
                raise ValueError("封面 URL 长度超过 500 字符限制")
            return v.strip()
        return v


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
    word_count: int = Field(..., description="当前总字数", ge=0)
    chapter_count: int = Field(..., description="当前章节数", ge=0)
    cover_url: Optional[str] = Field(default=None, description="封面图片 URL")
    synopsis: Optional[str] = Field(default=None, description="简介/大纲描述")
    target_platform: str = Field(..., description="目标发布平台")
    estimated_revenue: float = Field(..., description="预估收益（元）", ge=0)
    actual_revenue: float = Field(..., description="实际收益（元）", ge=0)
    token_cost: float = Field(..., description="AI 生成消耗的 Token 成本（元）", ge=0)
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
    total: int = Field(..., description="符合条件的小说总数", ge=0)
    page: Optional[int] = Field(default=None, description="当前页码", ge=1)
    page_size: Optional[int] = Field(default=None, description="每页数量", ge=1, le=100)
