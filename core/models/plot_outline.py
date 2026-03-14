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
    
    # 主线剧情详细字段 - 增强版
    main_plot = Column(JSONB, default=dict)  # 保留向后兼容
    main_plot_detailed = Column(JSONB, default=dict)  # 新增详细主线剧情
    # main_plot_detailed 结构：
    # {
    #     "core_conflict": "核心冲突的详细描述（300-500 字）",
    #     "protagonist_goal": "主角的终极目标及动机",
    #     "antagonist_force": "反派/阻碍力量的详细描述",
    #     "escalation_path": "冲突升级路径 [阶段 1, 阶段 2, ...]",
    #     "emotional_arc": "情感弧光变化曲线",
    #     "theme_expression": "主题表达方式",
    #     "key_revelations": "关键揭示点列表",
    #     "character_growth": "主角成长轨迹描述",
    #     "ending_description": "结局详细描述（包括最终冲突解决、角色归宿等）"
    # }
    
    sub_plots = Column(JSONB, default=list)
    key_turning_points = Column(JSONB, default=list)
    climax_chapter = Column(Integer, nullable=True)
    raw_content = Column(Text, nullable=True)  # Agent 原始输出
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    novel = relationship("Novel", back_populates="plot_outline")
