"""测试 CrawlerService._parse_word_count 方法"""
import pytest

from backend.services.crawler_service import CrawlerService


@pytest.mark.unit
class TestParseWordCount:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    def test_wan_unit(self):
        """'100万字' -> 1000000"""
        assert self.service._parse_word_count("100万字") == 1000000

    def test_wan_decimal(self):
        """'50.5万字' -> 505000"""
        assert self.service._parse_word_count("50.5万字") == 505000

    def test_wan_small(self):
        """'1.2万字' -> 12000"""
        assert self.service._parse_word_count("1.2万字") == 12000

    def test_direct_number_with_suffix(self):
        """'123456字' -> 123456"""
        assert self.service._parse_word_count("123456字") == 123456

    def test_plain_number(self):
        """'320000' -> 320000"""
        assert self.service._parse_word_count("320000") == 320000

    def test_invalid_returns_zero(self):
        """无法解析的文本返回 0"""
        assert self.service._parse_word_count("未知") == 0

    def test_empty_string_returns_zero(self):
        """空字符串返回 0"""
        assert self.service._parse_word_count("") == 0

    def test_alphabetic_returns_zero(self):
        """纯字母返回 0"""
        assert self.service._parse_word_count("abc") == 0

    def test_whitespace_only(self):
        """纯空白返回 0"""
        assert self.service._parse_word_count("   ") == 0

    def test_wan_without_zi_suffix(self):
        """'80.5万' (无'字'后缀) -> 805000"""
        assert self.service._parse_word_count("80.5万") == 805000
