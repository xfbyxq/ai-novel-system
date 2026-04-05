"""TokenCalculator 单元测试"""
import pytest
from llm.token_calculator import TokenCalculator


class TestTokenCalculator:
    """TokenCalculator 测试"""

    def setup_method(self):
        self.calc = TokenCalculator()

    # --- count_tokens 测试 ---

    def test_count_tokens_empty(self):
        """空文本返回 0"""
        assert self.calc.count_tokens("") == 0
        assert self.calc.count_tokens(None) == 0  # 支持 None

    def test_count_tokens_chinese(self):
        """中文文本 token 计数"""
        result = self.calc.count_tokens("测试文本")
        assert result > 0
        assert isinstance(result, int)

    def test_count_tokens_english(self):
        """英文文本 token 计数"""
        result = self.calc.count_tokens("hello world")
        assert result > 0

    def test_count_tokens_mixed(self):
        """中英混合文本"""
        result = self.calc.count_tokens("你好 hello 世界 world")
        assert result > 0

    def test_count_tokens_long_text(self):
        """长文本 token 计数"""
        long_text = "这是一段测试文本。" * 1000
        result = self.calc.count_tokens(long_text)
        assert result > 100

    # --- calculate_max_tokens 测试 ---

    def test_calculate_normal_input(self):
        """正常输入：动态计算的 max_tokens 在合理范围内"""
        result = self.calc.calculate_max_tokens(
            prompt="请分析这段文本",
            system="你是一个助手",
            context_window=196608,
            min_output=1024,
            max_output=16384,
        )
        # 输入很短，应该返回 max_output
        assert result == 16384

    def test_calculate_large_input(self):
        """大输入：接近窗口限制时输出空间被压缩"""
        # 构造一个很大的输入
        large_prompt = "测试" * 50000  # 约 50000+ tokens
        result = self.calc.calculate_max_tokens(
            prompt=large_prompt,
            system="",
            context_window=196608,
            min_output=1024,
            max_output=16384,
        )
        # 应该小于 max_output（因为输入占了大量空间）
        assert result <= 16384
        assert result >= 1024

    def test_calculate_exceeds_window(self):
        """输入超过窗口大小时返回 min_output"""
        # 使用较小的 context_window 进行快速测试
        # 10000 个字符约产生 6000-8000 tokens，超过设置的 context_window=5000
        huge_prompt = "测试" * 10000
        result = self.calc.calculate_max_tokens(
            prompt=huge_prompt,
            system="",
            context_window=5000,  # 较小的窗口
            min_output=1024,
            max_output=16384,
        )
        # 即使可用空间为负数，也应返回 min_output
        assert result == 1024

    def test_calculate_min_output_respected(self):
        """min_output 限制被尊重"""
        result = self.calc.calculate_max_tokens(
            prompt="短文本",
            system="",
            context_window=196608,
            min_output=2048,
            max_output=16384,
        )
        assert result >= 2048

    def test_calculate_max_output_respected(self):
        """max_output 限制被尊重"""
        result = self.calc.calculate_max_tokens(
            prompt="短文本",
            system="",
            context_window=196608,
            min_output=1024,
            max_output=8192,
        )
        assert result <= 8192

    def test_calculate_with_system_prompt(self):
        """system prompt 也参与计算"""
        result_no_sys = self.calc.calculate_max_tokens(
            prompt="测试",
            system="",
            context_window=200000,
        )
        result_with_sys = self.calc.calculate_max_tokens(
            prompt="测试",
            system="你是一个非常专业的助手" * 100,
            context_window=200000,
        )
        # 有 system prompt 时可用空间应该更小或相等
        assert result_with_sys <= result_no_sys
