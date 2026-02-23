import uuid

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func

from core.database import Base


class ReaderPreference(Base):
    __tablename__ = "reader_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)  # qidian / douban
    genre = Column(String(50), nullable=True)
    tags = Column(ARRAY(String), default=list)
    ranking_data = Column(JSONB, default=dict)
    comment_sentiment = Column(JSONB, default=dict)
    trend_score = Column(Float, default=0.0)
    data_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 新增字段 - 关联爬虫任务和书籍详情
    crawler_task_id = Column(UUID(as_uuid=True), ForeignKey("crawler_tasks.id", ondelete="SET NULL"), nullable=True)
    book_id = Column(String(100), nullable=True)  # 原平台书籍ID
    book_title = Column(String(200), nullable=True)
    author_name = Column(String(100), nullable=True)
    rating = Column(Float, nullable=True)
    word_count = Column(Integer, nullable=True)
