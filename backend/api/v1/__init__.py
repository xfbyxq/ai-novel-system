"""
API v1 router aggregation.
"""

from fastapi import APIRouter

from backend.api.v1 import novels, characters, chapters, outlines, generation

api_router = APIRouter(prefix="/api/v1")

# Include all v1 sub-routers
api_router.include_router(novels.router)
api_router.include_router(characters.router)
api_router.include_router(chapters.router)
api_router.include_router(outlines.router)
api_router.include_router(generation.router)

__all__ = ["api_router"]
