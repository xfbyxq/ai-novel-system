"""真实场景测试：起点分类列表爬取验证"""
import pytest

from backend.services.crawler_service import CrawlerService


GENRES_PAGE_URL = "https://www.qidian.com/all/"


@pytest.mark.real_crawl
@pytest.mark.network
class TestQidianGenresCrawl:
    """测试起点分类列表真实爬取"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    async def test_fetch_genres_page_returns_html(self, real_http_client, request_headers):
        """请求分类页面，验证能获取响应"""
        response = await real_http_client.get(GENRES_PAGE_URL, headers=request_headers)

        assert response.status_code in [200, 202], f"状态码: {response.status_code}"
        print(f"\n[分类列表] HTTP {response.status_code}, 内容长度: {len(response.text)}")

        if response.status_code == 202:
            pytest.skip("反爬虫机制触发，返回验证页面")

        assert len(response.text) > 500

    async def test_parse_real_genres_page(self, real_http_client, request_headers):
        """抓取真实分类页并解析"""
        response = await real_http_client.get(GENRES_PAGE_URL, headers=request_headers)

        genres = self.service._parse_qidian_genres_page(response.text)

        print(f"\n[分类列表] HTTP {response.status_code}, 解析到 {len(genres)} 个分类")

        if response.status_code == 202:
            print("  [提示] 收到 202 响应，可能是反爬虫验证页")
            pytest.skip("反爬虫机制触发，返回 202")

        assert len(genres) > 0, "未能从分类页解析出任何分类"

        # 打印所有分类
        for i, genre in enumerate(genres, 1):
            print(f"  {i}. {genre.get('name')}")

    async def test_genres_exclude_all(self, real_http_client, request_headers):
        """验证过滤掉 '全部' 和 '全部作品'"""
        response = await real_http_client.get(GENRES_PAGE_URL, headers=request_headers)
        genres = self.service._parse_qidian_genres_page(response.text)

        names = [g.get("name", "") for g in genres]
        assert "全部" not in names, "分类中不应包含 '全部'"
        assert "全部作品" not in names, "分类中不应包含 '全部作品'"

    async def test_genres_have_name_and_href(self, real_http_client, request_headers):
        """验证每个分类有 name 和 href"""
        response = await real_http_client.get(GENRES_PAGE_URL, headers=request_headers)
        genres = self.service._parse_qidian_genres_page(response.text)

        if len(genres) == 0:
            if response.status_code == 202:
                pytest.skip("反爬虫机制触发，无法解析分类")
            pytest.fail("未解析到任何分类")

        for genre in genres:
            assert "name" in genre and genre["name"], f"分类缺少 name: {genre}"
            assert "href" in genre, f"分类缺少 href: {genre}"
