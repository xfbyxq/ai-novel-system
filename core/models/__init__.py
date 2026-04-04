"""models 包模块."""

from core.models.novel import Novel, NovelStatus
from core.models.world_setting import WorldSetting
from core.models.character import Character, RoleType, Gender, CharacterStatus
from core.models.character_name_version import CharacterNameVersion
from core.models.plot_outline import PlotOutline
from core.models.plot_outline_version import PlotOutlineVersion
from core.models.chapter import Chapter, ChapterStatus
from core.models.generation_task import GenerationTask, TaskType, TaskStatus
from core.models.token_usage import TokenUsage
from core.models.platform_account import PlatformAccount, AccountStatus
from core.models.publish_task import PublishTask, PublishType, PublishTaskStatus
from core.models.chapter_publish import ChapterPublish, PublishStatus
from core.models.ai_chat_session import AIChatSession, AIChatMessage
from core.models.novel_creation_flow import NovelCreationFlow
from core.models.agent_activity import AgentActivity
from core.models.revision_plan import RevisionPlan, RevisionPlanStatus, RevisionTargetType
from core.models.hindsight_memory import (
    HindsightExperience,
    StrategyEffectiveness,
    UserPreference,
    TaskType as HindsightTaskType,
    StrategyTrend,
)

__all__ = [
    "Novel",
    "NovelStatus",
    "WorldSetting",
    "Character",
    "RoleType",
    "Gender",
    "CharacterStatus",
    "CharacterNameVersion",
    "PlotOutline",
    "PlotOutlineVersion",
    "Chapter",
    "ChapterStatus",
    "GenerationTask",
    "TaskType",
    "TaskStatus",
    "TokenUsage",
    # Publishing models
    "PlatformAccount",
    "AccountStatus",
    "PublishTask",
    "PublishType",
    "PublishTaskStatus",
    "ChapterPublish",
    "PublishStatus",
    # AI Chat models
    "AIChatSession",
    "AIChatMessage",
    # Novel creation flow
    "NovelCreationFlow",
    # Agent activity
    "AgentActivity",
    # Revision models
    "RevisionPlan",
    "RevisionPlanStatus",
    "RevisionTargetType",
    # Hindsight memory models
    "HindsightExperience",
    "StrategyEffectiveness",
    "UserPreference",
    "HindsightTaskType",
    "StrategyTrend",
]
