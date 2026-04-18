"""JsonExtractor 单元测试.

测试各种 JSON 提取场景，包括：
- 纯 JSON
- Markdown 代码块（闭合/未闭合）
- 截断 JSON
- 混合文本中的 JSON
"""

import pytest

from agents.base.json_extractor import JsonExtractor


class TestJsonExtractorBasic:
    """基础 JSON 提取测试."""

    def test_extract_pure_json_object(self):
        """测试纯 JSON 对象."""
        text = '{"key": "value", "number": 42}'
        result = JsonExtractor.extract_json(text)
        assert result == {"key": "value", "number": 42}

    def test_extract_pure_json_array(self):
        """测试纯 JSON 数组."""
        text = "[1, 2, 3]"
        result = JsonExtractor.extract_json(text)
        assert result == [1, 2, 3]

    def test_extract_nested_json(self):
        """测试嵌套 JSON."""
        text = '{"outer": {"inner": {"deep": "value"}}}'
        result = JsonExtractor.extract_json(text)
        assert result["outer"]["inner"]["deep"] == "value"


class TestJsonExtractorMarkdownBlock:
    """Markdown 代码块测试."""

    def test_extract_json_block_with_language(self):
        """测试带语言标识的代码块."""
        text = '```json\n{"key": "value"}\n```'
        result = JsonExtractor.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_block_without_language(self):
        """测试不带语言标识的代码块."""
        text = '```\n{"key": "value"}\n```'
        result = JsonExtractor.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_block_with_surrounding_text(self):
        """测试代码块周围有文本."""
        text = '这是响应：\n```json\n{"key": "value"}\n```\n以上是结果。'
        result = JsonExtractor.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_unclosed_code_block_simple(self):
        """测试未闭合的代码块（简单情况）."""
        text = '```json\n{"key": "value"}'
        result = JsonExtractor.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_unclosed_code_block_nested(self):
        """测试未闭合的代码块（嵌套对象）."""
        text = '```json\n{"outer": {"inner": "value"}}'
        result = JsonExtractor.extract_json(text)
        assert result["outer"]["inner"] == "value"

    def test_extract_unclosed_code_block_with_array(self):
        """测试未闭合的代码块（包含数组）."""
        text = '```json\n{"items": [1, 2, 3]}'
        result = JsonExtractor.extract_json(text)
        assert result["items"] == [1, 2, 3]


class TestJsonExtractorQualityReport:
    """质量评估报告场景测试."""

    def test_extract_quality_report_unclosed(self):
        """测试未闭合代码块中的质量评估报告."""
        text = """```json
{
    "overall_score": 7.5,
    "dimension_scores": {
        "accuracy": 7.5,
        "vividness": 7,
        "pacing": 8,
        "setting_consistency": 7,
        "immersion": 8
    },
    "revision_suggestions": [
        {"issue": "节奏稍慢", "suggestion": "加快情节推进", "severity": "medium"}
    ],
    "summary": "整体质量良好"
}"""
        result = JsonExtractor.extract_json(text)
        assert result["overall_score"] == 7.5
        assert result["dimension_scores"]["setting_consistency"] == 7
        assert len(result["revision_suggestions"]) == 1

    def test_extract_quality_report_closed(self):
        """测试闭合代码块中的质量评估报告."""
        text = """```json
{
    "overall_score": 8.0,
    "dimension_scores": {
        "accuracy": 8,
        "vividness": 8
    },
    "summary": "优秀"
}
```"""
        result = JsonExtractor.extract_json(text)
        assert result["overall_score"] == 8.0
        assert result["dimension_scores"]["accuracy"] == 8

    def test_extract_quality_report_pure_json(self):
        """测试纯 JSON 格式的质量评估报告."""
        text = '{"overall_score": 6.5, "dimension_scores": {"accuracy": 7}, "summary": "一般"}'
        result = JsonExtractor.extract_json(text)
        assert result["overall_score"] == 6.5


class TestJsonExtractorTruncated:
    """截断 JSON 测试."""

    def test_extract_truncated_missing_brace(self):
        """测试缺少闭合括号的截断 JSON."""
        text = '{"key": "value", "nested": {"a": 1'
        result = JsonExtractor.extract_json(text)
        # 应该能修复并解析
        assert result["key"] == "value"
        assert result["nested"]["a"] == 1

    def test_extract_truncated_in_string(self):
        """测试字符串被截断的情况."""
        text = '{"message": "这是被截断的字符'
        result = JsonExtractor.extract_json(text)
        # 应该能修复并解析
        assert "message" in result


class TestJsonExtractorEdgeCases:
    """边界情况测试."""

    def test_empty_string_raises_with_no_default(self):
        """测试空字符串无默认值时抛出异常."""
        with pytest.raises(ValueError, match="输入文本为空"):
            JsonExtractor.extract_json("")

    def test_empty_string_with_default(self):
        """测试空字符串有默认值时返回默认值."""
        result = JsonExtractor.extract_json("", default={"default": True})
        assert result == {"default": True}

    def test_non_json_text_with_default(self):
        """测试非 JSON 文本有默认值时返回默认值."""
        result = JsonExtractor.extract_json("这是普通文本", default={"default": True})
        assert result == {"default": True}

    def test_json_with_special_characters(self):
        """测试包含特殊字符的 JSON."""
        text = '{"message": "Hello\\nWorld\\t!", "emoji": "🎉"}'
        result = JsonExtractor.extract_json(text)
        assert result["message"] == "Hello\nWorld\t!"
        assert result["emoji"] == "🎉"

    def test_json_with_trailing_comma(self):
        """测试包含尾部逗号的 JSON."""
        text = '{"key": "value", "number": 42,}'
        result = JsonExtractor.extract_json(text)
        assert result["key"] == "value"
        assert result["number"] == 42

    def test_json_with_comments(self):
        """测试包含注释的 JSON."""
        text = """{
    "key": "value", // 这是一个注释
    "number": 42
}"""
        result = JsonExtractor.extract_json(text)
        assert result["key"] == "value"
        assert result["number"] == 42


class TestJsonExtractorMethods:
    """测试不同的提取方法."""

    def test_extract_object_returns_dict(self):
        """测试 extract_object 返回字典."""
        text = '{"key": "value"}'
        result = JsonExtractor.extract_object(text)
        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_extract_object_with_array_wrapped(self):
        """测试 extract_object 将数组包装为字典."""
        text = '[{"key": "value"}]'
        result = JsonExtractor.extract_object(text)
        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_extract_array_returns_list(self):
        """测试 extract_array 返回列表."""
        text = "[1, 2, 3]"
        result = JsonExtractor.extract_array(text)
        assert isinstance(result, list)
        assert result == [1, 2, 3]

    def test_extract_array_with_object_wrapped(self):
        """测试 extract_array 将对象包装为列表."""
        text = '{"key": "value"}'
        result = JsonExtractor.extract_array(text)
        assert isinstance(result, list)
        assert result[0]["key"] == "value"

    def test_safe_extract_returns_empty_dict_on_failure(self):
        """测试 safe_extract 失败时返回空字典."""
        result = JsonExtractor.safe_extract("不是 JSON", context="测试")
        assert result == {}

    def test_safe_extract_returns_dict_on_success(self):
        """测试 safe_extract 成功时返回字典."""
        result = JsonExtractor.safe_extract('{"key": "value"}')
        assert result == {"key": "value"}
