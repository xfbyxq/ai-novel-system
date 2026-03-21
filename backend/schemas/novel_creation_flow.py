from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class NovelDialogueScene(str, Enum):
    """小说对话场景"""
    CREATE = "create"  # 创建新小说
    QUERY = "query"  # 查询已有小说
    REVISE = "revise"  # 修改小说内容
    ANALYZE = "analyze"  # 分析小说


class CreationFlowStep(str, Enum):
    """小说对话流程步骤"""
    # 通用步骤
    INITIAL = "initial"  # 初始问候
    SCENE_SELECTION = "scene_selection"  # 场景选择（创建/查询/修改）

    # 创建流程
    GENRE_CONFIRMATION = "genre_confirmation"  # 确认小说类型
    WORLD_SETTING_DETAIL = "world_setting_detail"  # 世界观详情
    WORLD_SETTING_CLARIFY = "world_setting_clarify"  # 世界观澄清
    SYNOPSIS_EXTRACTION = "synopsis_extraction"  # 提炼简介
    SYNOPSIS_REFINEMENT = "synopsis_refinement"  # 简介优化
    FINAL_CONFIRMATION = "final_confirmation"  # 最终确认

    # 查询流程
    NOVEL_SELECTION = "novel_selection"  # 选择小说
    CONTENT_QUERY = "content_query"  # 内容查询
    QUERY_RESULT_DISPLAY = "query_result_display"  # 查询结果展示

    # 修改流程
    REVISION_TARGET_SELECTION = "revision_target_selection"  # 选择修改目标
    REVISION_DETAIL_COLLECTION = "revision_detail_collection"  # 收集修改详情
    REVISION_CONFIRMATION = "revision_confirmation"  # 修改确认

    COMPLETED = "completed"  # 完成


class WorldSettingDetails(BaseModel):
    """世界观背景设定详情"""
    era_background: Optional[str] = Field(None, description="时代背景")
    geographical_environment: Optional[str] = Field(None, description="地理环境")
    social_structure: Optional[str] = Field(None, description="社会结构")
    special_rules: Optional[str] = Field(None, description="特殊规则")
    power_system: Optional[str] = Field(None, description="力量体系")
    other_elements: Optional[str] = Field(None, description="其他元素")


class NovelSynopsis(BaseModel):
    """小说核心简介"""
    main_plot: str = Field(..., description="主要情节脉络")
    core_conflict: str = Field(..., description="核心冲突")
    target_audience: str = Field(..., description="目标读者群体")
    unique_selling_point: Optional[str] = Field(None, description="独特卖点")


class NovelCreationContext(BaseModel):
    """小说创建对话上下文"""
    # 对话场景
    scene: NovelDialogueScene = Field(default=NovelDialogueScene.CREATE)

    # 流程步骤
    current_step: CreationFlowStep = Field(default=CreationFlowStep.INITIAL)

    # 创建相关字段
    genre: Optional[str] = Field(None, description="小说类型")
    genre_confirmed: bool = Field(default=False, description="类型是否已确认")
    world_setting: Optional[WorldSettingDetails] = Field(None, description="世界观设定")
    world_setting_confirmed: bool = Field(default=False, description="世界观是否已确认")
    synopsis: Optional[NovelSynopsis] = Field(None, description="小说简介")
    synopsis_confirmed: bool = Field(default=False, description="简介是否已确认")
    novel_title: Optional[str] = Field(None, description="小说标题")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    target_platform: str = Field(default="番茄小说", description="目标平台")
    length_type: str = Field(default="medium", description="篇幅类型")

    # 查询相关字段
    selected_novel_id: Optional[str] = Field(None, description="选择的小说 ID")
    query_target: Optional[str] = Field(None, description="查询目标 (world_setting/character/plot/chapter)")
    query_result: Optional[dict] = Field(None, description="查询结果")

    # 修改相关字段
    revision_target: Optional[str] = Field(None, description="修改目标")
    revision_details: Optional[dict] = Field(None, description="修改详情")
    revision_confirmed: bool = Field(default=False, description="修改是否已确认")

    class Config:
        use_enum_values = True


class NovelCreationFlowState(BaseModel):
    """小说创建流程状态"""
    session_id: str
    context: NovelCreationContext
    conversation_history: list[dict] = Field(default_factory=list)
    created_at: str
    updated_at: str
