"""小说相关的 Pydantic schemas"""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class NovelCreate(BaseModel):
    """创建小说的请求模型"""
    title: str = Field(..., description="小说标题")
    genre: str = Field(..., description="小说类型")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    synopsis: Optional[str] = Field(default=None, description="简介")
    target_platform: str = Field(default="番茄小说", description="目标平台")
    length_type: str = Field(default="medium", description="小说篇幅类型: short(短文), medium(中篇小说), long(长篇小说)")


class NovelUpdate(BaseModel):
    """更新小说的请求模型"""
    title: Optional[str] = Field(default=None, description="小说标题")
    genre: Optional[str] = Field(default=None, description="小说类型")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    synopsis: Optional[str] = Field(default=None, description="简介")
    status: Optional[str] = Field(default=None, description="小说状态")
    cover_url: Optional[str] = Field(default=None, description="封面URL")
    target_platform: Optional[str] = Field(default=None, description="目标平台")
    length_type: Optional[str] = Field(default=None, description="小说篇幅类型: short(短文), medium(中篇小说), long(长篇小说)")


class NovelResponse(BaseModel):
    """小说响应模型"""
    id: UUID = Field(..., description="小说ID")
    title: str = Field(..., description="小说标题")
    author: str = Field(..., description="作者")
    genre: str = Field(..., description="小说类型")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    status: str = Field(..., description="小说状态")
    length_type: str = Field(..., description="小说篇幅类型")
    word_count: int = Field(..., description="字数")
    chapter_count: int = Field(..., description="章节数")
    cover_url: Optional[str] = Field(default=None, description="封面URL")
    synopsis: Optional[str] = Field(default=None, description="简介")
    target_platform: str = Field(..., description="目标平台")
    estimated_revenue: float = Field(..., description="预估收益")
    actual_revenue: float = Field(..., description="实际收益")
    token_cost: float = Field(..., description="Token成本")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class NovelListResponse(BaseModel):
    """小说列表响应模型"""
    items: list[NovelResponse] = Field(..., description="小说列表")
    total: int = Field(..., description="总数")
