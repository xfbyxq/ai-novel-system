"""全局测试 fixtures"""
import asyncio
import os
import random

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.config import settings
from core.database import Base


# ---------------------------------------------------------------------------
# 数据库 fixtures（集成测试用）
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", settings.DATABASE_URL)


@pytest.fixture(scope="session")
def event_loop():
    """创建 session 级别的 event loop，解决 asyncpg 事件循环问题"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_engine():
    """为每个测试函数创建独立的数据库引擎"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """提供隔离的异步数据库 session，测试结束后回滚"""
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        yield session

        await session.close()
        await trans.rollback()


@pytest.fixture
async def test_client(db_session):
    """FastAPI 异步测试客户端，覆盖 get_db 依赖"""
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
    """真实 HTTP 客户端，用于实际爬取测试"""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        yield client
