"""全局测试 fixtures."""

import os
import glob
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings
from core.database import Base

TEST_TEMP_PATTERNS = [
    "*.png",
    "*.log",
    "*.tmp",
    "*.json",
]


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束后清理测试产生的临时文件."""
    root = Path.cwd()
    test_dirs = [root, root / "tests" / "e2e", root / "tests" / "screenshots"]

    for base_dir in test_dirs:
        if not base_dir.exists():
            continue
        for pattern in TEST_TEMP_PATTERNS:
            for f in base_dir.glob(pattern):
                try:
                    if f.is_file():
                        f.unlink()
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# 数据库 fixtures（集成测试用）
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", settings.DATABASE_URL)


@pytest.fixture(scope="function")
async def db_engine():
    """为每个测试函数创建独立的数据库引擎."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """提供隔离的异步数据库 session，测试结束后回滚."""
    async_session = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture
async def test_client(db_session):
    """FastAPI 异步测试客户端，覆盖 get_db 依赖."""
    from backend.dependencies import get_db
    from backend.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 真实 HTTP 客户端（场景测试用）
# ---------------------------------------------------------------------------


@pytest.fixture
async def real_http_client():
    """真实 HTTP 客户端，用于实际爬取测试."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        yield client
