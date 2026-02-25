#!/usr/bin/env python3
"""
测试AI助手对小说世界观问题的回答能力
"""

import asyncio
import json
from backend.services.ai_chat_service import AiChatService, SCENE_NOVEL_ANALYSIS
from core.database import async_session_factory

async def test_worldview_question():
    """测试AI助手是否能够回答小说世界观问题"""
    async with async_session_factory() as db:
        # 创建AI聊天服务
        chat_service = AiChatService(db)
        
        # 使用刚创建的测试小说ID
        novel_id = "ec8c5c3e-e10f-4506-9445-9af42130453a"
        
        # 创建会话，使用小说分析场景
        session = await chat_service.create_session(
            scene=SCENE_NOVEL_ANALYSIS,
            context={"novel_id": novel_id}
        )
        
        print(f"创建会话成功: {session.session_id}")
        
        # 测试问题：询问小说世界观
        test_questions = [
            "这个小说的世界观是什么？",
            "小说的修炼体系是怎样的？",
            "小说的地理环境如何？",
            "小说的势力划分有哪些？"
        ]
        
        for question in test_questions:
            print(f"\n测试问题: {question}")
            print("=" * 50)
            
            # 发送消息并获取回复
            response = await chat_service.send_message(session.session_id, question)
            
            print(f"AI回复: {response}")
            print("=" * 50)
            
            # 检查回复是否包含追问
            if "为了给你提供更准确的帮助，我需要了解更多信息" in response:
                print("❌ 测试失败：AI助手仍然在追问，没有使用现有小说数据")
            else:
                print("✅ 测试成功：AI助手使用了现有小说数据回答问题")
        
        # 测试流式响应
        print("\n测试流式响应:")
        print("=" * 50)
        question = "这个小说的世界观详细介绍一下"
        print(f"测试问题: {question}")
        
        async for chunk in chat_service.send_message_stream(session.session_id, question):
            print(chunk, end="")
        
        print("\n" + "=" * 50)
        print("✅ 流式响应测试完成")

if __name__ == "__main__":
    asyncio.run(test_worldview_question())
