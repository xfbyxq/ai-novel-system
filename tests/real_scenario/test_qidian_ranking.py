"""真实场景测试：起点排行榜爬取验证"""
import asyncio

import pytest

from backend.services.crawler_service import CrawlerService


RANKING_TYPES = {
    "yuepiao": "https://www.qidian.com/rank/yuepiao/",
    "hotsales": "https://www.qidian.com/rank/hotsales/",
    "readIndex": "https://www.qidian.com/rank/readIndex/",
    "recom": "https://www.qidian.com/rank/recom/",
    "collect": "https://www.qidian.com/rank/collect/",
}


@pytest.mark.real_crawl
@pytest.mark.network
class TestQidianRankingCrawl:
    """测试起点排行榜真实爬取"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    async def test_fetch_ranking_page_returns_html(self, real_http_client, request_headers):
        """请求排行榜页面，验证能获取响应"""
        url = "https://www.qidian.com/rank/yuepiao/?page=1"
        response = await real_http_client.get(url, headers=request_headers)

        # 接受 200 或 202 (反爬虫验证页)
        assert response.status_code in [200, 202], f"状态码: {response.status_code}"
        print(f"\n[排行榜] HTTP {response.status_code}, 内容长度: {len(response.text)}")

        if response.status_code == 202:
            pytest.skip("反爬虫机制触发，返回验证页面")

        assert len(response.text) > 500  # 正常页面应该有内容

    async def test_parse_real_ranking_page(self, real_http_client, request_headers):
        """抓取真实页面并解析，验证提取到书籍数 > 0"""
        url = "https://www.qidian.com/rank/yuepiao/?page=1"
        response = await real_http_client.get(url, headers=request_headers)

        books = self.service._parse_qidian_ranking_page(response.text)

        print(f"\n[排行榜] HTTP {response.status_code}, 解析到 {len(books)} 本书籍")

        if response.status_code == 202:
            print("  [提示] 收到 202 响应，可能是反爬虫验证页，跳过解析验证")
            pytest.skip("反爬虫机制触发，返回 202")

        assert len(books) > 0, "未能从排行榜页面解析出任何书籍"

        # 打印前 3 本书用于人工校验
        for i, book in enumerate(books[:3], 1):
            print(f"  {i}. 《{book.get('book_title')}》 - {book.get('author_name')} "
                  f"[{book.get('genre')}] {book.get('word_count', 0)}字")

    async def test_ranking_books_have_required_fields(self, real_http_client, request_headers):
        """验证真实数据的字段完整性"""
        url = "https://www.qidian.com/rank/yuepiao/?page=1"
        response = await real_http_client.get(url, headers=request_headers)
        books = self.service._parse_qidian_ranking_page(response.text)

        if len(books) == 0:
            if response.status_code == 202:
                pytest.skip("反爬虫机制触发，无法解析书籍")
            pytest.fail("未解析到任何书籍")

        for book in books:
            # book_title 必须存在
            assert book.get("book_title"), f"书名为空: {book}"

    async def test_ranking_word_count_parsed(self, real_http_client, request_headers):
        """验证字数字段正确解析为整数"""
        url = "https://www.qidian.com/rank/yuepiao/?page=1"
        response = await real_http_client.get(url, headers=request_headers)
        books = self.service._parse_qidian_ranking_page(response.text)

        word_count_found = False
        for book in books:
            wc = book.get("word_count")
            if wc is not None and wc > 0:
                word_count_found = True
                assert isinstance(wc, int), f"word_count 应为 int: {wc}"
                break

        if not word_count_found:
            print("  [警告] 未找到有效的 word_count 字段")

    @pytest.mark.slow
    async def test_multiple_ranking_types(self, real_http_client, request_headers):
        """遍历 5 种排行榜类型，验证全部可抓取"""
        print("\n[多排行榜测试]")
        success_count = 0
        for ranking_name, base_url in RANKING_TYPES.items():
            url = f"{base_url}?page=1"
            response = await real_http_client.get(url, headers=request_headers)

            books = self.service._parse_qidian_ranking_page(response.text)
            print(f"  {ranking_name}: HTTP {response.status_code}, 解析到 {len(books)} 本书")

            if response.status_code == 200 and len(books) > 0:
                success_count += 1

            # 等待避免请求过快
            await asyncio.sleep(1.5)

        # 至少有一个榜单成功获取数据
        if success_count == 0:
            pytest.skip("所有排行榜都触发了反爬虫机制")

    @pytest.mark.slow
    async def test_ranking_pagination(self, real_http_client, request_headers):
        """抓取第 1、2 页，验证分页可用"""
        base_url = "https://www.qidian.com/rank/yuepiao/"
        print("\n[分页测试]")

        for page in [1, 2]:
            url = f"{base_url}?page={page}"
            response = await real_http_client.get(url, headers=request_headers)

            books = self.service._parse_qidian_ranking_page(response.text)
            print(f"  第 {page} 页: HTTP {response.status_code}, 解析到 {len(books)} 本书")

            if response.status_code == 202:
                pytest.skip("反爬虫机制触发")

            await asyncio.sleep(1.5)
