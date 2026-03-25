"""
Healenium适配器 - 连接Healenium自愈服务

提供与Healenium Server的通信能力，
实现元素定位的智能修复和评分

作者: Qoder
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import urljoin
import requests

from tests.ai_e2e.config import HealeniumConfig

logger = logging.getLogger(__name__)


@dataclass
class HealeniumResponse:
    """Healenium服务器响应"""
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None


@dataclass
class SelectorScore:
    """选择器评分"""
    selector: str
    score: float
    method: str  # healenium, ai, fallback


class HealeniumAdapter:
    """
    Healenium适配器

    与Healenium Server通信，获取元素定位的替代方案
    Healenium通过机器学习分析页面结构，推荐最佳选择器
    """

    def __init__(self, config: Optional[HealeniumConfig] = None):
        """
        初始化Healenium适配器

        参数:
            config: Healenium配置
        """
        self.config = config or HealeniumConfig()
        self.endpoint = self.config.endpoint
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        # 统计信息
        self.request_count = 0
        self.success_count = 0
        self.total_healing_time = 0.0

        logger.info(f"HealeniumAdapter初始化，endpoint: {self.endpoint}")

    def is_available(self) -> bool:
        """
        检查Healenium Server是否可用

        返回:
            服务器是否可达
        """
        try:
            response = self.session.get(
                f"{self.endpoint}/health",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Healenium Server不可用: {e}")
            return False

    def find_alternative(
        self,
        original_selector: str,
        page_html: str,
        page_url: str = "",
        action: str = "click",
    ) -> SelectorScore:
        """
        寻找失效选择器的替代方案

        参数:
            original_selector: 原始失效的选择器
            page_html: 页面HTML内容
            page_url: 页面URL
            action: 操作类型

        返回:
            SelectorScore: 最佳替代选择器及其评分
        """
        start_time = time.time()
        self.request_count += 1

        try:
            # 构建请求payload
            payload = {
                "selector": original_selector,
                "page": {
                    "html": page_html,
                    "url": page_url,
                },
                "action": action,
                "threshold": self.config.score_threshold,
            }

            # 调用Healenium API
            response = self.session.post(
                f"{self.endpoint}/selector/heal",
                json=payload,
                timeout=self.config.healing_timeout / 1000,
            )

            if response.status_code == 200:
                data = response.json()
                self.success_count += 1

                result = SelectorScore(
                    selector=data.get("healedSelector", original_selector),
                    score=data.get("score", 0.0),
                    method="healenium",
                )

                elapsed = time.time() - start_time
                self.total_healing_time += elapsed
                logger.info(
                    f"Healenium找到替代选择器: {result.selector}, "
                    f"评分: {result.score}, 耗时: {elapsed:.2f}s"
                )

                return result
            else:
                logger.warning(
                    f"Healenium返回错误状态码: {response.status_code}"
                )
                return SelectorScore(
                    selector=original_selector,
                    score=0.0,
                    method="healenium_failed",
                )

        except requests.Timeout:
            logger.warning("Healenium请求超时")
            return SelectorScore(
                selector=original_selector,
                score=0.0,
                method="healenium_timeout",
            )
        except Exception as e:
            logger.error(f"Healenium请求异常: {e}")
            return SelectorScore(
                selector=original_selector,
                score=0.0,
                method="healenium_error",
            )

    def record_successful_selectors(
        self,
        test_session_id: str,
        selectors: List[Dict[str, str]],
    ):
        """
        记录成功定位的元素选择器

        用于Healenium学习哪些选择器是稳定的

        参数:
            test_session_id: 测试会话ID
            selectors: 成功选择器列表 [{"selector": "...", "by": "..."}]
        """
        try:
            payload = {
                "sessionId": test_session_id,
                "selectors": selectors,
            }

            response = self.session.post(
                f"{self.endpoint}/selector/record",
                json=payload,
                timeout=10,
            )

            if response.status_code == 200:
                logger.info(f"成功记录{len(selectors)}个选择器")
            else:
                logger.warning(f"记录选择器失败: {response.status_code}")

        except Exception as e:
            logger.error(f"记录选择器异常: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """获取Healenium使用统计"""
        avg_time = (
            self.total_healing_time / self.request_count
            if self.request_count > 0
            else 0.0
        )
        success_rate = (
            self.success_count / self.request_count
            if self.request_count > 0
            else 0.0
        )

        return {
            "total_requests": self.request_count,
            "successful_heals": self.success_count,
            "success_rate": success_rate,
            "average_healing_time": avg_time,
            "total_healing_time": self.total_healing_time,
        }

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.session.close()
        return False


class SelectorManager:
    """
    选择器管理器

    统一管理所有选择器，包括缓存、学习和回退策略
    """

    def __init__(self, healenium_config: Optional[HealeniumConfig] = None):
        """
        初始化选择器管理器

        参数:
            healenium_config: Healenium配置
        """
        self.healenium = HealeniumAdapter(healenium_config)
        self.selector_history: Dict[str, List[SelectorScore]] = {}
        self.fallback_strategies = self._init_fallback_strategies()

    def _init_fallback_strategies(self) -> Dict[str, callable]:
        """初始化回退策略"""
        return {
            "css_to_text": self._css_to_text_strategy,
            "class_to_ant": self._class_to_ant_strategy,
            "xpath_fallback": self._xpath_fallback_strategy,
            "partial_match": self._partial_match_strategy,
        }

    def get_best_selector(
        self,
        failed_selector: str,
        page_html: str,
        action: str = "click",
    ) -> str:
        """
        获取最佳替代选择器

        优先级：
        1. Healenium智能推荐
        2. 回退策略
        3. 原始选择器

        参数:
            failed_selector: 失效的选择器
            page_html: 页面HTML
            action: 操作类型

        返回:
            最佳替代选择器
        """
        # 尝试Healenium
        if self.healenium.is_available():
            result = self.healenium.find_alternative(
                failed_selector, page_html, action=action
            )
            if result.score >= self.healenium.config.score_threshold:
                self._record_history(failed_selector, result)
                return result.selector

        # 尝试回退策略
        for strategy_name, strategy_func in self.fallback_strategies.items():
            alternative = strategy_func(failed_selector, page_html)
            if alternative:
                self._record_history(
                    failed_selector,
                    SelectorScore(alternative, 0.5, strategy_name),
                )
                return alternative

        # 返回原始选择器
        return failed_selector

    def _css_to_text_strategy(
        self, selector: str, page_html: str
    ) -> Optional[str]:
        """CSS选择器转文本定位策略"""
        # 提取可能的关键字
        keywords = []

        # 从class中提取
        if "." in selector:
            class_part = selector.split(".")[-1].split(" ")[0]
            keywords.append(class_part)

        # 从id中提取
        if "#" in selector:
            id_part = selector.split("#")[-1].split(" ")[0]
            keywords.append(id_part)

        # 生成文本选择器
        for keyword in keywords:
            if len(keyword) >= 3:  # 至少3个字符
                return f"text={keyword}"

        return None

    def _class_to_ant_strategy(
        self, selector: str, page_html: str
    ) -> Optional[str]:
        """Ant Design组件回退策略"""
        # 检测是否可能是Ant Design组件
        if "button" in selector.lower() or "btn" in selector.lower():
            return ".ant-btn-primary"

        if "input" in selector.lower() or "input" in selector.lower():
            return ".ant-input"

        if "modal" in selector.lower() or "dialog" in selector.lower():
            return ".ant-modal-content"

        if "table" in selector.lower():
            return ".ant-table"

        return None

    def _xpath_fallback_strategy(
        self, selector: str, page_html: str
    ) -> Optional[str]:
        """XPath回退策略"""
        # 尝试将CSS选择器转换为XPath
        if selector.startswith("."):
            # class选择器
            class_name = selector[1:]
            return f"//*[contains(@class, '{class_name}')]"

        if selector.startswith("#"):
            # ID选择器
            id_name = selector[1:]
            return f"//*[@id='{id_name}']"

        if selector.startswith("["):
            # 属性选择器
            return f"//{selector}"

        return None

    def _partial_match_strategy(
        self, selector: str, page_html: str
    ) -> Optional[str]:
        """部分匹配策略"""
        # 提取选择器的核心部分进行模糊匹配
        parts = selector.replace(".", " ").replace("#", " ").split()

        for part in parts:
            if len(part) >= 4:  # 至少4个字符
                # 生成模糊选择器
                fuzzy_selector = f"[class*='{part}']"
                return fuzzy_selector

        return None

    def _record_history(self, original: str, score: SelectorScore):
        """记录选择器历史"""
        if original not in self.selector_history:
            self.selector_history[original] = []
        self.selector_history[original].append(score)

    def get_statistics(self) -> Dict[str, Any]:
        """获取选择器管理统计"""
        return {
            "healenium_stats": self.healenium.get_statistics(),
            "selector_history_count": len(self.selector_history),
            "fallback_strategies": list(self.fallback_strategies.keys()),
        }