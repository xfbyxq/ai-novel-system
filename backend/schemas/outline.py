"""大纲相关的 Pydantic schemas"""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class WorldSettingResponse(BaseModel):
    """世界观设定响应模型"""
    id: UUID = Field(..., description="世界观ID")
    novel_id: UUID = Field(..., description="所属小说ID")
    world_name: Optional[str] = Field(default=None, description="世界名称")
    world_type: Optional[str] = Field(default=None, description="世界类型")
    power_system: Optional[dict] = Field(default=None, description="力量体系")
    geography: Optional[dict] = Field(default=None, description="地理设定")
    factions: Optional[list] = Field(default=None, description="势力组织")
    rules: Optional[list] = Field(default=None, description="世界规则")
    timeline: Optional[list] = Field(default=None, description="时间线")
    special_elements: Optional[list] = Field(default=None, description="特殊元素")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class WorldSettingUpdate(BaseModel):
    """更新世界观设定的请求模型"""
    world_name: Optional[str] = Field(default=None, description="世界名称")
    world_type: Optional[str] = Field(default=None, description="世界类型")
    power_system: Optional[dict] = Field(default=None, description="力量体系")
    geography: Optional[dict] = Field(default=None, description="地理设定")
    factions: Optional[list] = Field(default=None, description="势力组织")
    rules: Optional[list] = Field(default=None, description="世界规则")
    timeline: Optional[list] = Field(default=None, description="时间线")
    special_elements: Optional[list] = Field(default=None, description="特殊元素")


class PlotOutlineResponse(BaseModel):
    """剧情大纲响应模型"""
    id: UUID = Field(..., description="大纲ID")
    novel_id: UUID = Field(..., description="所属小说ID")
    structure_type: Optional[str] = Field(default=None, description="结构类型")
    volumes: Optional[list] = Field(default=None, description="卷/篇设定")
    main_plot: Optional[dict] = Field(default=None, description="主线剧情")
    sub_plots: Optional[list] = Field(default=None, description="支线剧情")
    key_turning_points: Optional[list] = Field(default=None, description="关键转折点")
    climax_chapter: Optional[int] = Field(default=None, description="高潮章节")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class PlotOutlineUpdate(BaseModel):
    """更新剧情大纲的请求模型"""
    structure_type: Optional[str] = Field(default=None, description="结构类型")
    volumes: Optional[list] = Field(default=None, description="卷/篇设定")
    main_plot: Optional[dict] = Field(default=None, description="主线剧情")
    sub_plots: Optional[list] = Field(default=None, description="支线剧情")
    key_turning_points: Optional[list] = Field(default=None, description="关键转折点")
    climax_chapter: Optional[int] = Field(default=None, description="高潮章节")


class ChapterCreate(BaseModel):
    """创建章节的请求模型"""
    chapter_number: int = Field(..., description="章节号")
    volume_number: int = Field(default=1, description="卷号")
    title: Optional[str] = Field(default=None, description="章节标题")


class ChapterUpdate(BaseModel):
    """更新章节的请求模型"""
    title: Optional[str] = Field(default=None, description="章节标题")
    content: Optional[str] = Field(default=None, description="章节内容")
    status: Optional[str] = Field(default=None, description="章节状态")


class ChapterResponse(BaseModel):
    """章节响应模型"""
    id: UUID = Field(..., description="章节ID")
    novel_id: UUID = Field(..., description="所属小说ID")
    chapter_number: int = Field(..., description="章节号")
    volume_number: int = Field(..., description="卷号")
    title: Optional[str] = Field(default=None, description="章节标题")
    content: Optional[str] = Field(default=None, description="章节内容")
    word_count: int = Field(..., description="字数")
    status: str = Field(..., description="章节状态")
    quality_score: Optional[float] = Field(default=None, description="质量评分")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class ChapterListResponse(BaseModel):
    """章节列表响应模型"""
    items: list[ChapterResponse] = Field(..., description="章节列表")
    total: int = Field(..., description="总数")
