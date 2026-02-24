#!/usr/bin/env python3
"""Test database connection and table structure."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from backend.config import settings

async def test_db_connection():
    """Test database connection and check tables."""
    print(f"Testing database connection: {settings.DATABASE_URL}")
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True
    )
    
    try:
        # Test connection
        async with engine.connect() as conn:
            print("Connected to database successfully!")
            
            # Check if novels table exists
            result = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
            tables = [row[0] for row in result]
            print(f"\nTables in database:")
            for table in tables:
                print(f"- {table}")
            
            if 'novels' in tables:
                print("\n✓ novels table exists!")
            else:
                print("\n✗ novels table does NOT exist!")
                
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db_connection())
