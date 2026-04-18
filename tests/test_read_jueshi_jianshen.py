"""测试 AI 助手读取《绝世剑神》小说内容."""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.ai_chat_service import AiChatService
from core.database import async_session_factory
from sqlalchemy import select
from core.models.novel import Novel


async def test_read_jueshi_jianshen():
    """测试读取《绝世剑神》小说内容."""
    
    print("=" * 60)
    print("测试 AI 助手读取《绝世剑神》小说内容")
    print("=" * 60)
    
    async with async_session_factory() as db:
        # 创建 AI 助手服务
        service = AiChatService(db)
        
        # 查找《绝世剑神》小说
        result = await db.execute(
            select(Novel).where(Novel.title == "绝世剑神")
        )
        novel = result.scalar_one_or_none()
        
        if not novel:
            print("\n❌ 未找到《绝世剑神》小说")
            print("可用小说列表:")
            
            all_novels = await db.execute(select(Novel))
            for n in all_novels.scalars().all():
                print(f"  - {n.title} (ID: {n.id})")
            return
        
        print(f"\n✅ 找到小说：{novel.title}")
        print(f"   ID: {novel.id}")
        print(f"   作者：{novel.author}")
        print(f"   类型：{novel.genre}")
        print(f"   状态：{novel.status}")
        print(f"   章节数：{novel.chapter_count}")
        print(f"   字数：{novel.word_count}")
        
        # 测试读取小说信息（包含章节内容）
        print("\n" + "=" * 60)
        print("测试读取小说信息（包含前 3 章内容）")
        print("=" * 60)
        
        novel_info = await service.get_novel_info(
            novel_id=str(novel.id),
            chapter_start=1,
            chapter_end=3,
            force_db=True
        )
        
        if "error" in novel_info:
            print(f"\n❌ 读取失败：{novel_info['error']}")
            return
        
        print(f"\n✅ 读取成功！")
        print(f"   小说标题：{novel_info.get('title')}")
        print(f"   作者：{novel_info.get('author')}")
        print(f"   章节数：{len(novel_info.get('chapters', []))}")
        
        # 显示章节信息
        print("\n章节列表:")
        for chapter in novel_info.get('chapters', []):
            print(f"\n  第{chapter['chapter_number']}章：{chapter['title']}")
            print(f"    字数：{chapter['word_count']}")
            
            # 显示内容预览
            content = chapter.get('content', '')
            if content:
                preview = content[:100] + "..." if len(content) > 100 else content
                print(f"    内容预览：{preview}")
            else:
                print(f"    ❌ 内容为空！")
        
        # 测试图库查询（如果已启用）
        print("\n" + "=" * 60)
        print("测试图库查询功能")
        print("=" * 60)
        
        if service.gallery_enabled:
            print("\n✅ 图库功能已启用")
            
            # 测试查询角色关系
            print("\n测试查询角色关系网络...")
            char_result = await service.query_character_network(novel.id)
            if "error" in char_result:
                print(f"  ❌ 查询失败：{char_result['error']}")
            else:
                print(f"  ✅ 查询成功")
                print(f"     结果：{char_result}")
            
            # 测试查询世界观
            print("\n测试查询世界观设定地图...")
            world_result = await service.query_world_setting_map(novel.id)
            if "error" in world_result:
                print(f"  ❌ 查询失败：{world_result['error']}")
            else:
                print(f"  ✅ 查询成功")
                print(f"     结果：{world_result}")
        else:
            print("\n⚠️  图库功能未启用（Neo4j 未配置）")
            print("    如需启用，请配置 Neo4j 数据库连接")


if __name__ == "__main__":
    asyncio.run(test_read_jueshi_jianshen())
