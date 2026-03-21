"""基础页面对象模型"""

from typing import Optional, Union
from playwright.sync_api import Page, Locator, TimeoutError
import time


class BasePage:
    """页面对象模型基类"""

    def __init__(self, page: Page):
        """
        初始化页面对象

        Args:
            page: Playwright页面实例
        """
        self.page = page
        self.timeout = 10000  # 默认超时时间10秒

    def wait_for_load(self, timeout: int = 10000):
        """
        等待页面加载完成

        Args:
            timeout: 超时时间(毫秒)
        """
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except TimeoutError:
            # 如果networkidle超时，至少等待domcontentloaded
            self.page.wait_for_load_state("domcontentloaded", timeout=timeout)

    def get_element(self, selector: str) -> Locator:
        """
        获取元素定位器

        Args:
            selector: CSS选择器或data-testid选择器

        Returns:
            Locator对象
        """
        return self.page.locator(selector)

    def click_element(self, selector: str, timeout: int = None):
        """
        点击元素

        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.get_element(selector).click(timeout=timeout)

    def fill_input(self, selector: str, value: str, timeout: int = None):
        """
        填充输入框

        Args:
            selector: 输入框选择器
            value: 要填充的值
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.get_element(selector).fill(value, timeout=timeout)

    def select_option(self, selector: str, value: str, timeout: int = None):
        """
        选择下拉选项

        Args:
            selector: 下拉选择器
            value: 选项值
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.page.select_option(selector, value, timeout=timeout)

    def is_element_visible(self, selector: str, timeout: int = None) -> bool:
        """
        检查元素是否可见

        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)

        Returns:
            bool: 元素是否可见
        """
        timeout = timeout or 1000  # 短超时用于检查
        try:
            return self.get_element(selector).is_visible(timeout=timeout)
        except TimeoutError:
            return False

    def is_element_enabled(self, selector: str, timeout: int = None) -> bool:
        """
        检查元素是否启用

        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)

        Returns:
            bool: 元素是否启用
        """
        timeout = timeout or 1000
        try:
            return self.get_element(selector).is_enabled(timeout=timeout)
        except TimeoutError:
            return False

    def get_text(self, selector: str, timeout: int = None) -> str:
        """
        获取元素文本内容

        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)

        Returns:
            str: 元素文本内容
        """
        timeout = timeout or self.timeout
        return self.get_element(selector).text_content(timeout=timeout) or ""

    def get_input_value(self, selector: str, timeout: int = None) -> str:
        """
        获取输入框的值

        Args:
            selector: 输入框选择器
            timeout: 超时时间(毫秒)

        Returns:
            str: 输入框的值
        """
        timeout = timeout or self.timeout
        return self.get_element(selector).input_value(timeout=timeout)

    def wait_for_element_visible(self, selector: str, timeout: int = None):
        """
        等待元素变为可见

        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.get_element(selector).wait_for(state="visible", timeout=timeout)

    def wait_for_element_hidden(self, selector: str, timeout: int = None):
        """
        等待元素变为隐藏

        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.get_element(selector).wait_for(state="hidden", timeout=timeout)

    def wait_for_url(self, url_pattern: str, timeout: int = None):
        """
        等待URL匹配指定模式

        Args:
            url_pattern: URL模式(支持正则表达式)
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.page.wait_for_url(url_pattern, timeout=timeout)

    def get_element_count(self, selector: str) -> int:
        """
        获取匹配选择器的元素数量

        Args:
            selector: 元素选择器

        Returns:
            int: 元素数量
        """
        return self.get_element(selector).count()

    def scroll_to_element(self, selector: str):
        """
        滚动到指定元素

        Args:
            selector: 元素选择器
        """
        self.get_element(selector).scroll_into_view_if_needed()

    def hover_element(self, selector: str, timeout: int = None):
        """
        悬停在元素上

        Args:
            selector: 元素选择器
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.get_element(selector).hover(timeout=timeout)

    def press_key(self, selector: str, key: str, timeout: int = None):
        """
        在元素上按下按键

        Args:
            selector: 元素选择器
            key: 按键名称
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        self.get_element(selector).press(key, timeout=timeout)

    def clear_input(self, selector: str, timeout: int = None):
        """
        清空输入框内容

        Args:
            selector: 输入框选择器
            timeout: 超时时间(毫秒)
        """
        timeout = timeout or self.timeout
        # 全选然后删除
        self.get_element(selector).press("Control+A", timeout=timeout)
        self.get_element(selector).press("Delete", timeout=timeout)
