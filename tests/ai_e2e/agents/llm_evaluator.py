"""LLM 语义断言评估器 — 使用 LLM 进行语义级别的页面状态断言."""

from __future__ import annotations

import json

from core.logging_config import logger
from llm.qwen_client import QwenClient
from tests.ai_e2e.schemas.test_case_schema import (
    AssertionResult,
    ElementRef,
    RuleAssertion,
    TestAssertion,
)
from tests.ai_e2e.tools.snapshot_resolver import SnapshotResolver

# LLM 断言评估的 system prompt
_EVAL_SYSTEM_PROMPT = """你是一个专业的 UI 自动化测试评估专家。

根据用户提供的断言描述和当前页面的 a11y 快照，判断断言是否通过。

请严格按 JSON 格式返回，不要包含其他内容：
{"passed": true/false, "reason": "判断理由的简要说明", "confidence": 0.0-1.0}

- passed: 断言是否通过
- reason: 基于快照内容的判断理由
- confidence: 你对判断的确信程度（0.0 完全不确定，1.0 完全确定）"""


class LLMEvaluator:
    """混合断言评估器 — 支持规则断言、LLM 语义断言、混合模式.

    - rule_based: 在快照上做确定性文本匹配，零 token 开销
    - llm_judged: 调用 LLM 进行语义判断
    - hybrid: 规则优先，不确定时 LLM 辅助
    """

    def __init__(
        self,
        qwen_client: QwenClient,
        resolver: SnapshotResolver,
        confidence_threshold: float = 0.7,
        temperature: float = 0.1,
    ):
        """初始化评估器.

        Args:
            qwen_client: LLM 客户端实例
            resolver: 快照解析器
            confidence_threshold: LLM 断言置信度阈值，低于此值标记为 inconclusive
            temperature: LLM 温度参数
        """
        self.client = qwen_client
        self.resolver = resolver
        self.confidence_threshold = confidence_threshold
        self.temperature = temperature
        self._total_tokens: int = 0

    @property
    def total_tokens_used(self) -> int:
        """累计消耗的 token 数."""
        return self._total_tokens

    async def evaluate(
        self,
        assertion: TestAssertion,
        page_snapshot: str,
        current_url: str = "",
        assertion_index: int = 0,
    ) -> AssertionResult:
        """评估单个断言.

        Args:
            assertion: 断言定义
            page_snapshot: 当前页面 a11y 快照
            current_url: 当前页面 URL
            assertion_index: 断言序号

        Returns:
            断言执行结果
        """
        if assertion.type == "rule_based":
            return self._evaluate_rule(
                assertion.rule_assertion, page_snapshot, current_url, assertion_index
            )
        elif assertion.type == "llm_judged":
            return await self._evaluate_llm(
                assertion.llm_assertion or "", page_snapshot, assertion_index
            )
        elif assertion.type == "hybrid":
            return await self._evaluate_hybrid(
                assertion, page_snapshot, current_url, assertion_index
            )
        else:
            return AssertionResult(
                assertion_index=assertion_index,
                passed=False,
                reason=f"不支持的断言类型: {assertion.type}",
            )

    def _evaluate_rule(
        self,
        rule: RuleAssertion | None,
        snapshot: str,
        current_url: str,
        index: int,
    ) -> AssertionResult:
        """执行规则断言 — 确定性验证."""
        if not rule:
            return AssertionResult(assertion_index=index, passed=False, reason="规则断言定义缺失")

        if rule.check == "element_visible":
            return self._check_element_visible(rule.element, snapshot, index)
        elif rule.check == "element_hidden":
            return self._check_element_hidden(rule.element, snapshot, index)
        elif rule.check == "text_contains":
            return self._check_text_contains(snapshot, str(rule.expected or ""), index)
        elif rule.check == "url_matches":
            pattern = str(rule.expected or "")
            matched = pattern in current_url
            return AssertionResult(
                assertion_index=index,
                passed=matched,
                reason=f"URL '{current_url}' {'包含' if matched else '不包含'} '{pattern}'",
            )
        elif rule.check == "element_count":
            return self._check_element_count(rule.element, snapshot, rule.expected, index)

        return AssertionResult(
            assertion_index=index,
            passed=False,
            reason=f"不支持的规则检查类型: {rule.check}",
        )

    def _check_element_visible(
        self, element: ElementRef | None, snapshot: str, index: int
    ) -> AssertionResult:
        """检查元素在快照中是否可见."""
        if not element:
            return AssertionResult(assertion_index=index, passed=False, reason="未指定目标元素")
        uid = self.resolver.resolve(snapshot, element)
        found = uid is not None
        return AssertionResult(
            assertion_index=index,
            passed=found,
            reason=f"元素 '{element.name}' {'存在' if found else '不存在'}于快照中"
            + (f" (uid={uid})" if uid else ""),
        )

    def _check_element_hidden(
        self, element: ElementRef | None, snapshot: str, index: int
    ) -> AssertionResult:
        """检查元素在快照中不可见."""
        if not element:
            return AssertionResult(
                assertion_index=index, passed=True, reason="未指定目标元素，视为通过"
            )
        uid = self.resolver.resolve(snapshot, element)
        hidden = uid is None
        return AssertionResult(
            assertion_index=index,
            passed=hidden,
            reason=f"元素 '{element.name}' {'不存在' if hidden else '仍存在'}于快照中",
        )

    def _check_text_contains(self, snapshot: str, expected: str, index: int) -> AssertionResult:
        """检查快照文本中是否包含预期内容."""
        found = expected in snapshot
        return AssertionResult(
            assertion_index=index,
            passed=found,
            reason=f"快照{'包含' if found else '不包含'}文本 '{expected}'",
        )

    def _check_element_count(
        self,
        element: ElementRef | None,
        snapshot: str,
        expected: str | int | None,
        index: int,
    ) -> AssertionResult:
        """检查匹配元素的数量."""
        if not element:
            return AssertionResult(assertion_index=index, passed=False, reason="未指定目标元素")
        matches = self.resolver.find_elements_by_text(snapshot, element.name)
        if element.role:
            matches = [m for m in matches if m.role == element.role]
        actual_count = len(matches)
        expected_count = int(expected) if expected is not None else 0
        passed = actual_count == expected_count
        return AssertionResult(
            assertion_index=index,
            passed=passed,
            reason=f"元素 '{element.name}' 数量: 期望 {expected_count}, 实际 {actual_count}",
        )

    async def _evaluate_llm(
        self, assertion_text: str, snapshot: str, index: int
    ) -> AssertionResult:
        """调用 LLM 进行语义断言评估."""
        user_prompt = f"断言描述：{assertion_text}\n\n" f"当前页面 a11y 快照：\n{snapshot}"

        try:
            result = await self.client.chat(
                prompt=user_prompt,
                system=_EVAL_SYSTEM_PROMPT,
                temperature=self.temperature,
                max_tokens=256,
            )
            content = result.get("content", "")
            usage = result.get("usage", {})
            self._total_tokens += usage.get("total_tokens", 0)

            # 处理 LLM 返回的 markdown 代码块包裹
            content = self._extract_json_text(content)
            parsed = json.loads(content)
            passed = bool(parsed.get("passed", False))
            reason = str(parsed.get("reason", ""))
            confidence = float(parsed.get("confidence", 0.5))

            # 置信度低于阈值时标记为不确定
            if not passed and confidence < self.confidence_threshold:
                return AssertionResult(
                    assertion_index=index,
                    passed=False,
                    reason=f"[inconclusive] {reason}",
                    confidence=confidence,
                )

            return AssertionResult(
                assertion_index=index,
                passed=passed,
                reason=reason,
                confidence=confidence,
            )

        except json.JSONDecodeError:
            logger.warning(f"LLM 断言返回非 JSON: {content[:200]}")
            return AssertionResult(
                assertion_index=index,
                passed=False,
                reason="LLM 返回格式异常",
                confidence=0.0,
            )
        except Exception as e:
            logger.error(f"LLM 断言调用失败: {e}")
            return AssertionResult(
                assertion_index=index,
                passed=False,
                reason=f"LLM 调用异常: {e}",
                confidence=0.0,
            )

    @staticmethod
    def _extract_json_text(text: str) -> str:
        """从 LLM 返回文本中提取纯 JSON（处理 markdown 代码块包裹）.

        Args:
            text: LLM 返回的原始文本，可能被 ```json ... ``` 包裹

        Returns:
            去除 markdown 包裹后的纯 JSON 文本
        """
        text = text.strip()
        if '```json' in text:
            start = text.index('```json') + 7
            end = text.index('```', start)
            return text[start:end].strip()
        if '```' in text:
            start = text.index('```') + 3
            end = text.index('```', start)
            return text[start:end].strip()
        return text

    async def _evaluate_hybrid(
        self,
        assertion: TestAssertion,
        snapshot: str,
        current_url: str,
        index: int,
    ) -> AssertionResult:
        """混合断言：规则优先，不确定时 LLM 辅助."""
        # 先执行规则断言
        if assertion.rule_assertion:
            rule_result = self._evaluate_rule(
                assertion.rule_assertion, snapshot, current_url, index
            )
            if rule_result.passed:
                return rule_result
            # 规则失败但有 LLM 断言描述时，用 LLM 辅助判断
            if assertion.llm_assertion:
                return await self._evaluate_llm(assertion.llm_assertion, snapshot, index)
            return rule_result

        # 没有规则断言时直接用 LLM
        if assertion.llm_assertion:
            return await self._evaluate_llm(assertion.llm_assertion, snapshot, index)

        return AssertionResult(
            assertion_index=index,
            passed=False,
            reason="混合断言缺少规则和 LLM 断言定义",
        )
