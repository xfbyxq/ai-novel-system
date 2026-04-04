"""
AI小说系统 - 添加企划任务功能测试

测试编号: E2E-06
测试目标: 测试在小说详情页添加企划任务的功能

前置条件: 已存在测试小说
依赖测试: E2E-01 (小说创建)

作者: Qoder
生成时间: 2026-03-23T22:07:01.965138
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test添加企划任务:
    """添加企划任务功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """每个测试前的准备工作"""
        self.page = page
        # 导航到目标页面
        page.goto("/novels/:id")
        page.wait_for_load_state("networkidle")


    def test_overview_tab_visible(self):
        """测试概览标签可见"""
        # 确保在概览标签
        overview_tab = self.page.locator("text=概览, text=Overview").first
        overview_tab.click()
        self.page.wait_for_timeout(1000)

    def test_find_planning_task_entry(self):
        """测试找到企划任务入口"""
        # 查找企划任务相关按钮
        task_buttons = self.page.locator("text=企划, text=任务, text=添加任务")
        expect(task_buttons.first).to_be_visible()

    def test_click_add_planning_task(self):
        """测试点击添加企划任务按钮"""
        # 点击添加企划任务按钮
        add_btn = self.page.locator("text=添加企划, text=新建任务, .ant-btn-primary").first
        add_btn.click()

        # 等待弹窗出现
        self.page.wait_for_selector(".ant-modal", state="visible", timeout=5000)

    def test_fill_planning_task_form(self):
        """测试填写企划任务表单"""
        # 先打开表单
        self.test_click_add_planning_task()

        # 填写任务名称
        name_input = self.page.locator("input[name='name'], input[placeholder*='名称']").first
        name_input.fill("测试企划任务_" + datetime.now().strftime("%H%M%S"))

    def test_submit_planning_task(self):
        """测试提交企划任务"""
        # 填写表单
        self.test_fill_planning_task_form()

        # 点击提交按钮
        submit_btn = self.page.locator("button[type='submit'], text=确定, text=提交").last
        submit_btn.click()

        # 等待提交完成
        self.page.wait_for_timeout(2000)
