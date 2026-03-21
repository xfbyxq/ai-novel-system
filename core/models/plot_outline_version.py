"""plot_outline_version 模块."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class PlotOutlineVersion(Base):
    """PlotOutlineVersion 类 - 大纲版本历史."""

    __tablename__ = "plot_outline_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plot_outline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plot_outlines.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number = Column(Integer, nullable=False)
    version_data = Column(JSONB, nullable=False)
    change_summary = Column(String(500), nullable=True)
    changes = Column(JSONB, default=dict)
    created_by = Column(String(100), default="system")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plot_outline = relationship("PlotOutline", back_populates="versions")
