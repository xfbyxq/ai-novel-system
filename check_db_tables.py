#!/usr/bin/env python3
"""检查数据库表结构"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from backend.config import settings

async def check_db_tables():
    """检查数据库表"""
    print(f"数据库连接字符串: {settings.DATABASE_URL}")
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True
    )
    
    try:
        # 连接数据库
        async with engine.connect() as conn:
            print("成功连接到数据库")
            
            # 列出所有表
            result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            print("\n数据库中的表:")
            tables = []
            for row in result:
                tables.append(row[0])
                print(row[0])
            
            print(f"\n总共有 {len(tables)} 个表")
            
            # 检查 alembic_version 表的内容
            if 'alembic_version' in tables:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                for row in result:
                    print(f"\nalembic 当前版本: {row[0]}")
            
            # 重置 alembic 版本
            print("\n重置 alembic 版本...")
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('5badc20e064a')"))
            print("成功重置 alembic 版本到初始状态")
                
    except Exception as e:
        print(f"连接数据库失败: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_db_tables())
