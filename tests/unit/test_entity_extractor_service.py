"""实体抽取服务单元测试.

测试 backend/services/entity_extractor_service.py 中的实体抽取功能。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestExtractedCharacter:
    """ExtractedCharacter 数据类测试."""

    def test_extracted_character_creation(self):
        """测试抽取的角色实体创建."""
        from backend.services.entity_extractor_service import ExtractedCharacter

        char = ExtractedCharacter(
            name="张三",
            role_type="protagonist",
            gender="male",
            is_new=True,
            actions=["出场", "战斗"],
            status_change="alive",
        )

        assert char.name == "张三"
        assert char.role_type == "protagonist"
        assert char.is_new is True
        assert len(char.actions) == 2

    def test_extracted_character_defaults(self):
        """测试抽取角色的默认值."""
        from backend.services.entity_extractor_service import ExtractedCharacter

        char = ExtractedCharacter(name="李四")

        assert char.role_type == "minor"
        assert char.is_new is True
        assert char.actions == []
        assert char.status_change is None


class TestExtractedLocation:
    """ExtractedLocation 数据类测试."""

    def test_extracted_location_creation(self):
        """测试抽取的地点实体创建."""
        from backend.services.entity_extractor_service import ExtractedLocation

        loc = ExtractedLocation(
            name="青云门",
            location_type="sect",
            description="修仙宗门",
        )

        assert loc.name == "青云门"
        assert loc.location_type == "sect"


class TestExtractedEvent:
    """ExtractedEvent 数据类测试."""

    def test_extracted_event_creation(self):
        """测试抽取的事件实体创建."""
        from backend.services.entity_extractor_service import ExtractedEvent

        event = ExtractedEvent(
            name="宗门大比",
            chapter_number=10,
            event_type="battle",
            participants=["张三", "李四"],
            description="年度大比",
            significance=8,
        )

        assert event.name == "宗门大比"
        assert event.chapter_number == 10
        assert event.event_type == "battle"
        assert len(event.participants) == 2


class TestExtractedForeshadowing:
    """ExtractedForeshadowing 数据类测试."""

    def test_extracted_foreshadowing_creation(self):
        """测试抽取的伏笔实体创建."""
        from backend.services.entity_extractor_service import ExtractedForeshadowing

        fore = ExtractedForeshadowing(
            content="神秘的玉佩",
            planted_chapter=3,
            ftype="item",
            importance=8,
            related_characters=["张三"],
            expected_resolve_chapter=20,
        )

        assert fore.content == "神秘的玉佩"
        assert fore.planted_chapter == 3
        assert fore.ftype == "item"
        assert fore.is_resolved is False


class TestExtractedRelationship:
    """ExtractedRelationship 数据类测试."""

    def test_extracted_relationship_creation(self):
        """测试抽取的关系实体创建."""
        from backend.services.entity_extractor_service import ExtractedRelationship

        rel = ExtractedRelationship(
            from_character="张三",
            to_character="李四",
            relation_type="friend",
            strength=8,
            is_new=True,
            change_type="establish",
        )

        assert rel.from_character == "张三"
        assert rel.to_character == "李四"
        assert rel.relation_type == "friend"
        assert rel.strength == 8


class TestExtractionResult:
    """ExtractionResult 数据类测试."""

    def test_extraction_result_creation(self):
        """测试抽取结果创建."""
        from backend.services.entity_extractor_service import (
            ExtractedCharacter,
            ExtractedEvent,
            ExtractionResult,
        )

        result = ExtractionResult(
            chapter_number=1,
            characters=[ExtractedCharacter(name="张三")],
            events=[ExtractedEvent(name="事件1", chapter_number=1)],
            summary="第一章摘要",
        )

        assert result.chapter_number == 1
        assert len(result.characters) == 1
        assert len(result.events) == 1
        assert result.summary == "第一章摘要"

    def test_extraction_result_to_dict(self):
        """测试抽取结果转换为字典."""
        from backend.services.entity_extractor_service import (
            ExtractedCharacter,
            ExtractedLocation,
            ExtractionResult,
        )

        result = ExtractionResult(
            chapter_number=1,
            characters=[ExtractedCharacter(name="张三", role_type="protagonist")],
            locations=[ExtractedLocation(name="青云门")],
        )

        result_dict = result.to_dict()

        assert result_dict["chapter_number"] == 1
        assert len(result_dict["characters"]) == 1
        assert result_dict["characters"][0]["name"] == "张三"
        assert len(result_dict["locations"]) == 1


class TestEntityExtractorService:
    """EntityExtractorService 服务测试."""

    @pytest.fixture
    def mock_llm_client(self):
        """创建mock LLM客户端."""
        client = MagicMock()
        client.chat = AsyncMock()
        return client

    @pytest.fixture
    def service(self, mock_llm_client):
        """创建服务实例."""
        from backend.services.entity_extractor_service import EntityExtractorService

        return EntityExtractorService(llm_client=mock_llm_client)

    @pytest.mark.asyncio
    async def test_extract_from_chapter_success(self, service, mock_llm_client):
        """测试从章节抽取实体成功."""
        mock_response = {
            "content": json.dumps(
                {
                    "summary": "第一章：主角出场",
                    "characters": [
                        {
                            "name": "张三",
                            "role_type": "protagonist",
                            "gender": "male",
                            "is_new": True,
                            "actions": ["出场", "获得玉佩"],
                        }
                    ],
                    "locations": [{"name": "青云门", "location_type": "sect"}],
                    "events": [{"name": "入门测试", "event_type": "plot", "significance": 7}],
                    "foreshadowings": [],
                    "relationships": [],
                }
            ),
            "usage": {"total_tokens": 500},
        }
        mock_llm_client.chat.return_value = mock_response

        result = await service.extract_from_chapter(
            chapter_number=1,
            chapter_content="这是第一章的内容...",
            known_characters=["李四"],
        )

        assert result.chapter_number == 1
        assert result.summary == "第一章：主角出场"
        assert len(result.characters) == 1
        assert result.characters[0].name == "张三"
        assert result.extraction_time > 0

    @pytest.mark.asyncio
    async def test_extract_from_chapter_empty_content(self, service, mock_llm_client):
        """测试抽取空章节内容."""
        mock_response = {
            "content": json.dumps({"summary": "空章节"}),
            "usage": {"total_tokens": 100},
        }
        mock_llm_client.chat.return_value = mock_response

        result = await service.extract_from_chapter(
            chapter_number=1,
            chapter_content="",
        )

        assert result.chapter_number == 1

    @pytest.mark.asyncio
    async def test_extract_from_chapter_llm_error(self, service, mock_llm_client):
        """测试LLM调用失败."""
        mock_llm_client.chat.side_effect = Exception("LLM服务不可用")

        result = await service.extract_from_chapter(
            chapter_number=1,
            chapter_content="测试内容",
        )

        assert result.summary is not None
        assert "抽取失败" in result.summary

    @pytest.mark.asyncio
    async def test_extract_entities_batch(self, service, mock_llm_client):
        """测试批量抽取实体."""
        mock_llm_client.chat.return_value = {
            "content": json.dumps(
                {
                    "characters": [{"name": "张三", "role_type": "protagonist"}],
                }
            ),
            "usage": {"total_tokens": 200},
        }

        chapters = [
            {"chapter_number": 1, "content": "第一章"},
            {"chapter_number": 2, "content": "第二章"},
        ]

        results = await service.extract_entities_batch(chapters)

        assert len(results) == 2
        assert results[0].chapter_number == 1
        assert results[1].chapter_number == 2

    @pytest.mark.asyncio
    async def test_extract_entities_batch_updates_known_chars(self, service, mock_llm_client):
        """测试批量抽取更新已知角色列表."""
        mock_llm_client.chat.return_value = {
            "content": json.dumps(
                {
                    "characters": [{"name": "张三", "is_new": True}],
                }
            ),
            "usage": {"total_tokens": 100},
        }

        chapters = [
            {"chapter_number": 1, "content": "第一章"},
            {"chapter_number": 2, "content": "第二章"},
        ]

        await service.extract_entities_batch(chapters, known_characters=["李四"])

        # 第一章发现新角色张三，第二章应该知道
        assert mock_llm_client.chat.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_foreshadowing_check(self, service, mock_llm_client):
        """测试伏笔回收检查."""
        mock_llm_client.chat.return_value = {
            "content": json.dumps(["fore-001", "fore-002"]),
            "usage": {"total_tokens": 100},
        }

        pending = [
            {"id": "fore-001", "content": "玉佩", "ftype": "item"},
            {"id": "fore-002", "content": "身世", "ftype": "mystery"},
        ]

        resolved = await service.extract_foreshadowing_check(
            chapter_content="章节内容",
            pending_foreshadowings=pending,
        )

        assert len(resolved) == 2
        assert "fore-001" in resolved

    @pytest.mark.asyncio
    async def test_extract_foreshadowing_check_empty(self, service, mock_llm_client):
        """测试空伏笔列表的回收检查."""
        resolved = await service.extract_foreshadowing_check(
            chapter_content="章节内容",
            pending_foreshadowings=[],
        )

        assert resolved == []
        mock_llm_client.chat.assert_not_called()


class TestJsonParsing:
    """JSON解析测试."""

    @pytest.fixture
    def service(self):
        """创建服务实例."""
        from backend.services.entity_extractor_service import EntityExtractorService

        mock_llm = MagicMock()
        return EntityExtractorService(llm_client=mock_llm)

    def test_parse_json_response_direct(self, service):
        """测试直接解析JSON响应."""
        content = '{"name": "张三", "age": 25}'

        result = service._parse_json_response(content)

        assert result["name"] == "张三"
        assert result["age"] == 25

    def test_parse_json_response_code_block(self, service):
        """测试从代码块解析JSON."""
        content = """
        这是回复内容
        ```json
        {"name": "张三", "age": 25}
        ```
        """

        result = service._parse_json_response(content)

        assert result["name"] == "张三"

    def test_parse_json_response_markdown_block(self, service):
        """测试从markdown代码块解析."""
        content = """
        ```
        {"name": "张三"}
        ```
        """

        result = service._parse_json_response(content)

        assert result["name"] == "张三"

    def test_parse_json_response_invalid(self, service):
        """测试解析无效JSON."""
        content = "这不是JSON格式的内容"

        result = service._parse_json_response(content)

        assert result == {}

    def test_parse_json_array_direct(self, service):
        """测试直接解析JSON数组."""
        content = '["item1", "item2", "item3"]'

        result = service._parse_json_array(content)

        assert len(result) == 3
        assert "item1" in result

    def test_parse_json_array_from_code_block(self, service):
        """测试从代码块解析JSON数组."""
        content = """
        ```json
        ["id1", "id2"]
        ```
        """

        result = service._parse_json_array(content)

        assert len(result) == 2

    def test_parse_json_array_invalid(self, service):
        """测试解析无效JSON数组."""
        content = "不是数组"

        result = service._parse_json_array(content)

        assert result == []


class TestBuildExtractionResult:
    """构建抽取结果测试."""

    @pytest.fixture
    def service(self):
        """创建服务实例."""
        from backend.services.entity_extractor_service import EntityExtractorService

        mock_llm = MagicMock()
        return EntityExtractorService(llm_client=mock_llm)

    def test_build_extraction_result_full(self, service):
        """测试构建完整抽取结果."""
        data = {
            "summary": "章节摘要",
            "characters": [
                {
                    "name": "张三",
                    "role_type": "protagonist",
                    "gender": "male",
                    "is_new": True,
                    "actions": ["出场"],
                }
            ],
            "locations": [{"name": "青云门", "location_type": "sect"}],
            "events": [
                {
                    "name": "入门",
                    "event_type": "plot",
                    "participants": ["张三"],
                    "significance": 7,
                }
            ],
            "foreshadowings": [
                {
                    "content": "玉佩",
                    "ftype": "item",
                    "importance": 8,
                    "related_characters": ["张三"],
                    "is_resolved": False,
                }
            ],
            "relationships": [
                {
                    "from_character": "张三",
                    "to_character": "李四",
                    "relation_type": "friend",
                    "strength": 7,
                }
            ],
        }

        result = service._build_extraction_result(1, data)

        assert result.chapter_number == 1
        assert result.summary == "章节摘要"
        assert len(result.characters) == 1
        assert len(result.locations) == 1
        assert len(result.events) == 1
        assert len(result.foreshadowings) == 1
        assert len(result.relationships) == 1

    def test_build_extraction_result_empty(self, service):
        """测试构建空抽取结果."""
        result = service._build_extraction_result(1, {})

        assert result.chapter_number == 1
        assert result.characters == []
        assert result.locations == []
        assert result.events == []


class TestConvenienceFunction:
    """便捷函数测试."""

    @pytest.mark.asyncio
    async def test_extract_chapter_entities_disabled(self):
        """测试实体抽取功能禁用."""
        with patch("backend.config.settings.ENABLE_ENTITY_EXTRACTION", False):
            from backend.services.entity_extractor_service import extract_chapter_entities

            result = await extract_chapter_entities(1, "内容")

            assert result.summary == "实体抽取功能未启用"

    @pytest.mark.asyncio
    async def test_extract_chapter_entities_enabled(self):
        """测试实体抽取功能启用."""
        with (
            patch("backend.config.settings.ENABLE_ENTITY_EXTRACTION", True),
            patch(
                "backend.services.entity_extractor_service.EntityExtractorService"
            ) as mock_service,
        ):
            mock_instance = MagicMock()
            mock_instance.extract_from_chapter = AsyncMock(return_value=MagicMock(chapter_number=1))
            mock_service.return_value = mock_instance

            from backend.services.entity_extractor_service import extract_chapter_entities

            result = await extract_chapter_entities(1, "内容")

            assert result.chapter_number == 1
