"""大纲相关的 Pydantic schemas"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorldSettingResponse(BaseModel):
    """世界观设定响应模型"""
    id: UUID = Field(..., description="世界观设定唯一标识符")
    novel_id: UUID = Field(..., description="所属小说ID")
    world_name: Optional[str] = Field(default=None, description="世界名称，如'青玄大陆'、'蔚蓝星'")
    world_type: Optional[str] = Field(
        default=None, description="世界类型：仙侠/都市/科幻/武侠/悬疑等"
    )
    power_system: Optional[dict] = Field(
        default=None,
        description="力量体系，格式: {name: 体系名, levels: [等级列表], description: 描述}"
    )
    geography: Optional[dict] = Field(
        default=None,
        description="地理设定，格式: {regions: [{name, description, features}], landmarks: [...]}}"
    )
    factions: Optional[list] = Field(
        default=None,
        description="势力组织列表，每项格式: {name, type, power_level, leader, description}"
    )
    rules: Optional[list] = Field(
        default=None, description="世界运行规则列表"
    )
    timeline: Optional[list] = Field(
        default=None, description="历史时间线列表"
    )
    special_elements: Optional[list] = Field(
        default=None, description="特殊元素列表"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class WorldSettingUpdate(BaseModel):
    """更新世界观设定的请求模型（仅更新提供的字段，不存在时自动创建）"""
    world_name: Optional[str] = Field(default=None, description="世界名称")
    world_type: Optional[str] = Field(
        default=None,
        description="世界类型，如：仙侠、都市、科幻、武侠、悬疑等"
    )
    power_system: Optional[dict] = Field(
        default=None,
        description="力量体系，格式: {name, levels: [], description}"
    )
    geography: Optional[dict] = Field(
        default=None,
        description="地理设定，格式: {regions: [{name: '东域', features: [...]}], landmarks: [...]}"
    )
    factions: Optional[list] = Field(
        default=None,
        description="势力组织列表，每项格式: {name: '天剑宗', type: '宗门', power_level: 'S级'}"
    )
    rules: Optional[list] = Field(default=None, description="世界运行规则列表")
    timeline: Optional[list] = Field(
        default=None,
        description="历史时间线，每项格式: {time, event, significance}"
    )
    special_elements: Optional[list] = Field(
        default=None, description="特殊元素列表"
    )


class PlotOutlineResponse(BaseModel):
    """剧情大纲响应模型"""
    id: UUID = Field(..., description="大纲唯一标识符")
    novel_id: UUID = Field(..., description="所属小说ID")
    structure_type: Optional[str] = Field(
        default=None,
        description="结构类型，如：三幕式、英雄之旅、多线叙事等"
    )
    volumes: Optional[list] = Field(
        default=None,
        description="卷/篇设定列表，每项格式: {number, title, chapters, summary}"
    )
    main_plot: Optional[dict] = Field(
        default=None,
        description="主线剧情，格式: {setup, conflict, climax, resolution}"
    )
    sub_plots: Optional[list] = Field(
        default=None,
        description="支线剧情列表，每项格式: {name: '感情线', characters: [...], arc: '...'}"
    )
    key_turning_points: Optional[list] = Field(
        default=None,
        description="关键转折点列表，每项格式: {chapter: 10, event: '获得神器', impact: '实力飞跃'}"
    )
    climax_chapter: Optional[int] = Field(default=None, description="高潮章节号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class PlotOutlineUpdate(BaseModel):
    """更新剧情大纲的请求模型（仅更新提供的字段，不存在时自动创建）"""
    structure_type: Optional[str] = Field(
        default=None, description="结构类型：三幕式/英雄之旅等"
    )
    volumes: Optional[list] = Field(
        default=None,
        description="卷/篇设定列表，每项格式: {number, title, chapters: [start, end], summary}"
    )
    main_plot: Optional[dict] = Field(
        default=None,
        description="主线剧情，格式: {setup, conflict, climax, resolution}"
    )
    sub_plots: Optional[list] = Field(
        default=None,
        description="支线剧情列表，每项格式: {name, characters, arc}"
    )
    key_turning_points: Optional[list] = Field(
        default=None,
        description="关键转折点列表，每项格式: {chapter, event, impact}"
    )
    climax_chapter: Optional[int] = Field(default=None, description="高潮章节号")


class ChapterCreate(BaseModel):
    """创建章节的请求模型"""
    chapter_number: int = Field(..., description="章节号（从1开始）")
    volume_number: int = Field(default=1, description="所属卷号")
    title: Optional[str] = Field(default=None, description="章节标题")


class ChapterUpdate(BaseModel):
    """更新章节的请求模型（仅更新提供的字段）"""
    title: Optional[str] = Field(default=None, description="章节标题")
    content: Optional[str] = Field(default=None, description="章节正文内容")
    status: Optional[str] = Field(
        default=None,
        description="章节状态：draft(草稿)、reviewing(审核中)、published(已发布)"
    )


class ChapterResponse(BaseModel):
    """章节响应模型"""
    id: UUID = Field(..., description="章节唯一标识符")
    novel_id: UUID = Field(..., description="所属小说ID")
    chapter_number: int = Field(..., description="章节号")
    volume_number: int = Field(..., description="所属卷号")
    title: Optional[str] = Field(default=None, description="章节标题")
    content: Optional[str] = Field(default=None, description="章节正文内容")
    word_count: int = Field(..., description="章节字数")
    status: str = Field(..., description="章节状态：draft/reviewing/published")
    quality_score: Optional[float] = Field(default=None, description="AI评估的质量评分（0-10）")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class ChapterListResponse(BaseModel):
    """章节列表响应模型（分页）"""
    items: list[ChapterResponse] = Field(..., description="章节列表")
    total: int = Field(..., description="符合条件的章节总数")
    page: Optional[int] = Field(default=None, description="当前页码")
    page_size: Optional[int] = Field(default=None, description="每页数量")
