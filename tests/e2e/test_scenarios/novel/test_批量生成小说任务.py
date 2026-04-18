"""
AI小说系统 - 批量生成小说任务功能测试

测试编号: E2E-08
测试目标: 测试批量生成小说内容的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
"""

import pytest
from playwright.sync_api import Page, expect


class Test批量生成小说任务:
    """批量生成小说任务功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, test_novel_id: str, base_url: str):
        """每个测试前的准备工作"""
        self.page = page
        self.novel_id = test_novel_id
        # 导航到小说详情页
        page.goto(f"{base_url}/novels/{test_novel_id}")
        page.wait_for_load_state("networkidle")

    def test_switch_to_generation_tab(self):
        """测试切换到生成历史标签"""
        # 点击生成历史标签 (Ant Design Tabs)
        gen_tab = self.page.locator('[role="tab"]').filter(has_text="生成历史")
        gen_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(500)

        # 验证标签已激活
        expect(gen_tab).to_have_attribute("aria-selected", "true")

    def test_find_batch_generation_entry(self):
        """测试找到批量生成入口"""
        # 先切换到章节标签（批量生成按钮通常在章节标签下）
        chapter_tab = self.page.locator('[role="tab"]').filter(has_text="章节")
        chapter_tab.click()
        self.page.wait_for_timeout(500)

        # 查找批量生成按钮
        batch_btn = self.page.locator("button:has-text('批量生成')")
        expect(batch_btn.first).to_be_visible()

    def test_click_batch_generation(self):
        """测试点击批量生成按钮"""
        # 先切换到章节标签
        chapter_tab = self.page.locator('[role="tab"]').filter(has_text="章节")
        chapter_tab.click()
        self.page.wait_for_timeout(500)

        # 点击批量生成按钮
        batch_btn = self.page.locator("button:has-text('批量生成')").first
        batch_btn.click()

        # 等待弹窗出现
        self.page.wait_for_selector(".ant-modal", state="visible", timeout=5000)

    def test_configure_batch_generation(self):
        """测试配置批量生成参数"""
        # 先打开批量生成界面
        self.test_click_batch_generation()

        # 填写章节数量
        num_input = self.page.locator(".ant-modal input[type='number']").first
        if num_input.is_visible():
            num_input.fill("5")

    def test_submit_batch_generation(self):
        """测试提交批量生成任务"""
        # 先配置参数
        self.test_configure_batch_generation()

        # 点击弹窗中的确定按钮
        confirm_btn = self.page.locator(".ant-modal button.ant-btn-primary")
        confirm_btn.click()

        # 等待任务提交
        self.page.wait_for_timeout(1000)
