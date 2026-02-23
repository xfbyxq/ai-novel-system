"""真实场景测试：起点标签页爬取验证"""
import pytest

from backend.services.crawler_service import CrawlerService


TAGS_PAGE_URL = "https://www.qidian.com/all/"


@pytest.mark.real_crawl
@pytest.mark.network
class TestQidianTagsCrawl:
    """测试起点标签页真实爬取"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = CrawlerService(db=None)

    async def test_fetch_tags_page_returns_html(self, real_http_client, request_headers):
        """请求标签页面，验证能获取响应"""
        response = await real_http_client.get(TAGS_PAGE_URL, headers=request_headers)

        assert response.status_code in [200, 202], f"状态码: {response.status_code}"
        print(f"\n[标签页] HTTP {response.status_code}, 内容长度: {len(response.text)}")

        if response.status_code == 202:
            pytest.skip("反爬虫机制触发，返回验证页面")

        assert len(response.text) > 500

    async def test_parse_real_tags_page(self, real_http_client, request_headers):
        """抓取真实标签页并解析"""
        response = await real_http_client.get(TAGS_PAGE_URL, headers=request_headers)

        tags = self.service._parse_qidian_tags_page(response.text)

        print(f"\n[标签页] HTTP {response.status_code}, 解析到 {len(tags)} 个标签")

        if response.status_code == 202:
            print("  [提示] 收到 202 响应，可能是反爬虫验证页")
            pytest.skip("反爬虫机制触发，返回 202")

        assert len(tags) > 0, "未能从标签页解析出任何标签"

        # 打印前 10 个标签
        for i, tag in enumerate(tags[:10], 1):
            print(f"  {i}. {tag.get('name')}")

    async def test_tags_have_name_and_href(self, real_http_client, request_headers):
        """验证每个标签有 name 和 href"""
        response = await real_http_client.get(TAGS_PAGE_URL, headers=request_headers)
        tags = self.service._parse_qidian_tags_page(response.text)

        if len(tags) == 0:
            if response.status_code == 202:
                pytest.skip("反爬虫机制触发，无法解析标签")
            pytest.fail("未解析到任何标签")

        for tag in tags:
            assert "name" in tag and tag["name"], f"标签缺少 name: {tag}"
            assert "href" in tag, f"标签缺少 href: {tag}"
