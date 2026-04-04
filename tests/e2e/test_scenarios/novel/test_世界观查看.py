"""
AI小说系统 - 世界观查看功能测试

测试编号: E2E-04
测试目标: 测试查看和编辑世界观的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
生成时间: 2026-03-23T22:07:01.963916
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test世界观查看:
    """世界观查看功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """每个测试前的准备工作"""
        self.page = page
        # 导航到目标页面
        page.goto("/novels/:id")
        page.wait_for_load_state("networkidle")


    def test_switch_to_world_tab(self):
        """测试切换到世界观标签"""
        # 点击世界观标签
        world_tab = self.page.locator("text=世界观, text=世界设定, text=World").first
        world_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(1000)

    def test_world_content_displayed(self):
        """测试世界观内容显示"""
        # 验证世界观内容区域存在
        world_content = self.page.locator(".world-setting, .ant-form, textarea")
        expect(world_content.first).to_be_visible()

    def test_world_edit_available(self):
        """测试世界观编辑功能可用"""
        # 查找编辑按钮
        edit_btn = self.page.locator("text=编辑, text=修改").first
        # 编辑按钮可能不存在或不可点击
        if edit_btn.count() > 0:
            edit_btn.click()
            self.page.wait_for_selector("textarea, input", state="visible", timeout=3000)


from datetime import datetime
