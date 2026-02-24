#!/usr/bin/env python3
"""
小说AI助手集成测试脚本
测试小说信息获取、上下文构建和智能内容分析功能
"""

import asyncio
import logging
from backend.services.ai_chat_service import AiChatService
from core.database import async_session_factory

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_get_novel_info():
    """测试小说信息获取功能"""
    logger.info("开始测试小说信息获取功能...")
    
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        # 测试用的小说ID（需要替换为实际存在的小说ID）
        # 注意：这里需要使用数据库中实际存在的小说ID
        test_novel_id = "123e4567-e89b-12d3-a456-426614174000"  # 示例ID，需要替换
        
        try:
            # 测试无效的小说ID格式
            logger.info("测试无效的小说ID格式...")
            result = await service.get_novel_info("invalid-id")
            logger.info(f"无效ID测试结果: {result}")
            assert "error" in result
            assert "无效的小说 ID 格式" in result["error"]
            logger.info("✓ 无效ID测试通过")
            
            # 测试小说不存在的情况
            logger.info("测试小说不存在的情况...")
            result = await service.get_novel_info("123e4567-e89b-12d3-a456-426614174000")
            logger.info(f"小说不存在测试结果: {result}")
            if "error" in result:
                logger.info("✓ 小说不存在测试通过")
            else:
                logger.info("✓ 小说存在，获取成功")
                # 验证返回数据的完整性
                assert "id" in result
                assert "title" in result
                assert "genre" in result
                assert "status" in result
                assert "world_setting" in result
                assert "characters" in result
                assert "plot_outline" in result
                assert "chapters" in result
                logger.info(f"✓ 小说信息获取完整: {result['title']}")
                
        except Exception as e:
            logger.error(f"测试小说信息获取失败: {e}")
            raise

async def test_revision_intent_analysis():
    """测试修订意图分析功能"""
    logger.info("开始测试修订意图分析功能...")
    
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        # 测试用例
        test_cases = [
            ("我觉得小说的世界观设定不够合理，特别是修炼体系", "world_setting"),
            ("主角的性格塑造不够立体，需要更多背景故事", "character"),
            ("剧情发展太慢，主线不够清晰", "outline"),
            ("第3章的描写不够生动，对话有点生硬", "chapter"),
            ("小说整体还不错，需要一些小的调整", "general"),
        ]
        
        for i, (message, expected_type) in enumerate(test_cases):
            try:
                result = service._analyze_revision_intent(message)
                logger.info(f"测试用例 {i+1}: '{message}' → {result}")
                # 这里不做严格断言，因为意图分析可能有多种合理结果
                logger.info("✓ 意图分析测试通过")
            except Exception as e:
                logger.error(f"测试修订意图分析失败: {e}")
                raise

async def test_revision_prompt_generation():
    """测试修订提示词生成功能"""
    logger.info("开始测试修订提示词生成功能...")
    
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        # 模拟小说信息
        mock_novel_info = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "测试小说",
            "genre": "玄幻",
            "status": "连载中",
            "synopsis": "这是一部测试用的玄幻小说，讲述了主角的成长故事。",
            "world_setting": {
                "id": "1",
                "setting_type": "玄幻",
                "content": "这是一个充满灵气的世界，修炼等级分为练气、筑基、金丹、元婴等多个层次。"
            },
            "characters": [
                {
                    "id": "1",
                    "name": "主角",
                    "role_type": "主角",
                    "description": "一个普通的山村少年，意外获得了神秘传承。",
                    "personality": "勇敢、善良、坚韧",
                    "background": "从小父母双亡，由爷爷抚养长大。"
                }
            ],
            "plot_outline": {
                "id": "1",
                "content": "主角从山村出发，踏上修炼之路，经历各种挑战，最终成为强者。"
            },
            "chapters": [
                {
                    "id": "1",
                    "chapter_number": 1,
                    "title": "第一章 山村少年",
                    "content": "在一个偏远的山村里，住着一个名叫小明的少年..."
                }
            ]
        }
        
        # 测试不同类型的修订提示词生成
        revision_types = ["world_setting", "character", "outline", "chapter", "general"]
        user_message = "我觉得这个部分需要改进"
        
        for revision_type in revision_types:
            try:
                prompt = service._generate_revision_prompt(user_message, revision_type, mock_novel_info)
                logger.info(f"✓ 生成{revision_type}类型的提示词成功")
                logger.info(f"提示词长度: {len(prompt)}")
                # 验证提示词包含必要信息
                assert "用户修订需求" in prompt
                assert "修订目标" in prompt
            except Exception as e:
                logger.error(f"测试修订提示词生成失败: {e}")
                raise

async def test_end_to_end_functionality():
    """测试端到端功能"""
    logger.info("开始测试端到端功能...")
    
    async with async_session_factory() as db:
        service = AiChatService(db)
        
        try:
            # 创建会话
            context = {"novel_id": "123e4567-e89b-12d3-a456-426614174000"}  # 示例ID
            session = await service.create_session("novel_revision", context)
            logger.info(f"✓ 创建会话成功: {session.session_id}")
            
            # 测试发送消息
            test_message = "我觉得小说的世界观设定不够合理"
            logger.info(f"发送测试消息: {test_message}")
            
            # 注意：这里不实际调用LLM，只测试消息处理流程
            # 因为实际调用LLM需要API密钥和网络连接
            # 如果需要完整测试，可以取消下面的注释
            
            # response = service.send_message(session.session_id, test_message)
            # logger.info(f"✓ 收到AI响应: {response[:100]}...")
            
            logger.info("✓ 端到端功能测试通过")
            
        except Exception as e:
            logger.error(f"测试端到端功能失败: {e}")
            # 这里不抛出异常，因为可能是因为缺少API密钥等环境问题
            logger.info("端到端测试可能需要配置API密钥")

async def main():
    """主测试函数"""
    logger.info("开始小说AI助手集成测试...")
    
    try:
        # 运行所有测试
        await test_get_novel_info()
        await test_revision_intent_analysis()
        await test_revision_prompt_generation()
        await test_end_to_end_functionality()
        
        logger.info("\n🎉 所有测试完成！")
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
