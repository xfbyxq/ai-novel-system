"""
测试自愈修复器

基于Healenium和AI的智能修复机制
当元素定位失败时自动寻找替代方案

作者: Qoder
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from tests.ai_e2e.config import HealeniumConfig, AIConfig
from tests.ai_e2e.selectors.healenium_adapter import HealeniumAdapter, SelectorManager
from tests.ai_e2e.agents.test_executor import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class HealingRecord:
    """修复记录"""
    original_selector: str
    healed_selector: Optional[str]
    healing_method: str
    success: bool
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None


@dataclass
class HealingResult:
    """修复结果"""
    success: bool
    original_selector: str
    healed_selector: Optional[str] = None
    method: str = ""
    confidence: float = 0.0
    alternatives: List[str] = field(default_factory=list)
    error: Optional[str] = None


class SelfHealer:
    """
    测试自愈修复器

    当测试中的元素定位失败时，自动寻找有效的替代选择器
    集成Healenium和LLM两种修复策略
    """

    def __init__(
        self,
        healenium_config: Optional[HealeniumConfig] = None,
        ai_config: Optional[AIConfig] = None,
    ):
        """
        初始化自愈修复器

        参数:
            healenium_config: Healenium配置
            ai_config: AI大模型配置
        """
        self.healenium_config = healenium_config or HealeniumConfig()
        self.ai_config = ai_config or AIConfig()

        # 初始化组件
        self.healenium_adapter = None
        self.selector_manager = None
        self.llm_client = None

        # 修复历史
        self.healing_history: List[HealingRecord] = []

        # 统计信息
        self.total_attempts = 0
        self.successful_heals = 0
        self.failed_heals = 0

        # 延迟初始化
        self._initialized = False

    def _ensure_initialized(self):
        """确保组件已初始化"""
        if not self._initialized:
            if self.healenium_config.enabled:
                self.healenium_adapter = HealeniumAdapter(self.healenium_config)
                self.selector_manager = SelectorManager(self.healenium_config)
            self.llm_client = LLMClient(self.ai_config)
            self._initialized = True
            logger.info("SelfHealer组件初始化完成")

    def heal(
        self,
        failed_selector: str,
        page_html: str,
        page_url: str = "",
        action: str = "click",
        context: Optional[Dict[str, Any]] = None,
    ) -> HealingResult:
        """
        修复失效的选择器

        参数:
            failed_selector: 原始失效的选择器
            page_html: 页面HTML内容
            page_url: 页面URL
            action: 操作类型
            context: 额外上下文信息

        返回:
            HealingResult: 修复结果
        """
        self._ensure_initialized()
        self.total_attempts += 1

        logger.info(f"开始修复选择器: {failed_selector} (操作: {action})")

        start_time = time.time()

        # 策略1: 尝试Healenium智能修复
        if self.healenium_config.enabled and self.healenium_adapter:
            result = self._try_healenium_heal(
                failed_selector, page_html, page_url, action
            )
            if result.success:
                self._record_healing(failed_selector, result, "healenium")
                return result

        # 策略2: 使用选择器管理器的回退策略
        if self.selector_manager:
            healed_selector = self.selector_manager.get_best_selector(
                failed_selector, page_html, action
            )
            if healed_selector and healed_selector != failed_selector:
                result = HealingResult(
                    success=True,
                    original_selector=failed_selector,
                    healed_selector=healed_selector,
                    method="fallback_strategy",
                    confidence=0.6,
                )
                self._record_healing(failed_selector, result, "fallback")
                return result

        # 策略3: 使用AI语义分析修复
        result = self._try_ai_heal(failed_selector, page_html, action, context)
        if result.success:
            self._record_healing(failed_selector, result, "ai")
            return result

        # 策略4: 本地回退策略
        result = self._try_local_fallback(failed_selector, page_html, action)
        if result.success:
            self._record_healing(failed_selector, result, "local")
            return result

        # 所有策略都失败
        elapsed = time.time() - start_time
        self.failed_heals += 1

        result = HealingResult(
            success=False,
            original_selector=failed_selector,
            method="exhausted",
            error=f"无法修复选择器，耗时: {elapsed:.2f}s",
        )

        self._record_healing(failed_selector, result, "failed")
        return result

    def _try_healenium_heal(
        self,
        selector: str,
        page_html: str,
        page_url: str,
        action: str,
    ) -> HealingResult:
        """使用Healenium进行修复"""
        try:
            if not self.healenium_adapter.is_available():
                logger.warning("Healenium服务不可用")
                return HealingResult(
                    success=False,
                    original_selector=selector,
                    method="healenium",
                    error="服务不可用",
                )

            score = self.healenium_adapter.find_alternative(
                selector, page_html, page_url, action
            )

            if score.score >= self.healenium_config.score_threshold:
                return HealingResult(
                    success=True,
                    original_selector=selector,
                    healed_selector=score.selector,
                    method="healenium",
                    confidence=score.score,
                )
            else:
                return HealingResult(
                    success=False,
                    original_selector=selector,
                    method="healenium",
                    error=f"评分过低: {score.score}",
                )

        except Exception as e:
            logger.warning(f"Healenium修复失败: {e}")
            return HealingResult(
                success=False,
                original_selector=selector,
                method="healenium",
                error=str(e),
            )

    def _try_ai_heal(
        self,
        selector: str,
        page_html: str,
        action: str,
        context: Optional[Dict[str, Any]],
    ) -> HealingResult:
        """使用AI进行语义分析修复"""
        try:
            # 构建提示词
            prompt = self._build_ai_heal_prompt(selector, page_html, action, context)

            # 调用LLM
            response = self.llm_client.generate(prompt)

            # 解析响应
            return self._parse_ai_response(selector, response)

        except Exception as e:
            logger.warning(f"AI修复失败: {e}")
            return HealingResult(
                success=False,
                original_selector=selector,
                method="ai",
                error=str(e),
            )

    def _build_ai_heal_prompt(
        self,
        selector: str,
        page_html: str,
        action: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """构建AI修复提示词"""
        # 提取页面关键元素用于分析
        elements = []

        # 简单解析HTML提取元素
        import re
        button_pattern = r'<button[^>]*>([^<]+)</button>'
        for match in re.finditer(button_pattern, page_html):
            text = match.group(1).strip()
            if text:
                elements.append(f"button: {text}")

        input_pattern = r'<input[^>]*placeholder="([^"]*)"'
        for match in re.finditer(input_pattern, page_html):
            placeholder = match.group(1).strip()
            if placeholder:
                elements.append(f"input: {placeholder}")

        elements_text = "\n".join(elements[:15])  # 限制元素数量

        prompt = f"""
你是一个自动化测试专家。原始的选择器 "{selector}" 失效了，
你需要分析页面元素，找出可以替代这个选择器的有效方案。

原始选择器: {selector}
要执行的操作: {action}

页面上的元素:
{elements_text}

请分析并给出一个或多个可以替代原选择器的CSS选择器或文本选择器。

请以JSON格式输出：
{{
    "best_selector": "最佳替代选择器",
    "confidence": 0.0-1.0的置信度,
    "alternatives": ["备选1", "备选2"],
    "reason": "选择这个选择器的理由"
}}

如果无法找到有效的替代选择器，返回空的best_selector。
"""
        return prompt

    def _parse_ai_response(self, original_selector: str, response: str) -> HealingResult:
        """解析AI响应"""
        try:
            # 尝试提取JSON
            if "{" in response and "}" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
                data = json.loads(json_str)

                healed_selector = data.get("best_selector", "")
                confidence = data.get("confidence", 0.5)
                alternatives = data.get("alternatives", [])

                if healed_selector and confidence >= 0.5:
                    return HealingResult(
                        success=True,
                        original_selector=original_selector,
                        healed_selector=healed_selector,
                        method="ai",
                        confidence=confidence,
                        alternatives=alternatives,
                    )

            return HealingResult(
                success=False,
                original_selector=original_selector,
                method="ai",
                error="无法解析AI响应",
            )

        except Exception as e:
            return HealingResult(
                success=False,
                original_selector=original_selector,
                method="ai",
                error=f"解析异常: {e}",
            )

    def _try_local_fallback(
        self,
        selector: str,
        page_html: str,
        action: str,
    ) -> HealingResult:
        """本地回退策略"""
        import re

        alternatives = []

        # 策略1: 基于文本内容的选择器
        if "." in selector or "#" in selector:
            # 提取class或id
            match = re.search(r'\.([a-zA-Z0-9_-]+)', selector)
            if match:
                class_name = match.group(1)
                # 尝试使用包含文本的选择器
                if "button" in action or "click" in action:
                    alternatives.append(f"button:has-text('{class_name}')")

        # 策略2: Ant Design通用选择器
        if "button" in selector.lower() or "btn" in selector.lower():
            alternatives.extend([
                ".ant-btn-primary",
                ".ant-btn",
                "button.ant-btn",
            ])

        if "input" in selector.lower():
            alternatives.extend([
                ".ant-input",
                "input.ant-input",
                "[class*='input']",
            ])

        if "modal" in selector.lower() or "dialog" in selector.lower():
            alternatives.extend([
                ".ant-modal-content",
                ".ant-modal",
            ])

        if "table" in selector.lower():
            alternatives.extend([
                ".ant-table",
                ".ant-table-tbody",
            ])

        # 策略3: 部分匹配
        for part in selector.replace(".", " ").replace("#", " ").split():
            if len(part) >= 4:
                alternatives.append(f"[class*='{part}']")
                alternatives.append(f"[id*='{part}']")

        # 尝试每个备选选择器
        for alt in alternatives:
            # 这里只返回第一个备选，实际使用时需要验证
            return HealingResult(
                success=True,
                original_selector=selector,
                healed_selector=alt,
                method="local_fallback",
                confidence=0.4,
                alternatives=alternatives,
            )

        return HealingResult(
            success=False,
            original_selector=selector,
            method="local_fallback",
            error="无法生成备选选择器",
        )

    def _record_healing(
        self,
        original_selector: str,
        result: HealingResult,
        method: str,
    ):
        """记录修复历史"""
        record = HealingRecord(
            original_selector=original_selector,
            healed_selector=result.healed_selector,
            healing_method=method,
            success=result.success,
            error=result.error,
        )

        self.healing_history.append(record)

        if result.success:
            self.successful_heals += 1
            logger.info(
                f"选择器修复成功: {original_selector} -> {result.healed_selector} "
                f"(方法: {method}, 置信度: {result.confidence:.2f})"
            )
        else:
            self.failed_heals += 1
            logger.warning(f"选择器修复失败: {original_selector} (方法: {method})")

    def get_statistics(self) -> Dict[str, Any]:
        """获取修复统计信息"""
        total = self.total_attempts
        success_rate = (
            self.successful_heals / total if total > 0 else 0.0
        )

        # 按方法统计
        method_stats = {}
        for record in self.healing_history:
            method = record.healing_method
            if method not in method_stats:
                method_stats[method] = {"total": 0, "success": 0}
            method_stats[method]["total"] += 1
            if record.success:
                method_stats[method]["success"] += 1

        return {
            "total_attempts": total,
            "successful_heals": self.successful_heals,
            "failed_heals": self.failed_heals,
            "success_rate": success_rate,
            "method_statistics": method_stats,
            "history_count": len(self.healing_history),
        }

    def get_cached_selector(self, original_selector: str) -> Optional[str]:
        """从缓存获取修复后的选择器"""
        for record in reversed(self.healing_history):
            if record.original_selector == original_selector and record.success:
                return record.healed_selector
        return None

    def clear_history(self):
        """清空修复历史"""
        self.healing_history.clear()
        self.total_attempts = 0
        self.successful_heals = 0
        self.failed_heals = 0
        logger.info("修复历史已清空")


class TestIssueAnalyzer:
    """
    测试问题分析器

    分析测试失败的原因，生成修复建议
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client

    def analyze_failure(
        self,
        test_name: str,
        error_message: str,
        page_html: str,
        screenshots: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        分析测试失败原因

        参数:
            test_name: 测试名称
            error_message: 错误信息
            page_html: 页面HTML
            screenshots: 截图列表(base64)

        返回:
            分析结果和建议
        """
        # 构建分析提示词
        prompt = self._build_analysis_prompt(
            test_name, error_message, page_html
        )

        if self.llm:
            # 调用AI分析
            response = self.llm.generate(prompt)
            return self._parse_analysis_response(response)
        else:
            # 简单的本地分析
            return self._local_analysis(error_message, page_html)

    def _build_analysis_prompt(
        self,
        test_name: str,
        error_message: str,
        page_html: str,
    ) -> str:
        """构建分析提示词"""
        # 提取页面关键信息
        import re
        buttons = re.findall(r'<button[^>]*>([^<]+)</button>', page_html)[:10]

        prompt = f"""
你是一个专业的测试工程师。请分析以下测试失败的原因。

测试名称: {test_name}
错误信息: {error_message}

页面按钮:
{chr(10).join(buttons)}

请给出:
1. 失败原因分析
2. 可能的解决方案
3. 建议的修复代码

请以JSON格式输出:
{{
    "root_cause": "根本原因",
    "analysis": "详细分析",
    "suggestions": ["建议1", "建议2"],
    "fix_code": "修复代码(如果有)"
}}
"""
        return prompt

    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """解析分析响应"""
        try:
            if "{" in response and "}" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
                return json.loads(json_str)
        except Exception:
            pass

        return {
            "analysis": response,
            "suggestions": ["请检查错误信息"],
        }

    def _local_analysis(
        self,
        error_message: str,
        page_html: str,
    ) -> Dict[str, Any]:
        """本地简单分析"""
        suggestions = []

        if "timeout" in error_message.lower():
            suggestions.append("增加等待时间")
            suggestions.append("检查页面是否正确加载")

        if "not found" in error_message.lower() or "找不到" in error_message:
            suggestions.append("检查选择器是否正确")
            suggestions.append("可能是页面结构发生变化")

        if "click" in error_message.lower():
            suggestions.append("元素可能被遮挡")
            suggestions.append("尝试使用force: true")

        return {
            "analysis": "基于错误信息的自动分析",
            "suggestions": suggestions,
        }