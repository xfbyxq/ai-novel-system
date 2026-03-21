"""plot_outline 模块."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class PlotOutline(Base):
    """PlotOutline 类."""

    __tablename__ = "plot_outlines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("novels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    structure_type = Column(String(50), default="three_act")  # 三幕式/英雄之旅
    volumes = Column(JSONB, default=list)  # 卷信息列表，增强结构：
    # [
    #     {
    #         "number": 1,                    # 卷号
    #         "title": "卷名",                 # 卷标题
    #         "summary": "卷概述",              # 卷概要 (200-300 字)
    #         "chapters": [1, 20],            # 章节范围 [start, end]
    #         "core_conflict": "核心冲突",     # 本卷核心矛盾
    #         "main_events": [                # 主线事件列表
    #             {
    #                 "chapter": 3,
    #                 "event": "事件描述",
    #                 "impact": "影响"
    #             }
    #         ],
    #         "key_turning_points": [         # 关键转折点
    #             {
    #                 "chapter": 5,
    #                 "event": "转折事件",
    #                 "significance": "重要性"
    #             }
    #         ],
    #         "tension_cycles": [             # 张力循环 (欲扬先抑)
    #             {
    #                 "chapters": [1, 7],
    #                 "suppress_events": ["压制事件 1", "压制事件 2"],
    #                 "release_event": "释放事件",
    #                 "tension_level": 7.5    # 紧张度 (0-10)
    #             }
    #         ],
    #         "emotional_arc": "情感弧线",    # 情感变化曲线描述
    #         "character_arcs": [             # 角色发展弧线
    #             {
    #                 "character_id": "xxx",
    #                 "arc_description": "成长描述",
    #                 "key_moments": [1, 5, 10]
    #             }
    #         ],
    #         "side_plots": [                 # 支线情节
    #             {
    #                 "name": "支线名",
    #                 "description": "描述",
    #                 "chapters": [2, 8]
    #             }
    #         ],
    #         "foreshadowing": [              # 伏笔分配
    #             {
    #                 "description": "伏笔描述",
    #                 "setup_chapter": 2,
    #                 "payoff_chapter": 15
    #             }
    #         ],
    #         "themes": ["主题 1", "主题 2"],  # 本卷主题
    #         "word_count_range": [20000, 30000]  # 字数范围
    #     }
    # ]

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

    # 大纲动态更新相关字段
    update_history = Column(JSONB, default=list)  # 动态更新历史记录
    # update_history 结构：
    # [
    #     {
    #         "version": 2,
    #         "updated_at": "2026-03-19T12:00:00",
    #         "trigger_chapter": 3,
    #         "deviation_score": 7.2,
    #         "change_summary": ["调整了第二卷支线走向", "新增转折点"],
    #         "affected_chapters": [4, 5, 6, 7, 8]
    #     }
    # ]
    version = Column(Integer, default=1)  # 大纲版本号，每次动态更新 +1

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    novel = relationship("Novel", back_populates="plot_outline")
