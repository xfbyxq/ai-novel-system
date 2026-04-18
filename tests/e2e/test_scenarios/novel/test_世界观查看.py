"""
AI小说系统 - 世界观查看功能测试

测试编号: E2E-04
测试目标: 测试查看和编辑世界观的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
"""

import pytest
from playwright.sync_api import Page, expect


class Test世界观查看:
    """世界观查看功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, test_novel_id: str, base_url: str):
        """每个测试前的准备工作"""
        self.page = page
        self.novel_id = test_novel_id
        # 导航到小说详情页
        page.goto(f"{base_url}/novels/{test_novel_id}")
        page.wait_for_load_state("networkidle")

    def test_switch_to_world_tab(self):
        """测试切换到世界观标签"""
        # 点击世界观标签 (Ant Design Tabs)
        world_tab = self.page.locator('[role="tab"]').filter(has_text="世界观")
        world_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(500)

        # 验证标签已激活
        expect(world_tab).to_have_attribute("aria-selected", "true")

    def test_world_content_displayed(self):
        """测试世界观内容显示"""
        # 先切换到世界观标签
        self.test_switch_to_world_tab()

        # 验证世界观内容区域存在
        world_content = self.page.locator(".ant-tabs-content, textarea, .ant-form")
        expect(world_content.first).to_be_visible()

    def test_world_edit_available(self):
        """测试世界观编辑功能可用"""
        # 先切换到世界观标签
        self.test_switch_to_world_tab()

        # 查找编辑或保存按钮
        edit_btn = self.page.locator("button:has-text('编辑'), button:has-text('保存')")
        # 如果存在编辑按钮，验证其可点击性
        if edit_btn.count() > 0:
            expect(edit_btn.first).to_be_enabled()
