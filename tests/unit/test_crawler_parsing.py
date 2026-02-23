"""测试 CrawlerService 的 HTML 解析方法"""
import pytest

from backend.services.crawler_service import CrawlerService
from tests.fixtures.html_samples import (
    RANKING_PAGE_HTML,
    TAGS_PAGE_HTML,
    BOOK_DETAIL_HTML,
    GENRES_PAGE_HTML,
    EMPTY_PAGE_HTML,
    PARTIAL_DATA_HTML,
)


@pytest.mark.unit
class TestParseRankingPage:
    """测试 _parse_qidian_ranking_page 方法"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    def test_extracts_books(self):
        """验证能从样本 HTML 提取书籍列表"""
        books = self.service._parse_qidian_ranking_page(RANKING_PAGE_HTML)
        assert isinstance(books, list)
        assert len(books) == 3

    def test_book_has_required_fields(self):
        """验证每本书包含必要字段"""
        books = self.service._parse_qidian_ranking_page(RANKING_PAGE_HTML)
        first_book = books[0]

        assert first_book.get("book_title") == "星域求生：我能看见提示"
        assert first_book.get("book_id") == "1038710110"
        assert first_book.get("author_name") == "孤独的飞鸟"
        assert first_book.get("genre") == "科幻"
        assert "末世来临" in first_book.get("synopsis", "")
        assert first_book.get("word_count") == 1500000  # 150万
        assert first_book.get("tags") == ["末世", "星际", "系统"]

    def test_parses_word_count_variants(self):
        """验证不同字数格式的解析"""
        books = self.service._parse_qidian_ranking_page(RANKING_PAGE_HTML)

        # 150万字 -> 1500000
        assert books[0].get("word_count") == 1500000
        # 80.5万字 -> 805000
        assert books[1].get("word_count") == 805000
        # 320000字 -> 320000
        assert books[2].get("word_count") == 320000

    def test_empty_html_returns_empty_list(self):
        """空 HTML 返回空列表"""
        books = self.service._parse_qidian_ranking_page(EMPTY_PAGE_HTML)
        assert books == []

    def test_partial_data_still_parsed(self):
        """部分字段缺失的条目仍能解析（仅有标题）"""
        books = self.service._parse_qidian_ranking_page(PARTIAL_DATA_HTML)
        assert len(books) == 1
        assert books[0].get("book_title") == "只有标题的书"
        assert books[0].get("book_id") == "9999999999"
        # 缺失字段不会抛异常
        assert books[0].get("author_name") is None


@pytest.mark.unit
class TestParseTagsPage:
    """测试 _parse_qidian_tags_page 方法"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    def test_extracts_tags(self):
        """验证能提取标签"""
        tags = self.service._parse_qidian_tags_page(TAGS_PAGE_HTML)
        assert isinstance(tags, list)
        assert len(tags) > 0

    def test_tag_has_name_and_href(self):
        """每个标签有 name 和 href"""
        tags = self.service._parse_qidian_tags_page(TAGS_PAGE_HTML)
        for tag in tags:
            assert "name" in tag
            assert tag["name"]  # 非空
            assert "href" in tag

    def test_empty_page_returns_empty_list(self):
        """空页面返回空列表"""
        tags = self.service._parse_qidian_tags_page(EMPTY_PAGE_HTML)
        assert tags == []


@pytest.mark.unit
class TestParseBookPage:
    """测试 _parse_qidian_book_page 方法"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    def test_extracts_book_info(self):
        """验证能提取书籍详情"""
        book = self.service._parse_qidian_book_page(BOOK_DETAIL_HTML, "12345")
        assert book["book_id"] == "12345"
        assert book.get("book_title") == "测试之书：无尽征途"
        assert book.get("author_name") == "青衫墨客"
        assert "冒险与成长" in book.get("synopsis", "")
        assert "tags" in book
        assert len(book["tags"]) == 3


@pytest.mark.unit
class TestParseGenresPage:
    """测试 _parse_qidian_genres_page 方法"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    def test_extracts_genres(self):
        """验证能提取分类"""
        genres = self.service._parse_qidian_genres_page(GENRES_PAGE_HTML)
        assert isinstance(genres, list)
        assert len(genres) > 0

    def test_filters_out_all(self):
        """过滤掉 '全部' 和 '全部作品'"""
        genres = self.service._parse_qidian_genres_page(GENRES_PAGE_HTML)
        names = [g["name"] for g in genres]
        assert "全部" not in names
        assert "全部作品" not in names

    def test_genres_have_name_and_href(self):
        """每个分类有 name 和 href"""
        genres = self.service._parse_qidian_genres_page(GENRES_PAGE_HTML)
        for genre in genres:
            assert "name" in genre
            assert genre["name"]
            assert "href" in genre

    def test_empty_page_returns_empty_list(self):
        """空页面返回空列表"""
        genres = self.service._parse_qidian_genres_page(EMPTY_PAGE_HTML)
        assert genres == []
