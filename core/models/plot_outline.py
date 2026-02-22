import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class PlotOutline(Base):
    __tablename__ = "plot_outlines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, unique=True)
    structure_type = Column(String(50), default="three_act")  # 三幕式/英雄之旅
    volumes = Column(JSONB, default=list)  # [{volume_num, title, summary, chapters, key_events}]
    main_plot = Column(JSONB, default=dict)
    sub_plots = Column(JSONB, default=list)
    key_turning_points = Column(JSONB, default=list)
    climax_chapter = Column(Integer, nullable=True)
    raw_content = Column(Text, nullable=True)  # Agent 原始输出
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    novel = relationship("Novel", back_populates="plot_outline")
