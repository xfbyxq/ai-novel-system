#!/usr/bin/env python3
"""
检查小说的世界观信息
"""

import asyncio
from core.database import async_session_factory
from core.models.novel import Novel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def check_novel_worldview():
    """检查小说的世界观信息"""
    async with async_session_factory() as db:
        try:
            # 查询特定小说
            novel_id = "d52b6369-f1e8-4b9b-b048-c6420a9263ae"
            query = select(Novel).where(Novel.id == novel_id).options(
                selectinload(Novel.world_setting),
                selectinload(Novel.characters),
                selectinload(Novel.plot_outline),
                selectinload(Novel.chapters)
            )
            result = await db.execute(query)
            novel = result.scalar_one_or_none()
            
            if not novel:
                print(f"小说不存在: {novel_id}")
                return
            
            print(f"小说标题: {novel.title}")
            print(f"小说类型: {novel.genre}")
            
            # 检查世界观信息
            if novel.world_setting:
                print(f"\n世界观信息:")
                print(f"ID: {novel.world_setting.id}")
                print(f"类型: {novel.world_setting.setting_type}")
                print(f"内容长度: {len(novel.world_setting.content)} 字符")
                print(f"内容预览: {novel.world_setting.content[:200]}...")
            else:
                print("\n小说没有世界观信息")
                
            # 检查角色信息
            print(f"\n角色数量: {len(novel.characters)}")
            if novel.characters:
                print("前3个角色:")
                for char in novel.characters[:3]:
                    print(f"- {char.name}: {char.role_type}")
            
            # 检查大纲信息
            if novel.plot_outline:
                print(f"\n大纲内容长度: {len(novel.plot_outline.content)} 字符")
                print(f"大纲预览: {novel.plot_outline.content[:200]}...")
            else:
                print("\n小说没有大纲信息")
                
            # 检查章节信息
            print(f"\n章节数量: {len(novel.chapters)}")
            if novel.chapters:
                print("前3个章节:")
                for chapter in novel.chapters[:3]:
                    print(f"- 第{chapter.chapter_number}章: {chapter.title}")
                    
        except Exception as e:
            print(f"查询失败: {e}")
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(check_novel_worldview())
