#!/usr/bin/env python3
"""
检查数据库中存在的小说
"""

import asyncio
from core.database import async_session_factory
from core.models.novel import Novel

async def check_novels():
    """检查数据库中存在的小说"""
    async with async_session_factory() as db:
        try:
            result = await db.execute(Novel.__table__.select().limit(5))
            novels = result.all()
            print("数据库中的小说:")
            for novel in novels:
                print(f"ID: {novel.id}, 标题: {novel.title}")
        except Exception as e:
            print(f"查询失败: {e}")
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(check_novels())
