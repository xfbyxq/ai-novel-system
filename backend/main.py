"""
FastAPI application entry point for the Novel Generation System.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api.v1 import api_router
from backend.config import settings
from backend.routes import agent_activities

# Setup logging
from core.logging_config import setup_logging

setup_logging()

# OpenAPI tags metadata
tags_metadata = [
    {
        "name": "novels",
        "description": "小说管理：创建、查询、更新、删除小说",
    },
    {
        "name": "characters",
        "description": "角色管理：创建、查询、更新、删除角色，获取角色关系图",
    },
    {
        "name": "chapters",
        "description": "章节管理：查询、更新、删除章节，支持批量操作",
    },
    {
        "name": "outlines",
        "description": "大纲管理：世界观设定、剧情大纲的查询和更新",
    },
    {
        "name": "generation",
        "description": "AI内容生成：创建生成任务（企划、写作、批量写作），查询任务状态",
    },
    {
        "name": "ai-chat",
        "description": "AI对话：创建会话、发送消息、解析意图、提取和应用修订建议",
    },
    {
        "name": "publishing",
        "description": "发布系统：平台账号管理、发布任务管理、发布预览",
    },
    {
        "name": "监控",
        "description": "系统监控：系统状态、性能指标、错误分析、Agent状态",
    },
    {
        "name": "root",
        "description": "根端点：API基本信息",
    },
    {
        "name": "health",
        "description": "健康检查：服务健康状态",
    },
]

app = FastAPI(
    title="小说生成系统 API",
    version=settings.APP_VERSION,
    description="""
## AI驱动的小说生成系统

本系统提供完整的AI小说创作能力，包括：

### 核心功能
- **小说管理**：创建、编辑、删除小说项目
- **角色管理**：创建角色档案，管理角色关系
- **世界观设定**：定义力量体系、地理、势力等
- **剧情大纲**：规划主线、支线、转折点
- **AI内容生成**：自动生成世界观、角色、章节内容
- **多平台发布**：支持起点、晋江等平台的自动发布

### 技术特点
- 基于CrewAI的多Agent协作架构
- 支持流式响应的AI对话
- 质量审查和自动优化
- 完整的任务状态追踪

### 使用方式
1. 创建小说项目 → 2. 执行企划任务 → 3. 执行写作任务 → 4. 发布到平台
""",
    debug=settings.APP_DEBUG,
    redirect_slashes=False,
    openapi_tags=tags_metadata,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # 限制为前端开发服务器
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router)

# Include Agent Activities router
app.include_router(agent_activities.router, prefix="/api/v1")


@app.get("/", tags=["root"])
async def root():
    """Root endpoint returning basic API information."""
    return {
        "name": "小说生成系统 API",
        "version": settings.APP_VERSION,
        "status": "running",
        "api_docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint with database and Redis dependency checks."""
    health = {
        "status": "healthy",
        "service": "novel-generation-system",
        "dependencies": {}
    }

    # 检查数据库
    try:
        from core.database import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["dependencies"]["postgres"] = "healthy"
    except Exception as e:
        health["status"] = "unhealthy"
        health["dependencies"]["postgres"] = f"error: {str(e)}"

    # 检查Redis
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        health["dependencies"]["redis"] = "healthy"
    except Exception as e:
        health["status"] = "unhealthy"
        health["dependencies"]["redis"] = f"error: {str(e)}"

    return health
