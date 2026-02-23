"""爬虫相关的 Pydantic schemas"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# CrawlerTask Schemas
# ============================================================

class CrawlerTaskCreate(BaseModel):
    """创建爬虫任务的请求模型"""
    task_name: str = Field(..., description="任务名称", max_length=100)
    platform: str = Field(default="qidian", description="目标平台")
    crawl_type: str = Field(..., description="爬取类型: ranking, trending_tags, book_metadata, genre_list")
    config: Optional[dict] = Field(default=None, description="爬取配置（URL、筛选条件等）")


class CrawlerTaskResponse(BaseModel):
    """爬虫任务响应模型"""
    id: UUID = Field(..., description="任务ID")
    task_name: str = Field(..., description="任务名称")
    platform: str = Field(..., description="目标平台")
    crawl_type: str = Field(..., description="爬取类型")
    config: Optional[dict] = Field(default=None, description="爬取配置")
    status: str = Field(..., description="任务状态")
    progress: Optional[dict] = Field(default=None, description="进度信息")
    result_summary: Optional[dict] = Field(default=None, description="结果摘要")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class CrawlerTaskListResponse(BaseModel):
    """爬虫任务列表响应模型"""
    items: list[CrawlerTaskResponse] = Field(..., description="任务列表")
    total: int = Field(..., description="总数")


# ============================================================
# CrawlResult Schemas
# ============================================================

class CrawlResultResponse(BaseModel):
    """爬取结果响应模型"""
    id: UUID = Field(..., description="结果ID")
    crawler_task_id: UUID = Field(..., description="所属任务ID")
    platform: str = Field(..., description="数据来源平台")
    data_type: str = Field(..., description="数据类型")
    raw_data: Optional[dict] = Field(default=None, description="原始数据")
    processed_data: Optional[dict] = Field(default=None, description="处理后的数据")
    url: Optional[str] = Field(default=None, description="来源URL")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class CrawlResultListResponse(BaseModel):
    """爬取结果列表响应模型"""
    items: list[CrawlResultResponse] = Field(..., description="结果列表")
    total: int = Field(..., description="总数")


# ============================================================
# Market Data Schemas (聚合数据)
# ============================================================

class MarketDataItem(BaseModel):
    """市场数据项"""
    book_id: Optional[str] = Field(default=None, description="平台书籍ID")
    book_title: Optional[str] = Field(default=None, description="书名")
    author_name: Optional[str] = Field(default=None, description="作者")
    genre: Optional[str] = Field(default=None, description="类型")
    tags: Optional[list[str]] = Field(default=None, description="标签")
    rating: Optional[float] = Field(default=None, description="评分")
    word_count: Optional[int] = Field(default=None, description="字数")
    trend_score: Optional[float] = Field(default=None, description="趋势评分")
    source: str = Field(..., description="数据来源")
    data_date: Optional[str] = Field(default=None, description="数据日期")


class MarketDataResponse(BaseModel):
    """市场数据响应模型"""
    items: list[MarketDataItem] = Field(..., description="数据列表")
    total: int = Field(..., description="总数")


# ============================================================
# ReaderPreference Schemas (扩展)
# ============================================================

class ReaderPreferenceResponse(BaseModel):
    """读者偏好数据响应模型"""
    id: UUID = Field(..., description="ID")
    source: str = Field(..., description="数据来源")
    genre: Optional[str] = Field(default=None, description="类型")
    tags: Optional[list[str]] = Field(default=None, description="标签")
    ranking_data: Optional[dict] = Field(default=None, description="排名数据")
    comment_sentiment: Optional[dict] = Field(default=None, description="评论情感")
    trend_score: Optional[float] = Field(default=None, description="趋势评分")
    data_date: Optional[str] = Field(default=None, description="数据日期")
    # 新增字段
    crawler_task_id: Optional[UUID] = Field(default=None, description="关联爬虫任务ID")
    book_id: Optional[str] = Field(default=None, description="平台书籍ID")
    book_title: Optional[str] = Field(default=None, description="书名")
    author_name: Optional[str] = Field(default=None, description="作者")
    rating: Optional[float] = Field(default=None, description="评分")
    word_count: Optional[int] = Field(default=None, description="字数")
    created_at: datetime = Field(..., description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class ReaderPreferenceListResponse(BaseModel):
    """读者偏好列表响应模型"""
    items: list[ReaderPreferenceResponse] = Field(..., description="数据列表")
    total: int = Field(..., description="总数")
