"""小说列表页面对象 - 稳定版."""

from typing import List, Optional
from .base_page import BasePage


class NovelListPage(BasePage):
    """小说列表页面对象."""

    URL = "/novels"

    # 页面元素选择器 - 稳定可靠的选择器
    SELECTORS = {
        # 主要按钮
        "create_button": "button:has-text('创建小说')",
        # 刷新功能通过页面重新加载实现，无需单独按钮
        # 小说卡片 - 使用表格行
        "novel_cards": ".ant-table-tbody tr",
        "novel_card_title": ".ant-table-tbody td a",
        "novel_card_status": ".ant-table-tbody td:nth-child(3)",
        "novel_card_word_count": ".ant-table-tbody td:nth-child(4)",
        # 创建小说表单 - 稳定的选择器
        "create_modal": ".ant-modal:has-text('创建新小说')",
        "title_input": ".ant-modal input[placeholder*='例如：星辰大主宰']",
        "genre_select": ".ant-modal .ant-select",
        "tags_input": ".ant-modal .ant-form-item:has(label:text('标签')) .ant-select",
        "synopsis_textarea": ".ant-modal textarea[placeholder*='简要描述']",
        "length_type_select": ".ant-modal .ant-select:last-child",
        "submit_button": ".ant-modal .ant-btn-primary",
        "cancel_button": ".ant-modal .ant-btn:not(.ant-btn-primary)",
        # 消息提示
        "success_message": ".ant-message-success",
        "error_message": ".ant-message-error",
        "loading_spinner": ".ant-spin-spinning",
        # 筛选和排序
        "status_filter": "[data-testid='status-filter']",
        "sort_select": "[data-testid='sort-select']",
        # 分页
        "pagination": "[data-testid='pagination']",
        "next_page_button": "[data-testid='next-page-btn']",
        "prev_page_button": "[data-testid='prev-page-btn']",
    }

    def navigate(self):
        """导航到小说列表页面."""
        full_url = f"{self.page.base_url}{self.URL}"
        self.page.goto(full_url)
        self.wait_for_load()

    def click_create_button(self):
        """点击创建小说按钮."""
        self.click_element(self.SELECTORS["create_button"])
        # 等待模态框出现
        self.wait_for_element_visible(self.SELECTORS["create_modal"])

    def fill_create_form(
        self,
        title: str,
        genre: str,
        tags: Optional[List[str]] = None,
        synopsis: Optional[str] = None,
        length_type: Optional[str] = None,
    ):
        """
        填写创建小说表单.

        Args:
            title: 小说标题
            genre: 小说类型
            tags: 标签列表
            synopsis: 简介
            length_type: 篇幅类型
        """
        # 填写标题
        self.fill_input(self.SELECTORS["title_input"], title)

        # 选择类型
        genre_select = self.get_element(self.SELECTORS["genre_select"]).nth(0)
        genre_select.click()
        self.page.wait_for_timeout(1000)  # 等待下拉动画
        # 选择匹配的选项
        option = self.page.locator(
            f".ant-select-dropdown .ant-select-item:has-text('{genre}')"
        )
        if option.count() > 0:
            option.first.click()
        else:
            # 如果找不到精确匹配，选择第一个选项
            self.page.locator(".ant-select-dropdown .ant-select-item").first.click()

        # 填写标签
        if tags:
            # 点击标签输入框
            tags_select = self.get_element(self.SELECTORS["tags_input"])
            tags_select.click()
            # 填写每个标签
            for tag in tags:
                self.page.keyboard.type(tag)
                self.page.keyboard.press("Enter")

        # 填写简介
        if synopsis:
            self.fill_input(self.SELECTORS["synopsis_textarea"], synopsis)

        # 选择篇幅类型
        if length_type:
            length_select = self.get_element(self.SELECTORS["length_type_select"]).nth(
                0
            )
            length_select.click()
            self.page.wait_for_timeout(1000)
            # 映射篇幅类型到选项文本
            length_mapping = {
                "短文": "短文",
                "中篇": "中篇小说",
                "长篇": "长篇小说",
                "short": "短文",
                "medium": "中篇小说",
                "long": "长篇小说",
            }
            option_text = length_mapping.get(length_type, length_type)
            option = self.page.locator(
                f".ant-select-dropdown .ant-select-item:has-text('{option_text}')"
            )
            if option.count() > 0:
                option.first.click()
            else:
                self.page.locator(".ant-select-dropdown .ant-select-item").first.click()

    def submit_create_form(self):
        """提交创建小说表单."""
        # 确保所有下拉选项都已关闭
        self.page.wait_for_timeout(1000)
        self.click_element(self.SELECTORS["submit_button"])
        # 等待模态框关闭或成功消息出现
        try:
            self.wait_for_element_hidden(self.SELECTORS["create_modal"], timeout=15000)
        except:
            # 模态框可能已经关闭，检查成功消息
            self.page.wait_for_timeout(2000)

    def cancel_create_form(self):
        """取消创建小说表单."""
        self.click_element(self.SELECTORS["cancel_button"])
        self.wait_for_element_hidden(self.SELECTORS["create_modal"])

    def create_novel(
        self,
        title: str,
        genre: str,
        tags: Optional[List[str]] = None,
        synopsis: Optional[str] = None,
        length_type: Optional[str] = None,
    ):
        """
        完整的小说创建流程.

        Args:
            title: 小说标题
            genre: 小说类型
            tags: 标签列表
            synopsis: 简介
            length_type: 篇幅类型
        """
        self.click_create_button()
        self.fill_create_form(title, genre, tags, synopsis, length_type)
        self.submit_create_form()

    def get_novel_count(self) -> int:
        """
        获取小说总数（从分页组件读取）.

        Returns:
            int: 小说总数
        """
        # 读取分页组件中的总数文本 "共 X 部"
        pagination_elem = self.page.locator(".ant-pagination-total-text")
        if pagination_elem.count() > 0:
            pagination_text = pagination_elem.text_content()
            if pagination_text:
                import re
                match = re.search(r"共\s*(\d+)", pagination_text)
                if match:
                    return int(match.group(1))
        # 回退：如果找不到分页总数，返回可见行数
        return self.get_element_count(self.SELECTORS["novel_cards"])

    def get_novel_titles(self) -> List[str]:
        """
        获取所有小说标题.

        Returns:
            list: 小说标题列表
        """
        titles = []
        title_elements = self.get_element(self.SELECTORS["novel_card_title"]).all()
        for element in title_elements:
            titles.append(element.text_content() or "")
        return titles

    def get_novel_statuses(self) -> List[str]:
        """
        获取所有小说状态.

        Returns:
            list: 小说状态列表
        """
        statuses = []
        status_elements = self.get_element(self.SELECTORS["novel_card_status"]).all()
        for element in status_elements:
            statuses.append(element.text_content() or "")
        return statuses

    def is_success_message_visible(self) -> bool:
        """
        检查成功消息是否可见.

        Returns:
            bool: 成功消息是否可见
        """
        return self.is_element_visible(self.SELECTORS["success_message"])

    def is_error_message_visible(self) -> bool:
        """
        检查错误消息是否可见.

        Returns:
            bool: 错误消息是否可见
        """
        return self.is_element_visible(self.SELECTORS["error_message"])

    def get_error_messages(self) -> List[str]:
        """
        获取所有错误消息.

        Returns:
            list: 错误消息列表
        """
        messages = []
        error_elements = self.get_element(self.SELECTORS["error_message"]).all()
        for element in error_elements:
            messages.append(element.text_content() or "")
        return messages

    def click_novel_card(self, index: int = 0):
        """
        点击小说卡片.

        Args:
            index: 小说卡片索引
        """
        # 点击小说标题链接而不是整行，因为前端只有标题是可点击的
        title_links = self.get_element(self.SELECTORS["novel_card_title"]).all()
        if index < len(title_links):
            title_links[index].click()

    def click_novel_by_title(self, title: str):
        """
        点击指定标题的小说.

        Args:
            title: 小说标题
        """
        title_link = self.page.locator(f"a:has-text('{title}')")
        title_link.first.click()

    def filter_by_status(self, status: str):
        """
        按状态筛选小说.

        Args:
            status: 状态值
        """
        self.select_option(self.SELECTORS["status_filter"], status)

    def sort_by(self, sort_option: str):
        """
        按指定方式排序.

        Args:
            sort_option: 排序选项
        """
        self.select_option(self.SELECTORS["sort_select"], sort_option)

    def go_to_next_page(self):
        """跳转到下一页."""
        if self.is_element_enabled(self.SELECTORS["next_page_button"]):
            self.click_element(self.SELECTORS["next_page_button"])

    def go_to_prev_page(self):
        """跳转到上一页."""
        if self.is_element_enabled(self.SELECTORS["prev_page_button"]):
            self.click_element(self.SELECTORS["prev_page_button"])

    def is_create_modal_open(self) -> bool:
        """
        检查创建模态框是否打开.

        Returns:
            bool: 模态框是否打开
        """
        return self.is_element_visible(self.SELECTORS["create_modal"])

    def wait_for_novels_loaded(self, timeout: int = 10000):
        """
        等待小说列表加载完成.

        Args:
            timeout: 超时时间(毫秒)
        """
        # 使用 first 避免 strict mode violation（多行匹配）
        self.page.locator(self.SELECTORS["novel_cards"]).first.wait_for(state="visible", timeout=timeout)

    def refresh_novels(self):
        """刷新小说列表 - 通过页面重新加载实现."""
        self.page.reload()
        self.wait_for_novels_loaded()
