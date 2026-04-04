"""
AI小说系统 - 小说创建功能测试

自动生成的E2E测试用例
测试目标: 测试创建新小说的完整流程

作者: Qoder
生成时间: 2026-03-23T22:07:01.961220
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test小说创建:
    """小说创建功能测试类"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page):
        """每个测试前的准备工作"""
        self.page = page
        # 导航到目标页面
        page.goto("/novels")
        page.wait_for_load_state("networkidle")


    def test_novel_list_page_loads(self):
        """测试小说列表页面正常加载"""
        # 验证页面标题或关键元素
        expect(self.page.locator("body")).to_be_visible()
        # 验证创建按钮存在
        create_btn = self.page.locator("text=创建小说, text=新建小说, .ant-btn-primary").first
        expect(create_btn).to_be_visible()

    def test_click_create_button(self):
        """测试点击创建小说按钮打开表单"""
        # 点击创建按钮
        self.page.locator("text=创建小说, text=新建小说").first.click()
        # 等待表单出现
        self.page.wait_for_selector(".ant-modal, form", state="visible", timeout=5000)

    def test_fill_novel_form(self):
        """测试填写小说表单"""
        # 点击创建按钮打开表单
        self.page.locator("text=创建小说, text=新建小说").first.click()

        # 填写标题
        title_input = self.page.locator("input[name='title'], input[placeholder*='标题']").first
        title_input.fill("测试小说_" + datetime.now().strftime("%Y%m%d%H%M%S"))

        # 填写简介
        desc_input = self.page.locator("textarea[name='description'], textarea[placeholder*='简介']").first
        desc_input.fill("这是自动化测试生成的小说简介")

    def test_submit_novel_form(self):
        """测试提交小说表单"""
        # 先填写表单
        self.test_fill_novel_form()

        # 点击提交按钮
        submit_btn = self.page.locator("button[type='submit'], text=确定, text=创建").last
        submit_btn.click()

        # 等待创建成功提示或页面刷新
        self.page.wait_for_timeout(2000)

    def test_novel_appears_in_list(self):
        """测试新创建的小说显示在列表中"""
        # 刷新页面
        self.page.reload()
        self.page.wait_for_load_state("networkidle")

        # 验证小说出现在列表中
        expect(self.page.locator("text=测试小说_")).to_be_visible()
