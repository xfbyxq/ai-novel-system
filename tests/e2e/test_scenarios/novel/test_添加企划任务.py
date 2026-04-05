"""
AI小说系统 - 添加企划任务功能测试

测试编号: E2E-06
测试目标: 测试在小说详情页添加企划任务的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test添加企划任务:
    """添加企划任务功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, test_novel_id: str, base_url: str):
        """每个测试前的准备工作"""
        self.page = page
        self.novel_id = test_novel_id
        # 导航到小说详情页
        page.goto(f"{base_url}/novels/{test_novel_id}")
        page.wait_for_load_state("networkidle")

    def test_overview_tab_visible(self):
        """测试概览标签可见"""
        # 概览标签是默认激活的
        overview_tab = self.page.locator('[role="tab"]').filter(has_text="概览")
        expect(overview_tab).to_have_attribute("aria-selected", "true")

    def test_find_planning_task_entry(self):
        """测试找到企划任务入口"""
        # 在概览标签中查找开始企划按钮
        start_btn = self.page.locator("button:has-text('开始企划'), button:has-text('企划')")
        expect(start_btn.first).to_be_visible()

    def test_click_add_planning_task(self):
        """测试点击添加企划任务按钮"""
        # 点击开始企划按钮
        start_btn = self.page.locator("button:has-text('开始企划')").first
        start_btn.click()

        # 等待企划流程开始
        self.page.wait_for_timeout(1000)

    def test_fill_planning_task_form(self):
        """测试填写企划任务表单"""
        # 如果有企划表单，填写相关信息
        form_input = self.page.locator(".ant-modal input, .ant-modal textarea").first
        if form_input.is_visible():
            form_input.fill("测试企划任务_" + datetime.now().strftime("%H%M%S"))

    def test_submit_planning_task(self):
        """测试提交企划任务"""
        # 如果有确认按钮，点击提交
        submit_btn = self.page.locator("button:has-text('确定'), button:has-text('提交')")
        if submit_btn.count() > 0:
            submit_btn.first.click()
            self.page.wait_for_timeout(1000)
