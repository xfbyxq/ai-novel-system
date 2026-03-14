"""CrewAI 风格的小说生成 Agent 系统"""

from agents.crew_manager import NovelCrewManager
from agents.continuity_models import (
    ContinuityConstraint,
    ValidationReport,
    ChapterTransition,
    ConstraintList,
)
from agents.continuity_inference import (
    ConstraintInferenceEngine,
    infer_chapter_constraints,
)
from agents.context_propagator import (
    ContextPropagator,
    propagate_constraints,
)
from agents.continuity_validation import (
    ValidationEngine,
    validate_chapter_transition,
)
from agents.continuity_integration import (
    ContinuityAssuranceIntegration,
    generate_chapter_with_continuity,
)
from agents.outline_refiner import OutlineRefiner
from agents.outline_validator import OutlineValidator

__all__ = [
    "NovelCrewManager",
    "ContinuityConstraint",
    "ValidationReport",
    "ChapterTransition",
    "ConstraintList",
    "ConstraintInferenceEngine",
    "infer_chapter_constraints",
    "ContextPropagator",
    "propagate_constraints",
    "ValidationEngine",
    "validate_chapter_transition",
    "ContinuityAssuranceIntegration",
    "generate_chapter_with_continuity",
    "OutlineRefiner",
    "OutlineValidator",
]
