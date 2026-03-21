"""database 模块."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    """Base 类."""


engine = create_async_engine(
    settings.DATABASE_URL.split("?")[0],  # 移除 URL 中的查询参数
    echo=settings.APP_DEBUG,
    pool_size=10,
    max_overflow=20,
    connect_args={"ssl": False},  # asyncpg 参数：禁用 SSL
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
