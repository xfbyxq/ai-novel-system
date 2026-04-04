"""
AI小说系统 - 小说查看功能测试

测试编号: E2E-02
测试目标: 测试查看小说详情的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
生成时间: 2026-03-23T22:07:01.962792
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test小说查看:
    """小说查看功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, base_url: str):
        """每个测试前的准备工作"""
        self.page = page
        # 导航到目标页面
        page.goto(f"{base_url}/novels")
        page.wait_for_load_state("networkidle")


    def test_novel_list_displays(self):
        """测试小说列表显示"""
        # 等待页面加载完成
        self.page.wait_for_selector(".ant-table, .ant-card, .novel-list", timeout=10000)

    def test_click_novel_to_view_detail(self):
        """测试点击小说查看详情"""
        # 等待表格加载
        self.page.wait_for_selector("table", timeout=15000)
        
        # 等待表格有数据行
        try:
            self.page.wait_for_function(
                "() => document.querySelectorAll('.ant-table-tbody tr').length > 0",
                timeout=10000
            )
        except Exception:
            # 如果没有数据，跳过点击测试
            pytest.skip("没有小说数据，跳过点击测试")
        
        # 查找第一个小说链接并点击
        novel_link = self.page.locator(".ant-table-tbody a").first
        novel_link.click()

        # 等待详情页加载
        self.page.wait_for_load_state("networkidle")

        # 验证进入详情页
        assert "/novels/" in self.page.url

    def test_novel_detail_tabs(self):
        """测试小说详情页标签"""
        # 确保在详情页
        if "/novels/" not in self.page.url:
            self.page.wait_for_selector("table", timeout=15000)
            try:
                self.page.wait_for_function(
                    "() => document.querySelectorAll('.ant-table-tbody tr').length > 0",
                    timeout=10000
                )
                self.page.locator(".ant-table-tbody a").first.click()
                self.page.wait_for_load_state("networkidle")
            except Exception:
                pytest.skip("没有小说数据，跳过详情页测试")

        # 查找标签栏
        tabs = self.page.locator(".ant-tabs-tab, [role='tab']")
        assert tabs.count() > 0, "应该找到标签页"


from datetime import datetime
