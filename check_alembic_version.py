#!/usr/bin/env python3
"""Check alembic version in database."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from backend.config import settings

async def check_alembic_version():
    """Check alembic version in database."""
    print(f"Checking alembic version in: {settings.DATABASE_URL}")
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False
    )
    
    try:
        # Test connection
        async with engine.connect() as conn:
            # Check alembic version
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            version = result.scalar()
            print(f"\nAlembic version in database: {version}")
            
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_alembic_version())
