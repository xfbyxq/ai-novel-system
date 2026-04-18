"""修订功能测试页面对象."""

from tests.e2e.pages.base_page import BasePage


class RevisionPage(BasePage):
    """修订功能测试页面对象."""

    # AI对话选择器（实际是 Drawer 组件，不是 Tab）
    CHAT_TAB_SELECTORS = {
        "chat_tab": "button:has-text('AI 助手')",  # 实际是按钮，不是标签页
        "chat_drawer": ".ant-drawer-content:has-text('AI 助手')",
        "chat_input": "textarea[placeholder*='输入你的问题']",
        "send_btn": "button:has-text('发送')",
        "chat_messages": ".ant-comment-content, .chat-message",
        "revision_plan_modal": ".ant-modal:has-text('修订计划')",
    }

    # 修订计划模态框选择器
    REVISION_PLAN_SELECTORS = {
        "understood_intent": ".revision-intent, [class*='intent']",
        "confidence_badge": ".ant-tag, .confidence-badge",
        "target_list": ".revision-targets, .target-list",
        "change_preview": ".change-preview, .proposed-changes",
        "impact_assessment": ".impact-assessment, .impact-info",
        "confirm_btn": "button:has-text('确认执行'), .ant-btn-primary",
        "cancel_btn": "button:has-text('取消'), .ant-btn-default",
        "modify_btn": "button:has-text('修改'), .ant-btn",
    }

    # 章节详情页选择器
    CHAPTER_SELECTORS = {
        "chapter_content": ".chapter-content, .ant-typography, article",
        "revision_btn": "button:has-text('修订'), button:has-text('反馈')",
    }

    def navigate_to_chat(self, novel_id: str):
        """
        导航到小说详情页并打开AI对话Drawer.

        Args:
            novel_id: 小说ID
        """
        url = f"{self.page.base_url}/novels/{novel_id}"
        self.page.goto(url)
        self.wait_for_load()
        self.page.wait_for_timeout(500)
        # 点击AI助手按钮打开Drawer
        self.click_element(self.CHAT_TAB_SELECTORS["chat_tab"])
        # 等待Drawer出现（使用更宽松的selector）
        self.page.wait_for_timeout(2000)

    def send_revision_feedback(self, feedback: str):
        """
        发送修订反馈.

        Args:
            feedback: 反馈文本
        """
        # 等待输入框可用（AI可能在streaming）
        chat_input = self.page.locator(self.CHAT_TAB_SELECTORS["chat_input"])
        chat_input.first.wait_for(state="attached", timeout=10000)
        chat_input.first.wait_for(state="visible", timeout=10000)

        # 输入反馈
        chat_input.first.fill(feedback)

        # 点击发送
        self.click_element(self.CHAT_TAB_SELECTORS["send_btn"])

        # 等待AI响应（等待streaming结束）
        self.page.wait_for_timeout(3000)

    def wait_for_revision_plan(self, timeout: int = 30000):
        """
        等待修订计划出现.

        Args:
            timeout: 超时时间(毫秒)
        """
        self.wait_for_element_visible(
            self.CHAT_TAB_SELECTORS["revision_plan_modal"], timeout=timeout
        )

    def get_revision_intent(self) -> str:
        """
        获取理解后的修订意图.

        Returns:
            str: 修订意图文本
        """
        intent_elem = self.get_element(self.REVISION_PLAN_SELECTORS["understood_intent"])
        return intent_elem.text_content() or ""

    def get_confidence(self) -> float:
        """
        获取置信度.

        Returns:
            float: 置信度值
        """
        badge = self.get_element(self.REVISION_PLAN_SELECTORS["confidence_badge"])
        text = badge.text_content() or "0"
        try:
            # 提取数字
            import re
            match = re.search(r"(\d+\.?\d*)", text)
            return float(match.group(1)) if match else 0.0
        except ValueError:
            return 0.0

    def get_targets(self) -> list:
        """
        获取修订目标列表.

        Returns:
            list: 修订目标列表
        """
        targets = []
        target_elements = self.page.locator(
            f"{self.REVISION_PLAN_SELECTORS['target_list']} li, "
            f"{self.REVISION_PLAN_SELECTORS['target_list']} .ant-list-item"
        ).all()
        for elem in target_elements:
            targets.append(elem.text_content() or "")
        return targets

    def get_proposed_changes(self) -> list:
        """
        获取提议的修改列表.

        Returns:
            list: 修改列表
        """
        changes = []
        change_elements = self.page.locator(
            f"{self.REVISION_PLAN_SELECTORS['change_preview']} tr, "
            f"{self.REVISION_PLAN_SELECTORS['change_preview']} .change-item"
        ).all()
        for elem in change_elements:
            changes.append(elem.text_content() or "")
        return changes

    def confirm_revision(self):
        """确认执行修订."""
        self.click_element(self.REVISION_PLAN_SELECTORS["confirm_btn"])
        self.wait_for_element_hidden(self.CHAT_TAB_SELECTORS["revision_plan_modal"])

    def cancel_revision(self):
        """取消修订."""
        self.click_element(self.REVISION_PLAN_SELECTORS["cancel_btn"])
        self.wait_for_element_hidden(self.CHAT_TAB_SELECTORS["revision_plan_modal"])

    def navigate_to_chapter(self, novel_id: str, chapter_id: str):
        """
        导航到章节详情页.

        Args:
            novel_id: 小说ID
            chapter_id: 章节ID
        """
        url = f"{self.page.base_url}/novels/{novel_id}/chapters/{chapter_id}"
        self.page.goto(url)
        self.wait_for_load()

    def click_revision_from_chapter(self):
        """从章节详情页点击修订按钮."""
        self.click_element(self.CHAPTER_SELECTORS["revision_btn"])
        # 应该跳转到对话页面
        self.page.wait_for_timeout(1000)
