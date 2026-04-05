"""
AI小说系统 - 小说章节查看功能测试

测试编号: E2E-05
测试目标: 测试查看和管理章节的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
"""

import pytest
from playwright.sync_api import Page, expect


class Test小说章节查看:
    """小说章节查看功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, test_novel_id: str, base_url: str):
        """每个测试前的准备工作"""
        self.page = page
        self.novel_id = test_novel_id
        # 导航到小说详情页
        page.goto(f"{base_url}/novels/{test_novel_id}")
        page.wait_for_load_state("networkidle")

    def test_switch_to_chapters_tab(self):
        """测试切换到章节标签"""
        # 点击章节标签 (Ant Design Tabs)
        chapter_tab = self.page.locator('[role="tab"]').filter(has_text="章节")
        chapter_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(500)

        # 验证标签已激活
        expect(chapter_tab).to_have_attribute("aria-selected", "true")

    def test_chapter_list_displays(self):
        """测试章节列表显示"""
        # 先切换到章节标签
        self.test_switch_to_chapters_tab()

        # 验证章节列表区域存在
        chapter_list = self.page.locator(".ant-tabs-content, .ant-table, .ant-empty")
        expect(chapter_list.first).to_be_visible()

    def test_click_chapter_to_view(self):
        """测试点击章节查看详情"""
        # 先切换到章节标签
        self.test_switch_to_chapters_tab()

        # 查找章节行（如果有章节的话）
        chapter_row = self.page.locator(".ant-table-tbody tr")
        if chapter_row.count() > 0:
            chapter_row.first.click()
            self.page.wait_for_timeout(500)
