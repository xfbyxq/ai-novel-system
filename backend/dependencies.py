"""
Shared dependencies for FastAPI application.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db as _get_db


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session dependency.

    Re-exports get_db from core.database for use in FastAPI dependencies.
    """
    async for session in _get_db():
        yield session


__all__ = ["get_db"]
