"""
API v1 router aggregation.
"""

from fastapi import APIRouter

from backend.api.v1 import (
    ai_chat,
    chapters,
    characters,
    generation,
    graph,
    monitoring,
    novels,
    outlines,
    publishing,
)

# 注释掉不存在或依赖缺失的模块
# from backend.api.v1 import crawler, automation, integration, revenue

api_router = APIRouter(prefix="/api/v1")

# Include all v1 sub-routers
api_router.include_router(novels.router)
api_router.include_router(characters.router)
api_router.include_router(chapters.router)
api_router.include_router(outlines.router)
api_router.include_router(generation.router)
api_router.include_router(ai_chat.router)
api_router.include_router(publishing.router)
api_router.include_router(monitoring.router)
api_router.include_router(graph.router)
# 注释掉不存在或依赖缺失的模块路由
# api_router.include_router(crawler.router)
# api_router.include_router(automation.router)
# api_router.include_router(integration.router)
# api_router.include_router(revenue.router)

__all__ = ["api_router"]
