"""爬虫任务模型"""
import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class CrawlType(str, enum.Enum):
    """爬取类型"""
    ranking = "ranking"              # 排行榜
    trending_tags = "trending_tags"  # 热门标签
    book_metadata = "book_metadata"  # 书籍元数据
    genre_list = "genre_list"        # 分类列表


class CrawlTaskStatus(str, enum.Enum):
    """爬虫任务状态"""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CrawlerTask(Base):
    """爬虫任务"""
    __tablename__ = "crawler_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_name = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False, default="qidian")
    crawl_type = Column(Enum(CrawlType), nullable=False)
    config = Column(JSONB, default=dict)  # 爬取配置（URL、筛选条件等）
    status = Column(Enum(CrawlTaskStatus), default=CrawlTaskStatus.pending)
    progress = Column(JSONB, default=dict)  # {current_page, total_pages, items_crawled}
    result_summary = Column(JSONB, default=dict)  # {items_count, success_count, error_count}
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    crawl_results = relationship("CrawlResult", back_populates="crawler_task", cascade="all, delete-orphan")
