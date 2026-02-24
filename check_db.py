#!/usr/bin/env python3
"""检查数据库状态"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

from backend.config import settings

async def check_db_status():
    """检查数据库状态"""
    print("正在检查数据库状态...")
    print(f"数据库URL: {settings.DATABASE_URL}")
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False
    )
    
    try:
        # 测试连接
        async with engine.begin() as conn:
            print("✅ 数据库连接成功")
            
            # 检查数据库中的表
            result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = [row[0] for row in result]
            
            print(f"\n数据库中的表 ({len(tables)}):")
            for table in sorted(tables):
                print(f"  - {table}")
            
            # 检查reader_preferences表是否存在
            if 'reader_preferences' in tables:
                print("\n✅ reader_preferences表存在")
                
                # 检查表结构
                result = await conn.execute(text("\dt+ reader_preferences"))
                print("表结构:")
                async for row in result:
                    print(row)
            else:
                print("\n❌ reader_preferences表不存在")
                
                # 尝试手动创建reader_preferences表
                print("\n尝试手动创建reader_preferences表...")
                try:
                    await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS reader_preferences (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        source VARCHAR(50) NOT NULL,
                        genre VARCHAR(50),
                        tags TEXT[],
                        ranking_data JSONB DEFAULT '{}',
                        comment_sentiment JSONB DEFAULT '{}',
                        trend_score FLOAT DEFAULT 0.0,
                        data_date DATE,
                        crawler_task_id UUID REFERENCES crawler_tasks(id) ON DELETE SET NULL,
                        book_id VARCHAR(100),
                        book_title VARCHAR(200),
                        author_name VARCHAR(100),
                        rating FLOAT,
                        word_count INTEGER,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                    """))
                    print("✅ reader_preferences表创建成功")
                except Exception as e:
                    print(f"❌ 创建表失败: {e}")
                    
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
    finally:
        await engine.dispose()
        print("\n数据库连接已关闭")

if __name__ == "__main__":
    asyncio.run(check_db_status())
