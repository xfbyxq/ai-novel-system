"""
Shared dependencies for FastAPI application.
"""

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db as _get_db
from backend.config import settings


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session dependency.

    Re-exports get_db from core.database for use in FastAPI dependencies.
    """
    async for session in _get_db():
        yield session


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> str:
    """
    Verify API Key for protected endpoints.

    Usage:
        @app.get("/protected")
        async def protected_endpoint(api_key: str = Depends(verify_api_key)):
            pass

    Returns:
        The validated API key string

    Raises:
        HTTPException: If authentication fails
    """
    # Development mode: skip auth if no API key configured (for local testing)
    if settings.APP_ENV == "development" and not settings.DASHSCOPE_API_KEY:
        return "dev-mode"

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != settings.DASHSCOPE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


__all__ = ["get_db", "verify_api_key"]
