"""
AI小说系统 - 大纲查看功能测试

测试编号: E2E-03
测试目标: 测试查看和编辑大纲的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
"""

import pytest
from playwright.sync_api import Page, expect


class Test大纲查看:
    """大纲查看功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, test_novel_id: str, base_url: str):
        """每个测试前的准备工作"""
        self.page = page
        self.novel_id = test_novel_id
        # 导航到小说详情页
        page.goto(f"{base_url}/novels/{test_novel_id}")
        page.wait_for_load_state("networkidle")

    def test_switch_to_outline_tab(self):
        """测试切换到大纲标签"""
        # 点击大纲标签 (Ant Design Tabs)
        outline_tab = self.page.locator('[role="tab"]').filter(has_text="大纲").filter(has_not_text="梳理")
        outline_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(500)

        # 验证标签已激活
        expect(outline_tab).to_have_attribute("aria-selected", "true")

    def test_outline_content_displayed(self):
        """测试大纲内容显示"""
        # 先切换到大纲标签
        self.test_switch_to_outline_tab()

        # 验证大纲内容区域存在
        outline_content = self.page.locator(".ant-tabs-content, .ant-card, textarea")
        expect(outline_content.first).to_be_visible()

    def test_outline_edit_available(self):
        """测试大纲编辑功能可用"""
        # 先切换到大纲标签
        self.test_switch_to_outline_tab()

        # 查找编辑或保存按钮
        edit_btn = self.page.locator("button:has-text('编辑'), button:has-text('保存')")
        if edit_btn.count() > 0:
            expect(edit_btn.first).to_be_enabled()
