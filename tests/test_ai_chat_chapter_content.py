"""测试 AI 助手读取章节内容."""

import asyncio
from uuid import UUID

from backend.services.ai_chat_service import AiChatService
from core.database import async_session_factory


async def test_chapter_content_reading():
    """测试章节内容读取."""
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        # 使用一个已知的小说 ID 测试
        novel_id = "test-novel-id"  # 替换为实际的小说 ID
        
        print(f"测试读取小说 {novel_id} 的章节内容...")
        
        # 测试 get_novel_info
        result = await service.get_novel_info(
            novel_id=novel_id,
            chapter_start=1,
            chapter_end=3,
            force_db=True
        )
        
        print(f"结果：{result}")
        
        if "chapters" in result:
            for chapter in result["chapters"]:
                print(f"\n章节 {chapter['chapter_number']}: {chapter['title']}")
                print(f"字数：{chapter['word_count']}")
                print(f"内容长度：{len(chapter.get('content', ''))}")
                if chapter.get('content'):
                    print(f"内容预览：{chapter['content'][:100]}...")
        else:
            print("❌ 未找到章节数据")


if __name__ == "__main__":
    asyncio.run(test_chapter_content_reading())
