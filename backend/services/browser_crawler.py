#!/usr/bin/env python3
"""浏览器爬虫服务 - 负责处理需要JavaScript渲染的页面"""
import asyncio
import logging
import random
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from backend.config import settings
from backend.services.anti_crawler_service import anti_crawler_service

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """浏览器配置"""
    headless: bool = True  # 是否使用无头浏览器
    slow_mo: int = 0  # 操作延迟（毫秒）
    timeout: int = 30000  # 超时时间（毫秒）
    user_agent: Optional[str] = None  # 用户代理
    viewport: Dict[str, int] = None  # 视口大小
    locale: str = "zh-CN"  # 语言
    accept_downloads: bool = False  # 是否接受下载


class BrowserCrawler:
    """浏览器爬虫"""
    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.logger = logger.getChild("browser_crawler")

    async def initialize(self):
        """初始化浏览器"""
        try:
            self.logger.info("开始初始化浏览器...")
            
            # 启动 Playwright
            self.logger.info("启动 Playwright...")
            playwright_instance = await async_playwright().start()
            if not playwright_instance:
                raise Exception("无法启动 Playwright")
            self.playwright = playwright_instance
            
            # 选择浏览器（默认使用Chromium）
            self.logger.info("选择浏览器...")
            browser_type = self.playwright.chromium
            if not browser_type:
                raise Exception("无法获取浏览器类型")
            
            # 启动浏览器
            self.logger.info("启动浏览器...")
            self.browser = await browser_type.launch(
                headless=self.config.headless,
                slow_mo=self.config.slow_mo,
                timeout=self.config.timeout
            )
            if not self.browser:
                raise Exception("无法启动浏览器")
            
            # 创建上下文
            self.logger.info("创建浏览器上下文...")
            context_options = {
                "locale": self.config.locale,
                "accept_downloads": self.config.accept_downloads,
            }
            
            if self.config.user_agent:
                context_options["user_agent"] = self.config.user_agent
            
            if self.config.viewport:
                context_options["viewport"] = self.config.viewport
            else:
                # 默认视口大小
                context_options["viewport"] = {
                    "width": 1366,
                    "height": 768
                }
            
            self.context = await self.browser.new_context(**context_options)
            if not self.context:
                raise Exception("无法创建浏览器上下文")
            
            # 创建页面
            self.logger.info("创建浏览器页面...")
            try:
                self.page = await self.context.new_page()
                if not self.page:
                    self.logger.warning("无法创建浏览器页面，将继续执行")
                else:
                    # 设置页面超时
                    try:
                        await self.page.set_default_timeout(self.config.timeout)
                        self.logger.info("设置页面超时成功")
                    except Exception as e:
                        self.logger.warning(f"无法设置页面超时: {e}")
            except Exception as e:
                self.logger.warning(f"创建浏览器页面时出错: {e}")
            
            self.logger.info("浏览器初始化成功")
            
        except Exception as e:
            self.logger.error(f"浏览器初始化失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            await self.close()
            raise

    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.logger.info("浏览器已关闭")
        except Exception as e:
            self.logger.error(f"关闭浏览器失败: {e}")

    async def goto(self, url: str, wait_until: str = "networkidle") -> bool:
        """导航到指定URL
        
        Args:
            url: 目标URL
            wait_until: 等待条件，可选值：load, domcontentloaded, networkidle, commit
            
        Returns:
            是否导航成功
        """
        try:
            if not self.page:
                await self.initialize()
            
            await self.page.goto(url, wait_until=wait_until)
            self.logger.info(f"成功导航到: {url}")
            return True
        except Exception as e:
            self.logger.error(f"导航失败 {url}: {e}")
            return False

    async def get_content(self) -> Optional[str]:
        """获取页面内容
        
        Returns:
            页面HTML内容
        """
        try:
            if not self.page:
                return None
            
            content = await self.page.content()
            return content
        except Exception as e:
            self.logger.error(f"获取页面内容失败: {e}")
            return None

    async def click(self, selector: str, timeout: Optional[int] = None) -> bool:
        """点击元素
        
        Args:
            selector: CSS选择器
            timeout: 超时时间（毫秒）
            
        Returns:
            是否点击成功
        """
        try:
            if not self.page:
                return False
            
            await self.page.click(selector, timeout=timeout)
            self.logger.info(f"成功点击元素: {selector}")
            return True
        except Exception as e:
            self.logger.error(f"点击元素失败 {selector}: {e}")
            return False

    async def fill(self, selector: str, text: str, timeout: Optional[int] = None) -> bool:
        """填充文本
        
        Args:
            selector: CSS选择器
            text: 要填充的文本
            timeout: 超时时间（毫秒）
            
        Returns:
            是否填充成功
        """
        try:
            if not self.page:
                return False
            
            await self.page.fill(selector, text, timeout=timeout)
            self.logger.info(f"成功填充文本到元素: {selector}")
            return True
        except Exception as e:
            self.logger.error(f"填充文本失败 {selector}: {e}")
            return False

    async def scroll(self, direction: str = "down", distance: int = 500) -> bool:
        """滚动页面
        
        Args:
            direction: 滚动方向，可选值：up, down, left, right
            distance: 滚动距离（像素）
            
        Returns:
            是否滚动成功
        """
        try:
            if not self.page:
                return False
            
            if direction == "down":
                await self.page.mouse.wheel(0, distance)
            elif direction == "up":
                await self.page.mouse.wheel(0, -distance)
            elif direction == "left":
                await self.page.mouse.wheel(-distance, 0)
            elif direction == "right":
                await self.page.mouse.wheel(distance, 0)
            else:
                self.logger.error(f"无效的滚动方向: {direction}")
                return False
            
            # 等待滚动完成
            await self.page.wait_for_timeout(1000)
            self.logger.info(f"成功滚动页面: {direction} {distance}px")
            return True
        except Exception as e:
            self.logger.error(f"滚动页面失败: {e}")
            return False

    async def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> bool:
        """等待元素出现
        
        Args:
            selector: CSS选择器
            timeout: 超时时间（毫秒）
            
        Returns:
            是否等待成功
        """
        try:
            if not self.page:
                return False
            
            await self.page.wait_for_selector(selector, timeout=timeout)
            self.logger.info(f"元素出现: {selector}")
            return True
        except Exception as e:
            self.logger.error(f"等待元素失败 {selector}: {e}")
            return False

    async def evaluate(self, expression: str) -> Optional[Any]:
        """执行JavaScript表达式
        
        Args:
            expression: JavaScript表达式
            
        Returns:
            表达式执行结果
        """
        try:
            if not self.page:
                return None
            
            result = await self.page.evaluate(expression)
            return result
        except Exception as e:
            self.logger.error(f"执行JavaScript失败: {e}")
            return None

    async def wait_for_load_state(self, state: str = "networkidle") -> bool:
        """等待页面加载状态
        
        Args:
            state: 加载状态，可选值：load, domcontentloaded, networkidle
            
        Returns:
            是否等待成功
        """
        try:
            if not self.page:
                return False
            
            await self.page.wait_for_load_state(state)
            self.logger.info(f"页面加载状态: {state}")
            return True
        except Exception as e:
            self.logger.error(f"等待页面加载状态失败: {e}")
            return False

    async def simulate_user_behavior(self):
        """模拟用户行为
        
        模拟真实用户的浏览行为，如随机滚动、停留等
        """
        try:
            if not self.page:
                return
            
            # 使用反爬虫服务的行为模拟功能
            await anti_crawler_service.simulate_user_behavior(self.page)
            
            self.logger.info("成功模拟用户行为")
            
        except Exception as e:
            self.logger.error(f"模拟用户行为失败: {e}")

    async def crawl_page(self, url: str, simulate_behavior: bool = True) -> Optional[str]:
        """爬取页面
        
        Args:
            url: 目标URL
            simulate_behavior: 是否模拟用户行为
            
        Returns:
            页面HTML内容
        """
        try:
            # 导航到URL
            success = await self.goto(url)
            if not success:
                return None
            
            # 模拟用户行为
            if simulate_behavior:
                await self.simulate_user_behavior()
            else:
                # 等待页面加载完成
                await self.wait_for_load_state()
            
            # 获取页面内容
            content = await self.get_content()
            return content
        except Exception as e:
            self.logger.error(f"爬取页面失败 {url}: {e}")
            return None


class BrowserCrawlerService:
    """浏览器爬虫服务"""
    def __init__(self):
        self.crawlers: List[BrowserCrawler] = []
        self.max_crawlers = 5
        self.logger = logger.getChild("browser_crawler_service")

    async def get_crawler(self) -> Optional[BrowserCrawler]:
        """获取一个可用的浏览器爬虫
        
        Returns:
            浏览器爬虫实例
        """
        # 如果爬虫数量超过最大值，关闭最早的爬虫
        if len(self.crawlers) >= self.max_crawlers:
            oldest_crawler = self.crawlers.pop(0)
            await oldest_crawler.close()
        
        # 创建新的爬虫
        crawler = BrowserCrawler()
        try:
            await crawler.initialize()
            self.crawlers.append(crawler)
            return crawler
        except Exception as e:
            self.logger.error(f"创建浏览器爬虫失败: {e}")
            await crawler.close()
            return None

    async def crawl(self, url: str, simulate_behavior: bool = True) -> Optional[str]:
        """爬取页面
        
        Args:
            url: 目标URL
            simulate_behavior: 是否模拟用户行为
            
        Returns:
            页面HTML内容
        """
        # 请求前等待，避免请求过快
        await anti_crawler_service.wait_before_request(url)
        
        crawler = await self.get_crawler()
        if not crawler:
            return None
        
        try:
            content = await crawler.crawl_page(url, simulate_behavior)
            return content
        finally:
            # 关闭爬虫
            await crawler.close()
            # 从列表中移除
            if crawler in self.crawlers:
                self.crawlers.remove(crawler)

    async def close_all(self):
        """关闭所有爬虫"""
        for crawler in self.crawlers:
            try:
                await crawler.close()
            except Exception as e:
                self.logger.error(f"关闭爬虫失败: {e}")
        self.crawlers.clear()


# 全局浏览器爬虫服务实例
browser_crawler_service = BrowserCrawlerService()
