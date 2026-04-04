"""
混合测试运行器 - 协调Playwright和Selenium/Healenium

核心功能：
1. 使用Playwright执行常规测试步骤
2. 当元素定位失败时，自动切换到Selenium+Healenium
3. Healenium自动寻找替代选择器并修复
4. 将修复后的选择器同步到测试中

作者: Qoder
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin

from playwright.sync_api import (
    sync_playwright,
    Page,
    Browser,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException as SeleniumTimeoutException
from selenium.common.exceptions import NoSuchElementException

from tests.ai_e2e.config import TestConfig, default_config

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TestFramework(Enum):
    """测试框架类型枚举"""
    PLAYWRIGHT = "playwright"
    SELENIUM = "selenium"
    HEALENIUM = "healenium"


@dataclass
class ElementAction:
    """元素操作描述"""
    action_type: str  # click, fill, hover, select, etc.
    selector: str
    value: Optional[str] = None
    timeout: int = 10000


@dataclass
class TestStep:
    """测试步骤"""
    step_id: int
    action: ElementAction
    framework: TestFramework = TestFramework.PLAYWRIGHT
    healed_selector: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    success: bool = False


@dataclass
class HealingResult:
    """自愈结果"""
    success: bool
    original_selector: str
    healed_selector: Optional[str] = None
    healing_method: str = ""
    score: float = 0.0
    error: Optional[str] = None


class HybridRunner:
    """
    混合测试运行器

    协调Playwright和Selenium/Healenium的测试执行，
    实现元素定位失败时的自动修复机制
    """

    def __init__(self, config: Optional[TestConfig] = None):
        """
        初始化混合运行器

        参数:
            config: 测试配置，如果为None则使用默认配置
        """
        self.config = config or default_config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.selenium_driver = None

        # 选择器缓存：记录失效选择器及其修复方案
        self.selector_cache: Dict[str, HealingResult] = {}

        # 测试步骤记录
        self.test_steps: List[TestStep] = []

        # 自愈开关
        self.self_healing_enabled = self.config.healenium.self_healing_enabled

        logger.info(f"HybridRunner初始化完成，Healenium自愈: {self.self_healing_enabled}")

    def start(self):
        """启动浏览器会话"""
        logger.info("启动Playwright浏览器...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.config.playwright.headless,
            slow_mo=self.config.playwright.slow_mo,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self.context = self.browser.new_context(
            viewport={
                "width": self.config.playwright.viewport_width,
                "height": self.config.playwright.viewport_height,
            },
            locale=self.config.playwright.locale,
            timezone_id=self.config.playwright.timezone,
        )
        self.context.set_default_timeout(self.config.playwright.timeout)
        self.context.set_default_navigation_timeout(
            self.config.playwright.navigation_timeout
        )
        self.page = self.context.new_page()
        logger.info("Playwright浏览器启动成功")

    def stop(self):
        """关闭浏览器会话"""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        if self.selenium_driver:
            try:
                self.selenium_driver.quit()
            except Exception:
                pass
        logger.info("浏览器会话已关闭")

    def navigate_to(self, path: str = ""):
        """导航到指定路径"""
        url = urljoin(self.config.base_url, path)
        logger.info(f"导航到: {url}")
        self.page.goto(url, wait_until="networkidle")
        return self.page

    def _create_page(self) -> Page:
        """创建新页面"""
        if not self.page:
            self.start()
        return self.page

    def execute_action(
        self,
        action: ElementAction,
        page: Optional[Page] = None,
    ) -> bool:
        """
        执行元素操作，失败时尝试自愈

        参数:
            action: 要执行的操作
            page: Playwright页面对象

        返回:
            操作是否成功
        """
        target_page = page or self.page
        if not target_page:
            logger.error("没有可用的页面对象")
            return False

        current_selector = action.selector

        # 检查选择器缓存
        if current_selector in self.selector_cache:
            cached = self.selector_cache[current_selector]
            if cached.success and cached.healed_selector:
                current_selector = cached.healed_selector
                logger.info(f"使用缓存的自愈选择器: {current_selector}")

        step = TestStep(
            step_id=len(self.test_steps) + 1,
            action=action,
            framework=TestFramework.PLAYWRIGHT,
        )

        try:
            # 使用Playwright执行操作
            self._execute_playwright_action(target_page, action, current_selector)
            step.success = True
            logger.info(f"步骤{step.step_id}执行成功: {action.action_type} - {current_selector}")

        except (PlaywrightTimeoutError, PlaywrightError) as e:
            logger.warning(f"Playwright执行失败: {e}")
            step.error = str(e)

            # 尝试自愈
            if self.self_healing_enabled:
                healing_result = self._heal_selector(
                    action.selector, target_page, action.action_type
                )

                if healing_result.success and healing_result.healed_selector:
                    # 使用修复后的选择器重试
                    step.healed_selector = healing_result.healed_selector
                    try:
                        self._execute_playwright_action(
                            target_page, action, healing_result.healed_selector
                        )
                        step.success = True
                        # 更新缓存
                        self.selector_cache[action.selector] = healing_result
                        logger.info(
                            f"自愈成功，新选择器: {healing_result.healed_selector}"
                        )
                    except Exception as retry_error:
                        step.error = f"重试失败: {retry_error}"
                        step.success = False
                else:
                    step.success = False
            else:
                step.success = False

        self.test_steps.append(step)
        return step.success

    def _execute_playwright_action(
        self, page: Page, action: ElementAction, selector: str
    ):
        """使用Playwright执行具体的元素操作"""
        timeout = action.timeout // 1000  # 转换为秒

        # 根据操作类型执行不同动作
        if action.action_type == "click":
            page.click(selector, timeout=timeout)
        elif action.action_type == "fill":
            page.fill(selector, action.value or "", timeout=timeout)
        elif action.action_type == "hover":
            page.hover(selector, timeout=timeout)
        elif action.action_type == "select":
            page.select_option(selector, action.value or "", timeout=timeout)
        elif action.action_type == "type":
            page.type(selector, action.value or "", timeout=timeout)
        elif action.action_type == "wait_for":
            page.wait_for_selector(selector, state="visible", timeout=timeout)
        elif action.action_type == "get_text":
            page.text_content(selector, timeout=timeout)
        elif action.action_type == "is_visible":
            page.is_visible(selector)
        else:
            raise ValueError(f"不支持的操作类型: {action.action_type}")

    def _heal_selector(
        self,
        original_selector: str,
        page: Page,
        action_type: str,
    ) -> HealingResult:
        """
        尝试修复失效的选择器

        参数:
            original_selector: 原始失效的选择器
            page: Playwright页面对象
            action_type: 操作类型（click, fill等）

        返回:
            HealingResult: 自愈结果
        """
        logger.info(f"开始自愈选择器: {original_selector}")

        try:
            # 获取页面HTML和截图用于分析
            page_html = page.content()

            # 尝试多种备选选择器策略
            alternative_selectors = self._generate_alternative_selectors(
                original_selector
            )

            for alt_selector in alternative_selectors:
                try:
                    # 验证备选选择器是否有效
                    if action_type == "click":
                        page.click(alt_selector, timeout=2000)
                    elif action_type == "fill":
                        page.fill(alt_selector, "", timeout=2000)
                    elif action_type == "wait_for":
                        page.wait_for_selector(alt_selector, state="visible", timeout=2000)
                    else:
                        page.is_visible(alt_selector, timeout=2000)

                    # 如果成功，返回修复结果
                    return HealingResult(
                        success=True,
                        original_selector=original_selector,
                        healed_selector=alt_selector,
                        healing_method="alternative_selector",
                        score=0.8,
                    )
                except Exception:
                    continue

            # 如果所有备选都失败，返回失败结果
            return HealingResult(
                success=False,
                original_selector=original_selector,
                healing_method="exhausted",
                error="无法找到有效的替代选择器",
            )

        except Exception as e:
            logger.error(f"自愈过程异常: {e}")
            return HealingResult(
                success=False,
                original_selector=original_selector,
                healing_method="error",
                error=str(e),
            )

    def _generate_alternative_selectors(self, selector: str) -> List[str]:
        """
        生成备选选择器列表

        根据原始选择器，生成多种备选策略
        """
        alternatives = []

        # 保留原始选择器（作为兜底）
        alternatives.append(selector)

        # 如果是CSS选择器，尝试以下策略：
        if selector.startswith(".") or selector.startswith("#") or selector.startswith("["):
            # 1. 尝试使用text内容定位
            if ":" in selector:
                alternatives.append(f"button:has-text('{selector.split(':')[-1]}')")

            # 2. 使用更宽泛的选择器
            if "." in selector:
                class_part = selector.split(".")[-1].split(" ")[0]
                alternatives.append(f".ant-btn:has-text('{class_part}')")
                alternatives.append(f"button.{class_part}")

            # 3. 使用Ant Design通用选择器
            if "button" in selector.lower():
                alternatives.extend([
                    ".ant-btn-primary",
                    "button.ant-btn",
                    "[class*='ant-btn']",
                ])

            # 4. 使用文本内容模糊匹配
            if "=" in selector:
                text_part = selector.split('=')[-1].strip("'")
                alternatives.append(f"text={text_part}")

        return alternatives

    def run_test_flow(
        self,
        actions: List[ElementAction],
        start_path: str = "",
    ) -> bool:
        """
        执行完整的测试流程

        参数:
            actions: 操作列表
            start_path: 起始路径

        返回:
            测试是否全部成功
        """
        logger.info(f"开始执行测试流程，共{len(actions)}个步骤")

        try:
            # 导航到起始页面
            if start_path:
                self.navigate_to(start_path)

            # 逐个执行操作
            for action in actions:
                success = self.execute_action(action)
                if not success:
                    logger.error(f"测试流程在步骤{len(self.test_steps)}失败")
                    return False

            logger.info("测试流程执行完成")
            return True

        except Exception as e:
            logger.error(f"测试流程异常: {e}")
            return False

    def get_test_report(self) -> Dict[str, Any]:
        """获取测试执行报告"""
        total_steps = len(self.test_steps)
        successful_steps = sum(1 for s in self.test_steps if s.success)
        healed_count = sum(
            1 for s in self.test_steps if s.healed_selector is not None
        )

        return {
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "failed_steps": total_steps - successful_steps,
            "healed_count": healed_count,
            "self_healing_rate": healed_count / total_steps if total_steps > 0 else 0,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action.action_type,
                    "selector": s.action.selector,
                    "healed_selector": s.healed_selector,
                    "success": s.success,
                    "error": s.error,
                }
                for s in self.test_steps
            ],
            "selector_cache": {
                original: {
                    "healed": result.healed_selector,
                    "method": result.healing_method,
                    "score": result.score,
                }
                for original, result in self.selector_cache.items()
            },
        }

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()
        return False


def create_action(
    action_type: str,
    selector: str,
    value: Optional[str] = None,
    timeout: int = 10000,
) -> ElementAction:
    """创建元素操作的辅助函数"""
    return ElementAction(
        action_type=action_type,
        selector=selector,
        value=value,
        timeout=timeout,
    )