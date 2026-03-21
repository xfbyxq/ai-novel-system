"""大纲相关的 Pydantic schemas"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorldSettingResponse(BaseModel):
    """世界观设定响应模型"""

    id: UUID = Field(..., description="世界观设定唯一标识符")
    novel_id: UUID = Field(..., description="所属小说 ID")
    world_name: Optional[str] = Field(
        default=None, description="世界名称，如'青玄大陆'、'蔚蓝星'"
    )
    world_type: Optional[str] = Field(
        default=None, description="世界类型：仙侠/都市/科幻/武侠/悬疑等"
    )
    power_system: Optional[dict] = Field(
        default=None,
        description="力量体系，格式：{name: 体系名，levels: [等级列表], description: 描述}",
    )
    geography: Optional[dict] = Field(
        default=None,
        description="地理设定，格式：{regions: [{name, description, features}], landmarks: [...]}}",
    )
    factions: Optional[list] = Field(
        default=None,
        description="势力组织列表，每项格式：{name, type, power_level, leader, description}",
    )
    rules: Optional[list] = Field(default=None, description="世界运行规则列表")
    timeline: Optional[list] = Field(default=None, description="历史时间线列表")
    special_elements: Optional[list] = Field(default=None, description="特殊元素列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class WorldSettingUpdate(BaseModel):
    """更新世界观设定的请求模型（仅更新提供的字段，不存在时自动创建）"""

    world_name: Optional[str] = Field(default=None, description="世界名称")
    world_type: Optional[str] = Field(
        default=None, description="世界类型，如：仙侠、都市、科幻、武侠、悬疑等"
    )
    power_system: Optional[dict] = Field(
        default=None, description="力量体系，格式：{name, levels: [], description}"
    )
    geography: Optional[dict] = Field(
        default=None,
        description="地理设定，格式：{regions: [{name: '东域', features: [...]}], landmarks: [...]}",
    )
    factions: Optional[list] = Field(
        default=None,
        description="势力组织列表，每项格式：{name: '天剑宗', type: '宗门', power_level: 'S 级'}",
    )
    rules: Optional[list] = Field(default=None, description="世界运行规则列表")
    timeline: Optional[list] = Field(
        default=None, description="历史时间线，每项格式：{time, event, significance}"
    )
    special_elements: Optional[list] = Field(default=None, description="特殊元素列表")


class VolumeInfo(BaseModel):
    """卷信息详细模型（增强版）"""

    number: int = Field(..., description="卷号")
    title: str = Field(..., description="卷标题")
    summary: Optional[str] = Field(default=None, description="卷概要")
    chapters: list[int] = Field(
        default_factory=list, description="章节范围 [start, end]"
    )

    # 核心冲突
    core_conflict: Optional[str] = Field(default=None, description="本卷核心矛盾")

    # 主线事件
    main_events: Optional[list] = Field(
        default_factory=list,
        description="主线事件列表，每项格式：{chapter, event, impact}",
    )

    # 关键转折点
    key_turning_points: Optional[list] = Field(
        default_factory=list,
        description="关键转折点列表，每项格式：{chapter, event, significance}",
    )

    # 张力循环
    tension_cycles: Optional[list] = Field(
        default_factory=list,
        description="张力循环列表，每项格式：{chapters, suppress_events, release_event, tension_level}",
    )

    # 情感弧线
    emotional_arc: Optional[str] = Field(default=None, description="情感变化曲线描述")

    # 角色发展弧线
    character_arcs: Optional[list] = Field(
        default_factory=list,
        description="角色发展弧线列表，每项格式：{character_id, arc_description, key_moments}",
    )

    # 支线情节
    side_plots: Optional[list] = Field(
        default_factory=list,
        description="支线情节列表，每项格式：{name, description, chapters}",
    )

    # 伏笔分配
    foreshadowing: Optional[list] = Field(
        default_factory=list,
        description="伏笔分配列表，每项格式：{description, setup_chapter, payoff_chapter}",
    )

    # 主题
    themes: Optional[list] = Field(default_factory=list, description="本卷主题列表")

    # 字数范围
    word_count_range: Optional[list[int]] = Field(
        default=None, description="字数范围 [min, max]"
    )


class PlotOutlineResponse(BaseModel):
    """剧情大纲响应模型"""

    id: UUID = Field(..., description="大纲唯一标识符")
    novel_id: UUID = Field(..., description="所属小说 ID")
    structure_type: Optional[str] = Field(
        default=None, description="结构类型，如：三幕式、英雄之旅、多线叙事等"
    )
    volumes: Optional[list[VolumeInfo]] = Field(
        default=None,
        description="卷/篇设定列表，每项格式：{number, title, chapters, summary}",
    )
    main_plot: Optional[dict] = Field(
        default=None,
        description="主线剧情，格式：{setup, conflict, climax, resolution}",
    )
    sub_plots: Optional[list] = Field(
        default=None,
        description="支线剧情列表，每项格式：{name: '感情线', characters: [...], arc: '...'}",
    )
    key_turning_points: Optional[list] = Field(
        default=None,
        description="关键转折点列表，每项格式：{chapter: 10, event: '获得神器', impact: '实力飞跃'}",
    )
    climax_chapter: Optional[int] = Field(default=None, description="高潮章节号")
    version: int = Field(default=1, description="大纲版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class PlotOutlineUpdate(BaseModel):
    """更新剧情大纲的请求模型（仅更新提供的字段，不存在时自动创建）"""

    structure_type: Optional[str] = Field(
        default=None, description="结构类型：三幕式/英雄之旅等"
    )
    volumes: Optional[list[dict]] = Field(
        default=None,
        description="卷/篇设定列表，每项格式：{number, title, chapters: [start, end], summary, core_conflict, main_events, key_turning_points, tension_cycles, emotional_arc, character_arcs, side_plots, foreshadowing, themes, word_count_range}",
    )
    main_plot: Optional[dict] = Field(
        default=None,
        description="主线剧情，格式：{setup, conflict, climax, resolution}",
    )
    sub_plots: Optional[list] = Field(
        default=None, description="支线剧情列表，每项格式：{name, characters, arc}"
    )
    key_turning_points: Optional[list] = Field(
        default=None, description="关键转折点列表，每项格式：{chapter, event, impact}"
    )
    climax_chapter: Optional[int] = Field(default=None, description="高潮章节号")


class ChapterCreate(BaseModel):
    """创建章节的请求模型"""

    chapter_number: int = Field(..., description="章节号（从 1 开始）")
    volume_number: int = Field(default=1, description="所属卷号")
    title: Optional[str] = Field(default=None, description="章节标题")


class ChapterUpdate(BaseModel):
    """更新章节的请求模型（仅更新提供的字段）"""

    title: Optional[str] = Field(default=None, description="章节标题")
    content: Optional[str] = Field(default=None, description="章节正文内容")
    status: Optional[str] = Field(
        default=None,
        description="章节状态：draft(草稿)、reviewing(审核中)、published(已发布)",
    )


class ChapterResponse(BaseModel):
    """章节响应模型"""

    id: UUID = Field(..., description="章节唯一标识符")
    novel_id: UUID = Field(..., description="所属小说 ID")
    chapter_number: int = Field(..., description="章节号")
    volume_number: int = Field(..., description="所属卷号")
    title: Optional[str] = Field(default=None, description="章节标题")
    content: Optional[str] = Field(default=None, description="章节正文内容")
    word_count: int = Field(..., description="章节字数")
    status: str = Field(..., description="章节状态：draft/reviewing/published")
    quality_score: Optional[float] = Field(
        default=None, description="AI 评估的质量评分（0-10）"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")

    model_config = ConfigDict(from_attributes=True)


class ChapterListResponse(BaseModel):
    """章节列表响应模型（分页）"""

    items: list[ChapterResponse] = Field(..., description="章节列表")
    total: int = Field(..., description="符合条件的章节总数")
    page: Optional[int] = Field(default=None, description="当前页码")
    page_size: Optional[int] = Field(default=None, description="每页数量")


class OutlineGenerateRequest(BaseModel):
    """生成大纲请求模型"""

    structure_type: Optional[str] = Field(
        default="three_act",
        description="结构类型：three_act(三幕式)/hero_journey(英雄之旅)/multi_thread(多线叙事)",
    )
    total_chapters: Optional[int] = Field(default=None, description="预计总章节数")
    volumes_count: Optional[int] = Field(default=None, description="预计卷数")
    generate_volumes: Optional[bool] = Field(default=True, description="是否生成卷设定")
    generate_subplots: Optional[bool] = Field(
        default=True, description="是否生成支线剧情"
    )
    generate_turning_points: Optional[bool] = Field(
        default=True, description="是否生成关键转折点"
    )


class OutlineDecomposeRequest(BaseModel):
    """分解大纲请求模型"""

    chapter_start: int = Field(..., description="起始章节号")
    chapter_end: int = Field(..., description="结束章节号")
    volume_number: Optional[int] = Field(default=1, description="所属卷号")
    decomposition_level: Optional[str] = Field(
        default="detailed",
        description="分解粒度：basic(基础)/detailed(详细)/granular(细粒度)",
    )


class ChapterOutlineTaskResponse(BaseModel):
    """章节大纲任务响应模型"""

    chapter_number: int = Field(..., description="章节号")
    volume_number: int = Field(..., description="所属卷号")
    title: Optional[str] = Field(default=None, description="章节标题")
    outline_task: dict = Field(..., description="章节大纲任务内容")
    main_plot_points: list = Field(default_factory=list, description="主要剧情点列表")
    character_arcs: list = Field(default_factory=list, description="角色发展弧线")
    foreshadowing_requirements: list = Field(
        default_factory=list, description="伏笔要求列表"
    )
    consistency_checks: list = Field(default_factory=list, description="一致性检查项")
    created_at: Optional[datetime] = Field(default=None, description="任务创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="任务更新时间")


class OutlineValidationRequest(BaseModel):
    """大纲验证请求模型"""

    chapter_outline: dict = Field(..., description="待验证的章节大纲")
    validation_scope: Optional[list] = Field(
        default=None,
        description="验证范围：['character_consistency', 'plot_continuity', 'world_setting', 'timeline']",
    )
    strict_mode: Optional[bool] = Field(default=False, description="是否启用严格模式")


class OutlineValidationResponse(BaseModel):
    """大纲验证响应模型"""

    is_valid: bool = Field(..., description="是否通过验证")
    validation_results: dict = Field(..., description="验证结果详情")
    issues: list = Field(default_factory=list, description="发现的问题列表")
    suggestions: list = Field(default_factory=list, description="改进建议列表")
    consistency_score: Optional[float] = Field(
        default=None, description="一致性评分（0-1）"
    )
    validated_at: datetime = Field(..., description="验证时间")


class OutlineVersionInfo(BaseModel):
    """大纲版本信息模型"""

    version_id: str = Field(..., description="版本号")
    novel_id: UUID = Field(..., description="所属小说 ID")
    version_number: int = Field(..., description="版本序号")
    change_summary: Optional[str] = Field(default=None, description="变更摘要")
    changes: Optional[dict] = Field(default=None, description="具体变更内容")
    created_by: Optional[str] = Field(default=None, description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    is_current: bool = Field(default=False, description="是否为当前版本")


class EnhancementOptions(BaseModel):
    """智能完善选项模型"""

    max_iterations: Optional[int] = Field(
        default=3, description="最大迭代次数", ge=1, le=10
    )
    quality_threshold: Optional[float] = Field(
        default=8.0, description="质量阈值（0-10）", ge=0.0, le=10.0
    )
    preserve_user_edits: Optional[bool] = Field(
        default=True, description="是否保留用户手动编辑的内容"
    )
    update_database: Optional[bool] = Field(
        default=False, description="是否直接更新数据库（false 时只返回预览）"
    )


class OutlineQualityReport(BaseModel):
    """大纲质量评估报告模型"""

    overall_score: float = Field(
        ..., description="总体质量评分（0-10）", ge=0.0, le=10.0
    )
    dimension_scores: dict = Field(
        ..., description="各维度评分，格式：{'完整性': 8.5, '逻辑性': 7.2, ...}"
    )
    strengths: list = Field(default_factory=list, description="优势点列表")
    weaknesses: list = Field(default_factory=list, description="薄弱点列表")
    improvement_suggestions: list = Field(
        default_factory=list, description="改进建议列表"
    )
    evaluated_at: datetime = Field(..., description="评估时间")


class EnhancementPreviewResponse(BaseModel):
    """智能完善预览响应模型"""

    original_outline: PlotOutlineResponse = Field(..., description="原始大纲")
    enhanced_outline: PlotOutlineResponse = Field(..., description="增强后的大纲")
    quality_comparison: dict = Field(
        ...,
        description="质量对比数据，格式：{original_score, enhanced_score, improvement, dimension_improvements}",
    )
    improvements_made: list = Field(
        default_factory=list, description="实施的改进措施列表"
    )
    processing_time: float = Field(..., description="处理耗时（秒）")
    cost_estimate: float = Field(..., description="预估成本（元）")

    model_config = ConfigDict(from_attributes=True)


class AIAssistRequest(BaseModel):
    """AI 辅助生成大纲字段请求模型"""

    field_name: str = Field(
        ...,
        description="需要辅助的字段名：structure_type/volumes/main_plot/sub_plots/key_turning_points/climax_chapter",
    )
    current_context: Optional[dict] = Field(
        default=None, description="当前大纲上下文，用于生成更精准的建议"
    )
    additional_hints: Optional[str] = Field(
        default=None, description="额外提示信息，如风格偏好、特殊要求等"
    )


class AIAssistResponse(BaseModel):
    """AI 辅助生成响应模型"""

    field_name: str = Field(..., description="字段名")
    suggestion: str = Field(..., description="AI 生成的建议内容")
    confidence: Optional[float] = Field(
        default=None, description="置信度（0-1）", ge=0.0, le=1.0
    )
    alternatives: Optional[list] = Field(default=None, description="备选建议列表")
    reasoning: Optional[str] = Field(default=None, description="生成理由说明")
    generated_at: datetime = Field(..., description="生成时间")
