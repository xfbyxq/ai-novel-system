"""修订数据验证服务单元测试.

测试 revision_data_validator.py 中的 RevisionDataValidator 服务.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestRevisionDataValidator:
    """RevisionDataValidator 测试."""

    @pytest.fixture
    def mock_db_session(self):
        """模拟数据库会话."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def validator(self, mock_db_session):
        """创建验证器实例."""
        from backend.services.revision_data_validator import RevisionDataValidator

        return RevisionDataValidator(db=mock_db_session)

    @pytest.mark.asyncio
    async def test_validate_feedback_no_entities(self, validator, mock_db_session):
        """测试无实体引用的反馈验证."""
        # 模拟数据库查询结果 - 空数据
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        novel_id = str(uuid4())
        result = await validator.validate_feedback(
            "这部小说写得真好", novel_id
        )

        assert result.entity_count == 0
        assert result.valid_count == 0
        assert result.invalid_count == 0
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_feedback_with_valid_character(
        self, validator, mock_db_session
    ):
        """测试验证存在的角色."""
        novel_id = str(uuid4())
        char_id = uuid4()

        # 创建模拟角色数据
        mock_char = MagicMock()
        mock_char.name = "张三"
        mock_char.id = char_id
        mock_char.role_type = "protagonist"
        mock_char.personality = "稳重内敛"

        # 模拟数据库查询结果
        mock_result_chars = MagicMock()
        mock_result_chars.scalars.return_value.all.return_value = [mock_char]

        mock_result_chapters = MagicMock()
        mock_result_chapters.scalars.return_value.all.return_value = []
        mock_result_chapters.scalar_one_or_none.return_value = None

        # 设置 execute 返回不同的结果
        mock_db_session.execute = AsyncMock(
            side_effect=[
                mock_result_chars,  # 角色查询
                mock_result_chapters,  # 章节查询
                mock_result_chapters,  # 世界观查询
                mock_result_chapters,  # 大纲查询
            ]
        )

        result = await validator.validate_feedback(
            "张三的性格需要修改", novel_id
        )

        # 验证角色存在
        assert len(result.character_results) >= 1
        char_result = result.character_results[0]
        assert char_result.exists is True
        assert char_result.entity_name == "张三"

    @pytest.mark.asyncio
    async def test_validate_feedback_with_unknown_character_not_extracted(
        self, validator, mock_db_session
    ):
        """测试验证未知角色（数据库中不存在该角色，无法提取）."""
        novel_id = str(uuid4())

        # 创建一个数据库中存在的角色"张三"
        mock_existing_char = MagicMock()
        mock_existing_char.name = "张三"
        mock_existing_char.id = uuid4()
        mock_existing_char.role_type = "protagonist"

        # 模拟数据库返回现有角色
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_existing_char]
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # 反馈中提到"李四"，但数据库中没有这个角色
        # 由于只基于数据库中的角色名提取，"李四"不会被检测到
        result = await validator.validate_feedback(
            "李四的性格需要修改", novel_id
        )

        # 由于"李四"不在数据库中，不会被提取
        # 因此没有角色验证结果
        assert len(result.character_results) == 0
        # 验证结果应该是有效的（因为没有检测到无效实体）
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_feedback_with_chapter_reference(
        self, validator, mock_db_session
    ):
        """测试验证章节引用."""
        novel_id = str(uuid4())
        chapter_id = uuid4()

        # 创建模拟章节数据
        mock_chapter = MagicMock()
        mock_chapter.chapter_number = 5
        mock_chapter.id = chapter_id
        mock_chapter.title = "测试章节"

        # 模拟数据库查询结果
        mock_result_chars = MagicMock()
        mock_result_chars.scalars.return_value.all.return_value = []

        mock_result_chapters = MagicMock()
        mock_result_chapters.scalars.return_value.all.return_value = [mock_chapter]

        mock_result_empty = MagicMock()
        mock_result_empty.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[
                mock_result_chars,  # 角色查询
                mock_result_chapters,  # 章节查询
                mock_result_empty,  # 世界观查询
                mock_result_empty,  # 大纲查询
            ]
        )

        result = await validator.validate_feedback("第5章需要修改", novel_id)

        # 验证章节存在
        assert len(result.chapter_results) >= 1
        chapter_result = result.chapter_results[0]
        assert chapter_result.exists is True
        assert chapter_result.entity_name == "第5章"

    @pytest.mark.asyncio
    async def test_validate_feedback_with_invalid_chapter(
        self, validator, mock_db_session
    ):
        """测试验证不存在的章节."""
        novel_id = str(uuid4())

        # 模拟空数据库
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await validator.validate_feedback("第100章需要修改", novel_id)

        # 验证章节不存在
        assert len(result.chapter_results) >= 1
        chapter_result = result.chapter_results[0]
        assert chapter_result.exists is False
        assert chapter_result.entity_name == "第100章"
        assert result.is_valid is False

    def test_extract_entities_chapter_patterns(self, validator):
        """测试章节号提取."""
        # 空上下文用于测试章节提取
        context = {"character_names": [], "chapters": []}
        test_cases = [
            ("第5章需要修改", [5]),
            ("第10章的张三有问题", [10]),
            ("情节发展太慢，需要调整大纲", []),
            ("第3章和第7章有问题", [3, 7]),
        ]

        for feedback, expected_chapters in test_cases:
            result = validator._extract_entities(feedback, context)
            assert (
                result["chapters"] == expected_chapters
            ), f"Failed for: {feedback}"

    def test_extract_entities_world_keywords(self, validator):
        """测试世界观关键词提取."""
        context = {"character_names": [], "chapters": []}
        feedback = "世界观设定需要调整，修炼体系有问题"
        result = validator._extract_entities(feedback, context)

        assert len(result["world_elements"]) > 0
        assert any("世界观" in e for e in result["world_elements"])

    def test_chinese_to_number_conversion(self, validator):
        """测试中文数字转换."""
        assert validator._chinese_to_number("一") == 1
        assert validator._chinese_to_number("十") == 10
        assert validator._chinese_to_number("十五") == 15
        assert validator._chinese_to_number("一百") == 100
        assert validator._chinese_to_number("一千") == 1000
        assert validator._chinese_to_number("5") == 5

    def test_find_similar_names(self, validator):
        """测试相似名称查找."""
        names = ["张三", "李四", "王五", "张飞", "赵六"]
        suggestions = validator._find_similar_names("张三", names)

        # 应该找到张三本身和张飞（包含"张"）
        assert "张三" in suggestions

    def test_generate_warning_with_invalid_entities(self, validator):
        """测试生成警告信息."""
        from backend.services.revision_data_validator import (
            EntityValidationResult,
            ValidationReport,
        )

        report = ValidationReport(
            novel_id="test",
            is_valid=False,
            entity_count=2,
            valid_count=0,
            invalid_count=2,
            character_results=[
                EntityValidationResult(
                    entity_type="character",
                    entity_name="李四",
                    exists=False,
                    suggestions=["张三", "李四四"],
                )
            ],
        )

        context = {"chapter_numbers": [1, 2, 3], "character_names": []}
        warning = validator._generate_warning(report, context)

        assert warning is not None
        assert "李四" in warning
        assert "不存在" in warning

    def test_generate_summary(self, validator):
        """测试生成验证总结."""
        from backend.services.revision_data_validator import (
            EntityValidationResult,
            ValidationReport,
        )

        report = ValidationReport(
            novel_id="test",
            is_valid=True,
            entity_count=2,
            valid_count=2,
            invalid_count=0,
            character_results=[
                EntityValidationResult(
                    entity_type="character",
                    entity_name="张三",
                    exists=True,
                    matched_item={"name": "张三", "role_type": "protagonist"},
                )
            ],
            chapter_results=[
                EntityValidationResult(
                    entity_type="chapter",
                    entity_name="第5章",
                    exists=True,
                    matched_item={"chapter_number": 5, "title": "测试"},
                )
            ],
        )

        summary = validator._generate_summary(report, {})

        assert "张三" in summary
        assert "第5章" in summary
