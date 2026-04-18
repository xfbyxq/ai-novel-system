"""JSON 提取功能单元测试.

测试 ChapterSummaryGenerator._extract_json 方法的各种场景.
"""

import json
import pytest


class TestExtractJson:
    """_extract_json 静态方法测试类."""

    def test_valid_json(self):
        """测试标准 JSON 解析."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        result = ChapterSummaryGenerator._extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_with_nested_objects(self):
        """测试嵌套对象的 JSON 解析."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        json_str = '{"key": "value", "nested": {"a": 1, "b": [1, 2, 3]}}'
        result = ChapterSummaryGenerator._extract_json(json_str)
        assert result["key"] == "value"
        assert result["nested"]["a"] == 1
        assert result["nested"]["b"] == [1, 2, 3]

    def test_json_with_newlines(self):
        """测试带换行符的 JSON."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        json_str = '{\n    "key": "value"\n}'
        result = ChapterSummaryGenerator._extract_json(json_str)
        assert result == {"key": "value"}

    def test_markdown_json_block(self):
        """测试 Markdown 代码块中的 JSON."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '```json\n{"key": "value"}\n```'
        result = ChapterSummaryGenerator._extract_json(text)
        assert result == {"key": "value"}

    def test_markdown_json_block_without_language(self):
        """测试 Markdown 代码块（无语言标识）."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '```\n{"key": "value"}\n```'
        result = ChapterSummaryGenerator._extract_json(text)
        assert result == {"key": "value"}

    def test_incomplete_json_missing_brace(self):
        """测试不完整 JSON（缺少闭合括号）."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '{"key": "value", "nested": {"a": 1}'
        result = ChapterSummaryGenerator._extract_json(text)
        assert result["key"] == "value"
        assert result["nested"]["a"] == 1

    def test_incomplete_json_multiple_missing_braces(self):
        """测试不完整 JSON（缺少多个闭合括号）- 返回空摘要兜底."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '{"level1": {"level2": {"level3": "value"'
        result = ChapterSummaryGenerator._extract_json(text)
        assert isinstance(result, dict)
        assert "plot_progress" in result

    def test_json_with_trailing_comma(self):
        """测试带有尾随逗号的不完整 JSON - 返回空摘要兜底."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '{"key": "value",}'
        result = ChapterSummaryGenerator._extract_json(text)
        assert isinstance(result, dict)
        assert "plot_progress" in result

    def test_empty_string(self):
        """测试空字符串."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        result = ChapterSummaryGenerator._extract_json("")
        assert isinstance(result, dict)
        assert result.get("plot_progress") == ""

    def test_non_json_text(self):
        """测试非 JSON 纯文本."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        result = ChapterSummaryGenerator._extract_json("这是一段普通文本")
        assert isinstance(result, dict)
        assert result.get("plot_progress") == "这是一段普通文本"

    def test_json_surrounded_by_text(self):
        """测试文本中包含 JSON."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '以下是生成的摘要：\n{"result": "success"}\n请确认。'
        result = ChapterSummaryGenerator._extract_json(text)
        assert result == {"result": "success"}

    def test_json_with_special_characters(self):
        """测试包含特殊字符的 JSON."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '{"message": "Hello\\nWorld\\t!", "emoji": "🎉"}'
        result = ChapterSummaryGenerator._extract_json(text)
        assert result["message"] == "Hello\nWorld\t!"
        assert result["emoji"] == "🎉"

    def test_json_array(self):
        """测试 JSON 数组 - 返回数组或兜底字典."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        result = ChapterSummaryGenerator._extract_json("[1, 2, 3]")
        assert isinstance(result, (list, dict))
        if isinstance(result, dict):
            assert "plot_progress" in result

    def test_whitespace_only(self):
        """测试仅包含空白字符."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        result = ChapterSummaryGenerator._extract_json("   \n\t  ")
        assert isinstance(result, dict)

    def test_leading_whitespace(self):
        """测试前导空白."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        text = '   \n{"key": "value"}  '
        result = ChapterSummaryGenerator._extract_json(text)
        assert result == {"key": "value"}


class TestExtractEnding:
    """_extract_ending 静态方法测试类."""

    def test_normal_content(self):
        """测试正常内容提取."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        content = "这是章节内容。" + "。" * 50 + "这是结尾部分。"
        result = ChapterSummaryGenerator._extract_ending(content, length=100)
        assert isinstance(result, str)
        assert len(result) <= 100

    def test_empty_content(self):
        """测试空内容."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        result = ChapterSummaryGenerator._extract_ending("")
        assert result == ""

    def test_short_content(self):
        """测试短内容."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        content = "这是一个短章节内容。"
        result = ChapterSummaryGenerator._extract_ending(content)
        assert "短章节内容" in result or len(result) <= 100

    def test_custom_length(self):
        """测试自定义长度."""
        from agents.chapter_summary_generator import ChapterSummaryGenerator

        content = "A" * 200 + "这是结尾。"
        result = ChapterSummaryGenerator._extract_ending(content, length=50)
        assert len(result) <= 60
