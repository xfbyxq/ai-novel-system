"""Pydantic schemas for the novel system"""

# Novel schemas
from .novel import (
    NovelCreate,
    NovelUpdate,
    NovelResponse,
    NovelListResponse,
)

# Character schemas
from .character import (
    CharacterCreate,
    CharacterUpdate,
    CharacterResponse,
    CharacterNode,
    CharacterEdge,
    CharacterRelationshipResponse,
)

# Outline schemas
from .outline import (
    WorldSettingResponse,
    WorldSettingUpdate,
    PlotOutlineResponse,
    PlotOutlineUpdate,
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
    ChapterListResponse,
)

# Generation schemas
from .generation import (
    GenerationTaskCreate,
    GenerationTaskResponse,
    GenerationTaskListResponse,
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
