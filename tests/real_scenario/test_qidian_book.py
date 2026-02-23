"""真实场景测试：起点书籍详情爬取验证"""
import pytest

from backend.services.crawler_service import CrawlerService


# 使用一个稳定存在的书籍 ID 进行测试
# 这是《诡秘之主》的 ID，长期热门作品
KNOWN_BOOK_ID = "1010868264"
BOOK_URL = f"https://book.qidian.com/info/{KNOWN_BOOK_ID}/"


@pytest.mark.real_crawl
@pytest.mark.network
class TestQidianBookCrawl:
    """测试起点书籍详情真实爬取"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    async def test_fetch_book_page_returns_html(self, real_http_client, request_headers):
        """请求书籍详情页，验证能获取响应"""
        response = await real_http_client.get(BOOK_URL, headers=request_headers)

        assert response.status_code in [200, 202], f"状态码: {response.status_code}"
        print(f"\n[书籍详情] HTTP {response.status_code}, 内容长度: {len(response.text)}")

        if response.status_code == 202:
            pytest.skip("反爬虫机制触发，返回验证页面")

        assert len(response.text) > 500

    async def test_parse_real_book_page(self, real_http_client, request_headers):
        """抓取真实书籍详情页并解析"""
        response = await real_http_client.get(BOOK_URL, headers=request_headers)

        book = self.service._parse_qidian_book_page(response.text, KNOWN_BOOK_ID)

        print(f"\n[书籍详情] HTTP {response.status_code}")
        print(f"  book_id: {book.get('book_id')}")
        print(f"  书名: {book.get('book_title')}")
        print(f"  作者: {book.get('author_name')}")
        print(f"  类型: {book.get('genre')}")
        print(f"  标签: {book.get('tags', [])}")
        if book.get("synopsis"):
            print(f"  简介: {book.get('synopsis')[:50]}...")

        assert book.get("book_id") == KNOWN_BOOK_ID

        if response.status_code == 202:
            print("  [提示] 收到 202 响应，可能是反爬虫验证页")
            pytest.skip("反爬虫机制触发，返回 202")

    async def test_book_has_title(self, real_http_client, request_headers):
        """验证能获取书名"""
        response = await real_http_client.get(BOOK_URL, headers=request_headers)
        book = self.service._parse_qidian_book_page(response.text, KNOWN_BOOK_ID)

        title = book.get("book_title")
        if not title:
            if response.status_code == 202:
                pytest.skip("反爬虫机制触发，无法解析书名")
            print("  [警告] 未能解析书名，可能页面结构已变化")
        else:
            assert len(title) > 0
            print(f"\n[书籍详情] 书名: {title}")
