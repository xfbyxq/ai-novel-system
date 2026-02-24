"""
FastAPI application entry point for the Novel Generation System.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1 import api_router
from backend.config import settings

# Setup logging
from core.logging_config import setup_logging
setup_logging()

app = FastAPI(
    title="小说生成系统 API",
    version="0.1.0",
    description="AI-powered novel generation system API",
    debug=settings.APP_DEBUG,
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


@app.get("/", tags=["root"])
async def root():
    """Root endpoint returning basic API information."""
    return {
        "name": "小说生成系统 API",
        "version": "0.1.0",
        "status": "running",
        "api_docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "novel-generation-system",
    }
