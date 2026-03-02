"""Pydantic schemas for the novel system"""

# Novel schemas
# Character schemas
from .character import (
    CharacterCreate,
    CharacterEdge,
    CharacterNode,
    CharacterRelationshipResponse,
    CharacterResponse,
    CharacterUpdate,
)

# Generation schemas
from .generation import (
    GenerationTaskCreate,
    GenerationTaskListResponse,
    GenerationTaskResponse,
)
from .novel import (
    NovelCreate,
    NovelListResponse,
    NovelResponse,
    NovelUpdate,
)

# Outline schemas
from .outline import (
    ChapterCreate,
    ChapterListResponse,
    ChapterResponse,
    ChapterUpdate,
    PlotOutlineResponse,
    PlotOutlineUpdate,
    WorldSettingResponse,
    WorldSettingUpdate,
)

__all__ = [
    # Novel
    "NovelCreate",
    "NovelUpdate",
    "NovelResponse",
    "NovelListResponse",
    # Character
    "CharacterCreate",
    "CharacterUpdate",
    "CharacterResponse",
    "CharacterNode",
    "CharacterEdge",
    "CharacterRelationshipResponse",
    # Outline
    "WorldSettingResponse",
    "WorldSettingUpdate",
    "PlotOutlineResponse",
    "PlotOutlineUpdate",
    "ChapterCreate",
    "ChapterUpdate",
    "ChapterResponse",
    "ChapterListResponse",
    # Generation
    "GenerationTaskCreate",
    "GenerationTaskResponse",
    "GenerationTaskListResponse",
]
