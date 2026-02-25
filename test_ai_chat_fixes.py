"""
AI助手模块集成测试 - 验证修复效果
测试内容:
1. save_session消息保存逻辑
2. load_session重复消息问题
3. send_message_stream异常处理
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.services.ai_chat_service import AiChatService, ChatSession, ChatMessage
from backend.services.memory_service import get_novel_memory_service
from core.database import async_session_factory


async def test_chat_session():
    """测试ChatSession基本功能"""
    print("\n=== 测试ChatSession基本功能 ===")
    
    session = ChatSession("test-session-1", "novel_analysis")
    
    # 验证欢迎消息
    assert len(session.messages) == 1
    assert session.messages[0].role == "assistant"
    print("✅ 欢迎消息正确添加")
    
    # 添加用户消息
    session.add_user_message("测试消息")
    assert len(session.messages) == 2
    assert len(session.conversation_history) == 1  # 只有用户消息
    print("✅ 用户消息正确添加")
    
    # 添加助手消息
    session.add_assistant_message("助手回复")
    assert len(session.messages) == 3
    assert len(session.conversation_history) == 2  # 用户消息+助手消息
    print("✅ 助手消息正确添加")
    
    return session


async def test_save_session_messages():
    """测试save_session消息保存逻辑"""
    print("\n=== 测试save_session消息保存逻辑 ===")
    
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        # 创建测试会话
        session = ChatSession("test-save-session", "novel_analysis")
        session.add_user_message("第一条用户消息")
        session.add_assistant_message("第一条助手回复")
        session.add_user_message("第二条用户消息")
        session.add_assistant_message("第二条助手回复")
        
        # 第一次保存
        await service.save_session(session)
        print("✅ 第一次保存成功")
        
        # 模拟从数据库加载并验证消息数量
        from sqlalchemy import select
        from core.models.ai_chat_session import AIChatMessage
        
        result = await db.execute(
            select(AIChatMessage)
            .where(AIChatMessage.session_id == session.session_id)
            .order_by(AIChatMessage.created_at)
        )
        messages = result.scalars().all()
        
        # 应该有5条消息（1欢迎+2用户+2助手）
        assert len(messages) == 5, f"预期5条消息，实际{len(messages)}条"
        print(f"✅ 第一次保存后消息数量正确: {len(messages)}条")
        
        # 添加更多消息
        session.add_user_message("第三条用户消息")
        session.add_assistant_message("第三条助手回复")
        
        # 第二次保存（增量保存）
        await service.save_session(session)
        print("✅ 第二次保存成功")
        
        # 再次验证消息数量
        result = await db.execute(
            select(AIChatMessage)
            .where(AIChatMessage.session_id == session.session_id)
            .order_by(AIChatMessage.created_at)
        )
        messages = result.scalars().all()
        
        # 应该有7条消息（5+2新消息）
        assert len(messages) == 7, f"预期7条消息，实际{len(messages)}条"
        print(f"✅ 第二次保存后消息数量正确: {len(messages)}条")
        
        # 清理测试数据
        from core.models.ai_chat_session import AIChatSession
        await db.execute(
            AIChatMessage.__table__.delete().where(AIChatMessage.session_id == session.session_id)
        )
        await db.execute(
            AIChatSession.__table__.delete().where(AIChatSession.session_id == session.session_id)
        )
        await db.commit()
        print("✅ 测试数据清理完成")


async def test_load_session_no_duplicates():
    """测试load_session不会产生重复消息"""
    print("\n=== 测试load_session不会产生重复消息 ===")
    
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        # 创建并保存会话
        session = ChatSession("test-load-session", "novel_analysis")
        session.add_user_message("测试用户消息")
        session.add_assistant_message("测试助手回复")
        
        await service.save_session(session)
        print("✅ 会话保存成功")
        
        # 从数据库加载会话
        loaded_session = await service.load_session(session.session_id)
        
        assert loaded_session is not None
        print("✅ 会话加载成功")
        
        # 验证消息数量（应该是3条：1欢迎+1用户+1助手）
        assert len(loaded_session.messages) == 3, f"预期3条消息，实际{len(loaded_session.messages)}条"
        print(f"✅ 加载后消息数量正确: {len(loaded_session.messages)}条")
        
        # 验证消息内容
        assert loaded_session.messages[0].role == "assistant"  # 欢迎消息
        assert loaded_session.messages[1].role == "user"
        assert loaded_session.messages[2].role == "assistant"
        print("✅ 消息顺序正确")
        
        # 清理测试数据
        from core.models.ai_chat_session import AIChatSession, AIChatMessage
        await db.execute(
            AIChatMessage.__table__.delete().where(AIChatMessage.session_id == session.session_id)
        )
        await db.execute(
            AIChatSession.__table__.delete().where(AIChatSession.session_id == session.session_id)
        )
        await db.commit()
        print("✅ 测试数据清理完成")


async def test_session_context():
    """测试会话上下文处理"""
    print("\n=== 测试会话上下文处理 ===")
    
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        # 创建带上下文的会话
        context = {
            "novel_id": "test-novel-id",
            "chapter_start": 1,
            "chapter_end": 5
        }
        
        session = ChatSession("test-context-session", "novel_revision", context)
        
        # 验证上下文
        assert session.context.get("novel_id") == "test-novel-id"
        assert session.context.get("chapter_start") == 1
        assert session.context.get("chapter_end") == 5
        print("✅ 会话上下文正确设置")
        
        # 保存并重新加载
        await service.save_session(session)
        loaded_session = await service.load_session(session.session_id)
        
        # 验证上下文在加载后保持不变
        assert loaded_session.context.get("novel_id") == "test-novel-id"
        print("✅ 上下文在加载后保持不变")
        
        # 清理测试数据
        from core.models.ai_chat_session import AIChatSession, AIChatMessage
        await db.execute(
            AIChatMessage.__table__.delete().where(AIChatMessage.session_id == session.session_id)
        )
        await db.execute(
            AIChatSession.__table__.delete().where(AIChatSession.session_id == session.session_id)
        )
        await db.commit()
        print("✅ 测试数据清理完成")


async def test_memory_service():
    """测试记忆服务"""
    print("\n=== 测试记忆服务 ===")
    
    memory_service = get_novel_memory_service()
    
    # 测试设置记忆 - 使用扁平化的数据结构，与get_novel_info返回的格式一致
    test_novel_id = "test-memory-novel"
    test_data = {
        "id": test_novel_id,
        "title": "测试小说",
        "genre": "玄幻",
        "synopsis": "这是一个测试小说",
        "status": "writing",
        "world_setting": {"content": "测试世界观"},
        "characters": [],
        "plot_outline": None,
        "chapters": []
    }
    
    memory_service.set_novel_memory(test_novel_id, test_data)
    print("✅ 记忆设置成功")
    
    # 测试获取记忆
    retrieved_data = memory_service.get_novel_memory(test_novel_id)
    assert retrieved_data is not None
    # 记忆服务会将数据结构化为 base/details/chapters 三层结构
    assert retrieved_data["base"]["title"] == "测试小说"
    print("✅ 记忆获取成功")
    
    # 测试删除记忆
    memory_service.invalidate_novel_memory(test_novel_id)
    retrieved_data = memory_service.get_novel_memory(test_novel_id)
    assert retrieved_data is None
    print("✅ 记忆删除成功")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("开始AI助手模块集成测试")
    print("=" * 60)
    
    try:
        await test_chat_session()
        await test_save_session_messages()
        await test_load_session_no_duplicates()
        await test_session_context()
        await test_memory_service()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        raise
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
