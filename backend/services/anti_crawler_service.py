#!/usr/bin/env python3
"""反爬虫服务 - 负责实现高级反爬虫策略"""
import asyncio
import logging
import random
import time
import hashlib
import json
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

import httpx
from fake_useragent import UserAgent

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AntiCrawlerConfig:
    """反爬虫配置"""
    min_request_interval: float = 1.0  # 最小请求间隔（秒）
    max_request_interval: float = 5.0  # 最大请求间隔（秒）
    use_random_headers: bool = True  # 是否使用随机头
    use_fingerprint: bool = True  # 是否使用指纹模拟
    use_cookies: bool = True  # 是否使用Cookie管理
    use_behavior_simulation: bool = True  # 是否使用行为模拟
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 2.0  # 重试延迟（秒）


class BrowserFingerprint:
    """浏览器指纹模拟"""
    def __init__(self):
        self.user_agent = UserAgent()
        self.logger = logger.getChild("browser_fingerprint")
        
    def get_fingerprint(self, platform: str = "desktop") -> Dict[str, str]:
        """获取浏览器指纹
        
        Args:
            platform: 平台类型，可选值：desktop, mobile, tablet
            
        Returns:
            浏览器指纹信息
        """
        fingerprint = {
            # User-Agent
            "User-Agent": self._get_user_agent(platform),
            
            # Accept headers
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            
            # Connection headers
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            
            # Cache headers
            "Cache-Control": "max-age=0",
            
            # DNT (Do Not Track)
            "DNT": "1",
            
            # Sec headers (Chrome specific)
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        
        return fingerprint
    
    def _get_user_agent(self, platform: str = "desktop") -> str:
        """获取用户代理
        
        Args:
            platform: 平台类型
            
        Returns:
            用户代理字符串
        """
        try:
            if platform == "mobile":
                return self.user_agent.random
            elif platform == "tablet":
                return self.user_agent.random
            else:  # desktop
                return self.user_agent.chrome
        except Exception as e:
            self.logger.error(f"获取用户代理失败: {e}")
            # 返回默认的用户代理
            return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class CookieManager:
    """Cookie管理"""
    def __init__(self):
        self.cookies: Dict[str, Dict[str, str]] = {}  # 按域名存储Cookie
        self.logger = logger.getChild("cookie_manager")
    
    def get_cookies(self, domain: str) -> Dict[str, str]:
        """获取指定域名的Cookie
        
        Args:
            domain: 域名
            
        Returns:
            Cookie字典
        """
        return self.cookies.get(domain, {})
    
    def update_cookies(self, domain: str, cookies: Dict[str, str]):
        """更新指定域名的Cookie
        
        Args:
            domain: 域名
            cookies: 新的Cookie字典
        """
        if domain not in self.cookies:
            self.cookies[domain] = {}
        self.cookies[domain].update(cookies)
        self.logger.info(f"更新域名 {domain} 的Cookie")
    
    def clear_cookies(self, domain: Optional[str] = None):
        """清除Cookie
        
        Args:
            domain: 域名，如果为None则清除所有Cookie
        """
        if domain:
            if domain in self.cookies:
                del self.cookies[domain]
                self.logger.info(f"清除域名 {domain} 的Cookie")
        else:
            self.cookies.clear()
            self.logger.info("清除所有Cookie")


class BehaviorSimulator:
    """行为模拟"""
    def __init__(self):
        self.logger = logger.getChild("behavior_simulator")
    
    async def simulate_behavior(self, page=None):
        """模拟用户行为
        
        Args:
            page: 浏览器页面对象（如果有）
        """
        try:
            # 随机等待时间
            wait_time = random.uniform(0.5, 2.0)
            self.logger.info(f"模拟用户思考，等待 {wait_time:.2f} 秒")
            await asyncio.sleep(wait_time)
            
            # 如果有页面对象，可以模拟更多行为
            if page:
                # 随机滚动
                await self._simulate_scrolling(page)
                
                # 随机点击
                await self._simulate_clicking(page)
                
                # 随机鼠标移动
                await self._simulate_mouse_movement(page)
                
        except Exception as e:
            self.logger.error(f"模拟用户行为失败: {e}")
    
    async def _simulate_scrolling(self, page):
        """模拟滚动行为
        
        Args:
            page: 浏览器页面对象
        """
        try:
            if random.random() > 0.5:
                scroll_count = random.randint(1, 3)
                for i in range(scroll_count):
                    distance = random.randint(100, 500)
                    direction = random.choice(["up", "down"])
                    self.logger.info(f"模拟滚动 {direction} {distance}px")
                    
                    if direction == "down":
                        await page.mouse.wheel(0, distance)
                    else:
                        await page.mouse.wheel(0, -distance)
                    
                    await asyncio.sleep(random.uniform(0.3, 1.0))
        except Exception as e:
            self.logger.error(f"模拟滚动失败: {e}")
    
    async def _simulate_clicking(self, page):
        """模拟点击行为
        
        Args:
            page: 浏览器页面对象
        """
        try:
            if random.random() > 0.7:
                # 尝试点击页面中的一些常见元素
                clickable_selectors = [
                    "a[href]",
                    "button",
                    ".btn",
                    ".link",
                    "input[type='button']",
                    "input[type='submit']"
                ]
                
                for selector in clickable_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            # 随机选择一个元素点击
                            element = random.choice(elements)
                            self.logger.info(f"模拟点击元素: {selector}")
                            await element.click()
                            await asyncio.sleep(random.uniform(0.5, 1.5))
                            break
                    except Exception:
                        pass
        except Exception as e:
            self.logger.error(f"模拟点击失败: {e}")
    
    async def _simulate_mouse_movement(self, page):
        """模拟鼠标移动行为
        
        Args:
            page: 浏览器页面对象
        """
        try:
            if random.random() > 0.5:
                # 随机移动鼠标
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                self.logger.info(f"模拟鼠标移动到 ({x}, {y})")
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.2, 0.5))
        except Exception as e:
            self.logger.error(f"模拟鼠标移动失败: {e}")


class AntiCrawlerService:
    """反爬虫服务"""
    def __init__(self, config: Optional[AntiCrawlerConfig] = None):
        self.config = config or AntiCrawlerConfig()
        self.fingerprint = BrowserFingerprint()
        self.cookie_manager = CookieManager()
        self.behavior_simulator = BehaviorSimulator()
        self.request_history: List[Tuple[str, float]] = []  # (url, timestamp)
        self.logger = logger.getChild("anti_crawler_service")
    
    async def get_headers(self, url: str, platform: str = "desktop") -> Dict[str, str]:
        """获取反爬虫 headers
        
        Args:
            url: 请求URL
            platform: 平台类型
            
        Returns:
            Headers字典
        """
        headers = {}
        
        # 添加浏览器指纹
        if self.config.use_fingerprint:
            fingerprint = self.fingerprint.get_fingerprint(platform)
            headers.update(fingerprint)
        else:
            # 使用默认的User-Agent
            headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        return headers
    
    async def get_cookies(self, url: str) -> Dict[str, str]:
        """获取反爬虫 cookies
        
        Args:
            url: 请求URL
            
        Returns:
            Cookies字典
        """
        if not self.config.use_cookies:
            return {}
        
        # 提取域名
        domain = url.split("//")[1].split("/")[0]
        return self.cookie_manager.get_cookies(domain)
    
    async def update_cookies(self, url: str, response: httpx.Response):
        """从响应中更新 cookies
        
        Args:
            url: 请求URL
            response: 响应对象
        """
        if not self.config.use_cookies:
            return
        
        # 提取域名
        domain = url.split("//")[1].split("/")[0]
        
        # 从响应中获取 cookies
        cookies = {}
        for cookie in response.cookies:
            cookies[cookie.name] = cookie.value
        
        if cookies:
            self.cookie_manager.update_cookies(domain, cookies)
    
    async def calculate_request_interval(self, url: str) -> float:
        """计算请求间隔
        
        Args:
            url: 请求URL
            
        Returns:
            请求间隔（秒）
        """
        # 清理过期的历史记录（只保留最近10分钟的）
        now = time.time()
        self.request_history = [(u, t) for u, t in self.request_history if now - t < 600]
        
        # 计算最近的请求频率
        domain = url.split("//")[1].split("/")[0]
        domain_requests = [t for u, t in self.request_history if domain in u]
        
        if domain_requests:
            # 计算最近1分钟内的请求次数
            recent_requests = [t for t in domain_requests if now - t < 60]
            request_count = len(recent_requests)
            
            # 根据请求次数动态调整间隔
            if request_count > 20:
                # 高频率请求，增加间隔
                return min(self.config.max_request_interval, 3.0)
            elif request_count > 10:
                # 中等频率请求，保持中等间隔
                return min(self.config.max_request_interval, 2.0)
            else:
                # 低频率请求，使用最小间隔
                return self.config.min_request_interval
        else:
            # 第一次请求，使用默认间隔
            return self.config.min_request_interval
    
    async def wait_before_request(self, url: str):
        """请求前等待
        
        Args:
            url: 请求URL
        """
        interval = await self.calculate_request_interval(url)
        self.logger.info(f"请求前等待 {interval:.2f} 秒")
        await asyncio.sleep(interval)
        
        # 记录请求时间
        self.request_history.append((url, time.time()))
    
    async def simulate_user_behavior(self, page=None):
        """模拟用户行为
        
        Args:
            page: 浏览器页面对象（如果有）
        """
        if self.config.use_behavior_simulation:
            await self.behavior_simulator.simulate_behavior(page)
    
    def is_ip_blocked(self, response: httpx.Response) -> bool:
        """检测IP是否被封禁
        
        Args:
            response: 响应对象
            
        Returns:
            是否被封禁
        """
        try:
            # 检查状态码
            if response.status_code in [403, 429, 503]:
                self.logger.warning(f"可能被封禁，状态码: {response.status_code}")
                return True
            
            # 检查响应内容
            content = response.text.lower()
            if any(keyword in content for keyword in [
                "您的访问过于频繁",
                "访问被拒绝",
                "403 forbidden",
                "too many requests",
                "captcha",
                "验证码"
            ]):
                self.logger.warning("检测到可能被封禁的响应内容")
                return True
            
            return False
        except Exception as e:
            self.logger.error(f"检测IP封禁状态失败: {e}")
            return False
    
    def get_fingerprint_hash(self, fingerprint: Dict[str, str]) -> str:
        """获取指纹哈希值
        
        Args:
            fingerprint: 指纹字典
            
        Returns:
            哈希值
        """
        try:
            # 对指纹排序后生成哈希
            sorted_items = sorted(fingerprint.items())
            fingerprint_str = json.dumps(sorted_items)
            return hashlib.md5(fingerprint_str.encode()).hexdigest()
        except Exception as e:
            self.logger.error(f"生成指纹哈希失败: {e}")
            return ""


# 全局反爬虫服务实例
anti_crawler_service = AntiCrawlerService()
