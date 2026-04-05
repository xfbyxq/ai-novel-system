"""
AI小说系统 - 小说创建功能测试

测试编号: E2E-01 (基础测试 - 无依赖)
测试目标: 测试创建新小说的完整流程

前置条件: 无
依赖测试: 无

作者: Qoder
生成时间: 2026-03-23T22:07:01.961220
"""

from datetime import datetime

import pytest
from playwright.sync_api import Page, expect


class Test小说创建:
    """小说创建功能测试类 (E2E-01)"""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, base_url: str):
        """每个测试前的准备工作"""
        self.page = page
        # 导航到目标页面
        page.goto(f"{base_url}/novels")
        page.wait_for_load_state("networkidle")


    @pytest.mark.e2e01
    @pytest.mark.smoke
    def test_novel_list_page_loads(self):
        """测试小说列表页面正常加载"""
        # 验证页面标题或关键元素
        expect(self.page.locator("body")).to_be_visible()
        # 验证"小说管理"标题存在
        expect(self.page.locator("h4:has-text('小说管理')")).to_be_visible()
        # 验证创建按钮存在 (Ant Design Button with text)
        expect(self.page.locator("button:has-text('创建小说')")).to_be_visible()

    @pytest.mark.e2e01
    def test_click_create_button(self):
        """测试点击创建小说按钮打开表单"""
        # 点击创建按钮
        self.page.locator("button:has-text('创建小说')").click()
        # 等待 Modal 出现
        expect(self.page.locator(".ant-modal")).to_be_visible()
        # 验证 Modal 标题
        expect(self.page.locator(".ant-modal-title")).to_contain_text("创建新小说")

    @pytest.mark.e2e01
    def test_fill_novel_form(self):
        """测试填写小说表单"""
        # 点击创建按钮打开表单
        self.page.locator("button:has-text('创建小说')").click()

        # 等待 Modal 打开
        expect(self.page.locator(".ant-modal")).to_be_visible()

        # 填写标题 (placeholder="例如：星辰大主宰")
        self.page.locator("input[placeholder*='星辰']").fill("测试小说_" + datetime.now().strftime("%Y%m%d%H%M%S"))

        # 选择类型 - 点击类型选择框
        self.page.locator(".ant-modal .ant-select").first.click()
        # 等待下拉菜单出现并选择第一项
        self.page.locator(".ant-select-dropdown .ant-select-item").first.click()

        # 填写简介 (placeholder包含"核心设定")
        self.page.locator("textarea[placeholder*='核心设定']").fill("这是自动化测试生成的小说简介")

    @pytest.mark.e2e01
    def test_submit_novel_form(self):
        """测试提交小说表单"""
        # 先填写表单
        self.test_fill_novel_form()

        # 点击 Modal 中的"创建"按钮 (Modal footer 中的主要按钮)
        self.page.locator(".ant-modal-footer button.ant-btn-primary").click()

        # 等待创建成功 - 会跳转到小说详情页 /novels/{id}
        self.page.wait_for_url("**/novels/**", timeout=10000)

    @pytest.mark.e2e01
    def test_novel_appears_in_list(self):
        """测试新创建的小说显示在列表中"""
        # 刷新页面回到列表
        self.page.goto(f"{self.page.url.split('#')[0]}#/novels" if '#' in self.page.url else self.page.url)
        self.page.wait_for_load_state("networkidle")

        # 验证小说出现在表格中
        expect(self.page.locator("table").locator("a:has-text('测试小说_')")).to_be_visible()
