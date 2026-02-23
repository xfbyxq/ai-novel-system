"""爬取结果模型"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class CrawlResult(Base):
    """爬取结果"""
    __tablename__ = "crawl_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawler_task_id = Column(UUID(as_uuid=True), ForeignKey("crawler_tasks.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String(50), nullable=False)
    data_type = Column(String(50), nullable=False)  # ranking / book / tag
    raw_data = Column(JSONB, default=dict)
    processed_data = Column(JSONB, default=dict)
    url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    crawler_task = relationship("CrawlerTask", back_populates="crawl_results")
