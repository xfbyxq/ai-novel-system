#!/usr/bin/env python3
"""
测试get_novel_info方法
"""

import asyncio
from core.database import async_session_factory
from backend.services.ai_chat_service import AiChatService

async def test_get_novel_info():
    """测试get_novel_info方法"""
    async with async_session_factory() as db:
        try:
            # 创建AiChatService实例
            ai_chat_service = AiChatService(db)
            
            # 测试小说ID
            novel_id = "d52b6369-f1e8-4b9b-b048-c6420a9263ae"
            
            # 调用get_novel_info方法
            novel_info = await ai_chat_service.get_novel_info(novel_id)
            
            print("小说信息:")
            print(f"标题: {novel_info.get('title')}")
            print(f"类型: {novel_info.get('genre')}")
            print(f"是否有错误: {'error' in novel_info}")
            
            # 检查世界观信息
            if 'world_setting' in novel_info:
                world_setting = novel_info['world_setting']
                print(f"\n世界观信息:")
                print(f"类型: {world_setting.get('setting_type')}")
                print(f"内容长度: {len(world_setting.get('content', ''))} 字符")
                print(f"内容预览: {world_setting.get('content', '')[:200]}...")
            else:
                print("\n小说没有世界观信息")
                
            # 检查角色信息
            print(f"\n角色数量: {len(novel_info.get('characters', []))}")
            
            # 检查大纲信息
            if 'plot_outline' in novel_info:
                plot_outline = novel_info['plot_outline']
                print(f"\n大纲内容长度: {len(plot_outline.get('content', ''))} 字符")
            else:
                print("\n小说没有大纲信息")
                
            # 检查章节信息
            print(f"\n章节数量: {len(novel_info.get('chapters', []))}")
            
        except Exception as e:
            print(f"测试失败: {e}")
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(test_get_novel_info())
