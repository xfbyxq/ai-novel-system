#!/usr/bin/env python3
"""Reset alembic version and re-run migrations."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from backend.config import settings

async def reset_alembic():
    """Reset alembic version and re-run migrations."""
    print(f"Resetting alembic in: {settings.DATABASE_URL}")
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False
    )
    
    try:
        # Test connection
        async with engine.connect() as conn:
            # Drop alembic_version table
            await conn.execute(
                text("DROP TABLE IF EXISTS alembic_version CASCADE")
            )
            await conn.commit()
            print("✓ Dropped alembic_version table")
            
            # Drop all other tables to start fresh
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
            tables = [row[0] for row in result]
            for table in tables:
                await conn.execute(
                    text(f"DROP TABLE IF EXISTS {table} CASCADE")
                )
                print(f"✓ Dropped table: {table}")
            
            # Drop all enum types
            result = await conn.execute(
                text("SELECT typname FROM pg_type WHERE typcategory = 'E' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')")
            )
            enums = [row[0] for row in result]
            for enum in enums:
                await conn.execute(
                    text(f"DROP TYPE IF EXISTS {enum} CASCADE")
                )
                print(f"✓ Dropped enum: {enum}")
            
            await conn.commit()
            
            print("\n✓ Database reset successfully!")
            print("Now you can run: poetry run alembic upgrade head")
            
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_alembic())
