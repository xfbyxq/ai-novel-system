"""
AI小说系统 - 批量生成小说任务功能测试

测试编号: E2E-08
测试目标: 测试批量生成小说内容的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
生成时间: 2026-03-23T22:07:01.965351
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test批量生成小说任务:
    """批量生成小说任务功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """每个测试前的准备工作"""
        self.page = page
        # 导航到目标页面
        page.goto("/novels/:id")
        page.wait_for_load_state("networkidle")


    def test_switch_to_generation_tab(self):
        """测试切换到生成历史标签"""
        # 点击生成历史或相关标签
        gen_tab = self.page.locator("text=生成历史, text=生成, text=Generation").first
        gen_tab.click()

        # 等待标签内容加载
        self.page.wait_for_timeout(1000)

    def test_find_batch_generation_entry(self):
        """测试找到批量生成入口"""
        # 查找批量生成按钮
        batch_btn = self.page.locator("text=批量生成, text=批量, .ant-btn-primary")
        expect(batch_btn.first).to_be_visible()

    def test_click_batch_generation(self):
        """测试点击批量生成按钮"""
        # 点击批量生成按钮
        batch_btn = self.page.locator("text=批量生成").first
        batch_btn.click()

        # 等待弹窗出现
        self.page.wait_for_selector(".ant-modal", state="visible", timeout=5000)

    def test_configure_batch_generation(self):
        """测试配置批量生成参数"""
        # 打开批量生成界面
        self.test_click_batch_generation()

        # 填写章节数量
        num_input = self.page.locator("input[name='count'], input[name='chapterCount'], input[type='number']").first
        if num_input.count() > 0:
            num_input.fill("5")

    def test_submit_batch_generation(self):
        """测试提交批量生成任务"""
        # 配置参数
        self.test_configure_batch_generation()

        # 点击生成按钮
        gen_btn = self.page.locator("text=开始生成, text=生成, button[type='submit']").first
        gen_btn.click()

        # 等待任务提交
        self.page.wait_for_timeout(2000)


from datetime import datetime
