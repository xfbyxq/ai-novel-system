#!/usr/bin/env python3
"""代理池管理服务 - 负责获取、验证和管理代理IP"""
import asyncio
import logging
import random
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Proxy:
    """代理IP信息"""
    ip: str
    port: int
    protocol: str = "http"
    country: str = ""
    city: str = ""
    speed: float = 0.0
    success_rate: float = 0.0
    last_used: Optional[float] = None
    last_verified: Optional[float] = None
    status: str = "unknown"  # unknown, valid, invalid
    source: str = ""
    anonymity: str = "unknown"  # transparent, anonymous, elite

    @property
    def url(self) -> str:
        """获取代理URL"""
        return f"{self.protocol}://{self.ip}:{self.port}"

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "country": self.country,
            "city": self.city,
            "speed": self.speed,
            "success_rate": self.success_rate,
            "last_used": self.last_used,
            "last_verified": self.last_verified,
            "status": self.status,
            "source": self.source,
            "anonymity": self.anonymity,
            "url": self.url
        }


class ProxySource:
    """代理源基类"""
    def __init__(self, name: str):
        self.name = name
        self.logger = logger.getChild(name)

    async def fetch_proxies(self) -> List[Proxy]:
        """获取代理列表"""
        raise NotImplementedError


class FreeProxyListSource(ProxySource):
    """FreeProxyList.net 代理源"""
    def __init__(self):
        super().__init__("free_proxy_list")
        self.url = "https://free-proxy-list.net/"

    async def fetch_proxies(self) -> List[Proxy]:
        """从FreeProxyList.net获取代理"""
        proxies = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                table = soup.select_one("#proxylisttable")
                if not table:
                    return proxies
                
                rows = table.select("tbody tr")
                for row in rows:
                    cols = row.select("td")
                    if len(cols) < 8:
                        continue
                    
                    ip = cols[0].text.strip()
                    port = int(cols[1].text.strip())
                    protocol = "https" if cols[6].text.strip() == "yes" else "http"
                    anonymity = cols[4].text.strip()
                    country = cols[2].text.strip()
                    
                    proxy = Proxy(
                        ip=ip,
                        port=port,
                        protocol=protocol,
                        country=country,
                        anonymity=anonymity,
                        source=self.name
                    )
                    proxies.append(proxy)
                    
        except Exception as e:
            self.logger.error(f"获取代理失败: {e}")
        
        return proxies


class ProxyNovaSource(ProxySource):
    """ProxyNova 代理源"""
    def __init__(self):
        super().__init__("proxy_nova")
        self.url = "https://www.proxynova.com/proxy-server-list/"

    async def fetch_proxies(self) -> List[Proxy]:
        """从ProxyNova获取代理"""
        proxies = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                rows = soup.select("table#tbl_proxy_list tbody tr")
                
                for row in rows:
                    ip_elem = row.select_one(".ip")
                    port_elem = row.select_one(".port")
                    if not ip_elem or not port_elem:
                        continue
                    
                    # 提取IP和端口
                    ip = ip_elem.text.strip()
                    port_script = port_elem.select_one("script").text.strip()
                    # 简单的JavaScript解析来获取端口
                    port = self._extract_port(port_script)
                    if not port:
                        continue
                    
                    country_elem = row.select_one(".country")
                    country = country_elem.text.strip() if country_elem else ""
                    
                    proxy = Proxy(
                        ip=ip,
                        port=port,
                        protocol="http",
                        country=country,
                        source=self.name
                    )
                    proxies.append(proxy)
                    
        except Exception as e:
            self.logger.error(f"获取代理失败: {e}")
        
        return proxies

    def _extract_port(self, script: str) -> Optional[int]:
        """从JavaScript中提取端口"""
        try:
            # 简单的JavaScript解析
            # 例如: document.write((1412439 ^ 0x16B7B));
            import re
            match = re.search(r'\(\s*(\d+)\s*\^\s*0x([0-9A-Fa-f]+)\s*\)', script)
            if match:
                num1 = int(match.group(1))
                num2 = int(match.group(2), 16)
                return num1 ^ num2
        except Exception:
            pass
        return None


class SocksProxySource(ProxySource):
    """Socks-Proxy.net 代理源"""
    def __init__(self):
        super().__init__("socks_proxy")
        self.url = "https://www.socks-proxy.net/"

    async def fetch_proxies(self) -> List[Proxy]:
        """从Socks-Proxy.net获取代理"""
        proxies = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                table = soup.select_one("#proxylisttable")
                if not table:
                    return proxies
                
                rows = table.select("tbody tr")
                for row in rows:
                    cols = row.select("td")
                    if len(cols) < 8:
                        continue
                    
                    ip = cols[0].text.strip()
                    port = int(cols[1].text.strip())
                    protocol = "socks4" if cols[4].text.strip() == "Socks4" else "socks5"
                    country = cols[2].text.strip()
                    
                    proxy = Proxy(
                        ip=ip,
                        port=port,
                        protocol=protocol,
                        country=country,
                        source=self.name
                    )
                    proxies.append(proxy)
                    
        except Exception as e:
            self.logger.error(f"获取代理失败: {e}")
        
        return proxies


class ProxyManager:
    """代理管理器"""
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.proxies: List[Proxy] = []
        self.sources: List[ProxySource] = [
            FreeProxyListSource(),
            ProxyNovaSource(),
            SocksProxySource()
        ]
        self.min_proxies = 50
        self.max_proxies = 200
        self.validation_timeout = 5.0
        self.logger = logger.getChild("proxy_manager")

    async def initialize(self):
        """初始化代理池"""
        await self.refresh_proxies()

    async def refresh_proxies(self):
        """刷新代理池"""
        self.logger.info("开始刷新代理池...")
        
        # 从所有源获取代理
        new_proxies = []
        tasks = [source.fetch_proxies() for source in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"从{self.sources[i].name}获取代理失败: {result}")
                continue
            new_proxies.extend(result)
        
        # 去重
        unique_proxies = self._deduplicate_proxies(new_proxies)
        
        # 验证代理
        valid_proxies = await self._validate_proxies(unique_proxies)
        
        # 更新代理池
        self.proxies = valid_proxies[:self.max_proxies]
        self.logger.info(f"代理池刷新完成，有效代理数: {len(self.proxies)}")

    def _deduplicate_proxies(self, proxies: List[Proxy]) -> List[Proxy]:
        """去重代理"""
        seen = set()
        unique = []
        for proxy in proxies:
            key = (proxy.ip, proxy.port)
            if key not in seen:
                seen.add(key)
                unique.append(proxy)
        return unique

    async def _validate_proxies(self, proxies: List[Proxy]) -> List[Proxy]:
        """验证代理有效性"""
        valid_proxies = []
        tasks = []
        
        for proxy in proxies:
            task = self._validate_proxy(proxy)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if result:
                valid_proxies.append(result)
        
        return valid_proxies

    async def _validate_proxy(self, proxy: Proxy) -> Optional[Proxy]:
        """验证单个代理"""
        try:
            start_time = time.time()
            
            async with httpx.AsyncClient(
                timeout=self.validation_timeout,
                proxies={"all://": proxy.url}
            ) as client:
                response = await client.get("http://www.example.com", timeout=self.validation_timeout)
                if response.status_code == 200:
                    proxy.status = "valid"
                    proxy.speed = time.time() - start_time
                    proxy.success_rate = 1.0
                    proxy.last_verified = time.time()
                    return proxy
        except Exception:
            pass
        
        proxy.status = "invalid"
        proxy.last_verified = time.time()
        return None

    async def get_proxy(self, protocol: str = "http") -> Optional[Proxy]:
        """获取一个可用的代理"""
        # 确保代理池有足够的代理
        if len(self.proxies) < self.min_proxies:
            await self.refresh_proxies()
        
        # 过滤出符合协议要求的有效代理
        valid_proxies = [
            p for p in self.proxies 
            if p.status == "valid" and (protocol == "all" or p.protocol == protocol)
        ]
        
        if not valid_proxies:
            return None
        
        # 按速度和成功率排序，选择最优代理
        valid_proxies.sort(key=lambda p: (p.speed, -p.success_rate))
        
        # 标记为已使用
        proxy = valid_proxies[0]
        proxy.last_used = time.time()
        
        return proxy

    async def mark_proxy_used(self, proxy: Proxy, success: bool):
        """标记代理使用情况"""
        # 更新成功率
        if success:
            proxy.success_rate = min(1.0, proxy.success_rate + 0.1)
        else:
            proxy.success_rate = max(0.0, proxy.success_rate - 0.2)
        
        # 如果成功率过低，标记为无效
        if proxy.success_rate < 0.3:
            proxy.status = "invalid"

    def get_proxy_stats(self) -> Dict[str, int]:
        """获取代理池统计信息"""
        total = len(self.proxies)
        valid = len([p for p in self.proxies if p.status == "valid"])
        invalid = len([p for p in self.proxies if p.status == "invalid"])
        
        return {
            "total": total,
            "valid": valid,
            "invalid": invalid
        }


class ProxyService:
    """代理服务"""
    def __init__(self, db: Optional[AsyncSession] = None):
        self.manager = ProxyManager(db)
        self.logger = logger.getChild("proxy_service")

    async def initialize(self):
        """初始化代理服务"""
        await self.manager.initialize()

    async def get_proxy(self, protocol: str = "http") -> Optional[str]:
        """获取一个可用的代理URL"""
        proxy = await self.manager.get_proxy(protocol)
        return proxy.url if proxy else None

    async def mark_proxy_result(self, proxy_url: str, success: bool):
        """标记代理使用结果"""
        # 查找对应的代理
        for proxy in self.manager.proxies:
            if proxy.url == proxy_url:
                await self.manager.mark_proxy_used(proxy, success)
                break

    async def get_stats(self) -> Dict[str, int]:
        """获取代理服务统计信息"""
        return self.manager.get_proxy_stats()

    async def refresh_proxies(self):
        """手动刷新代理池"""
        await self.manager.refresh_proxies()
