#!/usr/bin/env python3
"""重置数据库迁移"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

from backend.config import settings

async def reset_migrations():
    """重置数据库迁移"""
    print("正在重置数据库迁移...")
    print(f"数据库URL: {settings.DATABASE_URL}")
    
    # 创建异步引擎
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False
    )
    
    try:
        # 测试连接
        async with engine.begin() as conn:
            # 删除所有表
            print("删除所有表...")
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS novels CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS chapters CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS characters CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS generation_tasks CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS plot_outlines CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS world_settings CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS token_usages CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS reader_preferences CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS crawler_tasks CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS crawl_results CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS platform_accounts CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS publish_tasks CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS chapter_publishes CASCADE"))
            
            # 删除所有枚举类型
            print("删除所有枚举类型...")
            enums = [
                'novelstatus', 'chapterstatus', 'roletype', 'gender', 'characterstatus',
                'tasktype', 'taskstatus', 'crawltype', 'crawltaskstatus',
                'accountstatus', 'publishtype', 'publishtaskstatus', 'publishstatus'
            ]
            for enum in enums:
                try:
                    await conn.execute(text(f"DROP TYPE IF EXISTS {enum} CASCADE"))
                except Exception as e:
                    print(f"删除枚举 {enum} 失败: {e}")
            
            print("✅ 数据库已重置")
    except Exception as e:
        print(f"❌ 操作失败: {e}")
    finally:
        await engine.dispose()
        print("\n数据库连接已关闭")

if __name__ == "__main__":
    asyncio.run(reset_migrations())
