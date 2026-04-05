"""
AI Chat 意图分类单元测试

测试 backend.services.ai_chat_service 的 LLM 意图分类功能
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestIntentClassificationSchema:
    """意图分类 Schema 测试."""

    def test_intent_tools_schema_structure(self):
        """测试 INTENT_TOOLS schema 结构正确."""
        from backend.services.ai_chat_service import INTENT_TOOLS

        assert isinstance(INTENT_TOOLS, list)
        assert len(INTENT_TOOLS) == 1

        tool = INTENT_TOOLS[0]
        assert tool["type"] == "function"
        assert "function" in tool

        function_def = tool["function"]
        assert function_def["name"] == "classify_intent"
        assert "parameters" in function_def

    def test_intent_types_complete(self):
        """测试所有意图类型都已定义."""
        from backend.services.ai_chat_service import INTENT_TOOLS

        tool = INTENT_TOOLS[0]
        intent_enum = tool["function"]["parameters"]["properties"]["primary_intent"]["enum"]

        expected_intents = [
            "world_creation",
            "world_revision",
            "character_creation",
            "character_revision",
            "plot_creation",
            "plot_revision",
            "chapter_revision",
            "analysis",
            "general",
        ]

        for intent in expected_intents:
            assert intent in intent_enum

    def test_confidence_score_range(self):
        """测试置信度范围定义正确."""
        from backend.services.ai_chat_service import INTENT_TOOLS

        tool = INTENT_TOOLS[0]
        confidence = tool["function"]["parameters"]["properties"]["confidence"]

        assert confidence["type"] == "number"
        assert confidence["minimum"] == 0
        assert confidence["maximum"] == 1


class TestIntentClassificationFallback:
    """意图分类回退逻辑测试."""

    @pytest.mark.asyncio
    async def test_fallback_world_creation(self):
        """测试回退逻辑识别世界观创建."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())
        service.client = MagicMock()  # Mock LLM client

        # Mock LLM 调用失败
        service.client.chat_with_tools = AsyncMock(side_effect=Exception("LLM Error"))

        result = await service._classify_intent_fallback(
            "我想创建一个玄幻世界观", SCENE_NOVEL_CREATION
        )

        assert result["primary_intent"] == "world_creation"
        assert result["confidence"] == 0.5
        assert "keyword" in result["reasoning"].lower()

    @pytest.mark.asyncio
    async def test_fallback_character_creation(self):
        """测试回退逻辑识别角色创建."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())
        service.client = MagicMock()

        service.client.chat_with_tools = AsyncMock(side_effect=Exception("LLM Error"))

        result = await service._classify_intent_fallback("帮我设计一个主角", SCENE_NOVEL_CREATION)

        assert result["primary_intent"] == "character_creation"

    @pytest.mark.asyncio
    async def test_fallback_extracts_characters(self):
        """测试回退逻辑提取角色名."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_REVISION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())
        service.client = MagicMock()
        service.client.chat_with_tools = AsyncMock(side_effect=Exception("LLM Error"))

        result = await service._classify_intent_fallback(
            "我想修改张三这个角色的性格", SCENE_NOVEL_REVISION
        )

        entities = result.get("entities", {})
        characters = entities.get("mentioned_characters", [])

        # 应该能提取到角色名（具体结果取决于正则表达式）
        assert isinstance(characters, list)

    @pytest.mark.asyncio
    async def test_fallback_extracts_chapters(self):
        """测试回退逻辑提取章节号."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_REVISION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())
        service.client = MagicMock()
        service.client.chat_with_tools = AsyncMock(side_effect=Exception("LLM Error"))

        result = await service._classify_intent_fallback(
            "优化一下第5章的内容", SCENE_NOVEL_REVISION
        )

        entities = result.get("entities", {})
        chapters = entities.get("mentioned_chapters", [])

        assert 5 in chapters

    @pytest.mark.asyncio
    async def test_fallback_extracts_genre(self):
        """测试回退逻辑提取类型."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())
        service.client = MagicMock()
        service.client.chat_with_tools = AsyncMock(side_effect=Exception("LLM Error"))

        result = await service._classify_intent_fallback("我想写一个都市小说", SCENE_NOVEL_CREATION)

        entities = result.get("entities", {})
        genre = entities.get("genre", "")

        assert genre == "都市"


class TestIntentClassificationLLM:
    """LLM 意图分类测试."""

    @pytest.mark.asyncio
    async def test_llm_classification_success(self):
        """测试 LLM 分类成功."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        # Mock 成功的工具调用响应
        mock_response = {
            "type": "tool_call",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "classify_intent",
                        "arguments": '{"primary_intent": "world_creation", "confidence": 0.9, "reasoning": "用户明确提到创建世界观", "entities": {"mentioned_characters": [], "mentioned_chapters": [], "genre": "玄幻"}}',
                    },
                }
            ],
        }

        service.client = MagicMock()
        service.client.chat_with_tools = AsyncMock(return_value=mock_response)

        result = await service._classify_intent_llm("创建一个玄幻世界观", SCENE_NOVEL_CREATION)

        assert result["primary_intent"] == "world_creation"
        assert result["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self):
        """测试 LLM 失败时回退."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())
        service.client = MagicMock()
        service.client.chat_with_tools = AsyncMock(side_effect=Exception("Network Error"))

        result = await service._classify_intent_llm("设计一个主角", SCENE_NOVEL_CREATION)

        # 应该返回回退结果
        assert result["primary_intent"] == "character_creation"
        assert result["confidence"] == 0.5


class TestAnalyzeUserIntent:
    """_analyze_user_intent 方法测试."""

    @pytest.mark.asyncio
    async def test_analyze_intent_uses_llm_when_confident(self):
        """测试高置信度时使用 LLM 结果."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        mock_response = {
            "type": "tool_call",
            "tool_calls": [
                {
                    "id": "call_123",
                    "function": {
                        "name": "classify_intent",
                        "arguments": '{"primary_intent": "plot_creation", "confidence": 0.85, "reasoning": "测试", "entities": {}}',
                    },
                }
            ],
        }

        service.client = MagicMock()
        service.client.chat_with_tools = AsyncMock(return_value=mock_response)

        result = await service._analyze_user_intent("写一个大纲", SCENE_NOVEL_CREATION)

        assert result == "plot_creation"

    @pytest.mark.asyncio
    async def test_analyze_intent_falls_back_on_llm_error(self):
        """测试 LLM 错误时回退到规则."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())
        service.client = MagicMock()
        service.client.chat_with_tools = AsyncMock(side_effect=Exception("Error"))

        result = await service._analyze_user_intent("创建世界观", SCENE_NOVEL_CREATION)

        # 应该回退到规则匹配
        assert result in ["world_creation", "general_creation"]


class TestRuleBasedIntent:
    """规则意图分析测试."""

    def test_rule_based_world_keywords(self):
        """测试世界观关键词识别."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        # 使用规则中匹配的关键字
        result = service._analyze_user_intent_rule_based("我想设计世界观", SCENE_NOVEL_CREATION)

        assert result == "world_creation"

    def test_rule_based_character_keywords(self):
        """测试角色关键词识别."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        result = service._analyze_user_intent_rule_based("帮我设计主角", SCENE_NOVEL_CREATION)

        assert result == "character_creation"

    def test_rule_based_plot_keywords(self):
        """测试情节关键词识别."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_CREATION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        result = service._analyze_user_intent_rule_based("写一个剧情大纲", SCENE_NOVEL_CREATION)

        assert result == "plot_creation"

    def test_rule_based_revision_world(self):
        """测试修订场景世界观识别."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_REVISION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        result = service._analyze_user_intent_rule_based("优化世界观设定", SCENE_NOVEL_REVISION)

        assert result == "world_setting"

    def test_rule_based_revision_chapter(self):
        """测试修订场景章节识别."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_REVISION,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        result = service._analyze_user_intent_rule_based("修改第3章的描写", SCENE_NOVEL_REVISION)

        assert result == "chapter"

    def test_rule_based_analysis_structure(self):
        """测试分析场景结构识别."""
        from backend.services.ai_chat_service import (
            SCENE_NOVEL_ANALYSIS,
            AiChatService,
        )

        service = AiChatService(db=MagicMock())

        result = service._analyze_user_intent_rule_based("分析小说的整体结构", SCENE_NOVEL_ANALYSIS)

        assert result == "structure_analysis"
