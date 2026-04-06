"""UI 测试编排器 — 加载 JSON 用例，驱动 MCP 执行，评估结果.

串联 MCPExecutor、SelfHealer、LLMEvaluator 三个组件，
实现 TestCase 从加载到执行到评估的完整流程。
"""

from __future__ import annotations

import asyncio
import time

from core.logging_config import logger
from tests.ai_e2e.agents.llm_evaluator import LLMEvaluator
from tests.ai_e2e.schemas.test_case_schema import (
    AssertionResult,
    StepResult,
    SuiteResult,
    TestCase,
    TestCaseResult,
    TestSuite,
)
from tests.ai_e2e.tools.mcp_executor import MCPExecutor


class UITestOrchestrator:
    """UI 测试编排器 — 协调 MCP 执行器和 LLM 评估器完成测试用例.

    完整流程：
    1. 检查前置条件
    2. 按序执行 steps（MCPExecutor）
    3. 执行 assertions（LLMEvaluator）
    4. 执行 cleanup steps
    5. 聚合 TestCaseResult
    """

    def __init__(
        self,
        executor: MCPExecutor,
        evaluator: LLMEvaluator,
        case_timeout: int = 120,
        enable_screenshot_on_failure: bool = True,
    ):
        """初始化编排器.

        Args:
            executor: MCP 执行器
            evaluator: LLM 断言评估器
            case_timeout: 单个用例超时（秒）
            enable_screenshot_on_failure: 失败时是否自动截图
        """
        self.executor = executor
        self.evaluator = evaluator
        self.case_timeout = case_timeout
        self.enable_screenshot_on_failure = enable_screenshot_on_failure

    async def run_test_case(self, test_case: TestCase) -> TestCaseResult:
        """执行单个测试用例.

        Args:
            test_case: 测试用例定义

        Returns:
            测试用例执行结果
        """
        start_time = time.monotonic()
        step_results: list[StepResult] = []
        assertion_results: list[AssertionResult] = []
        screenshots: list[str] = []

        try:
            # 带超时执行
            result = await asyncio.wait_for(
                self._run_case_inner(test_case, step_results, assertion_results, screenshots),
                timeout=self.case_timeout,
            )
            return result
        except asyncio.TimeoutError:
            duration = int((time.monotonic() - start_time) * 1000)
            logger.error(f"测试用例超时: {test_case.name} ({self.case_timeout}s)")
            if self.enable_screenshot_on_failure:
                screenshot = await self.executor.take_failure_screenshot()
                screenshots.append(screenshot)
            return TestCaseResult(
                test_case_id=test_case.id,
                status="error",
                step_results=step_results,
                assertion_results=assertion_results,
                failure_reason=f"用例超时 ({self.case_timeout}s)",
                screenshots=screenshots,
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start_time) * 1000)
            logger.error(f"测试用例异常: {test_case.name} - {e}")
            return TestCaseResult(
                test_case_id=test_case.id,
                status="error",
                step_results=step_results,
                assertion_results=assertion_results,
                failure_reason=str(e),
                screenshots=screenshots,
                duration_ms=duration,
            )

    async def _run_case_inner(
        self,
        test_case: TestCase,
        step_results: list[StepResult],
        assertion_results: list[AssertionResult],
        screenshots: list[str],
    ) -> TestCaseResult:
        """测试用例内部执行逻辑."""
        start_time = time.monotonic()
        has_failure = False

        # === Phase 1: 执行测试步骤 ===
        for i, step in enumerate(test_case.steps):
            logger.info(f"[{test_case.id}] 步骤 {i + 1}/{len(test_case.steps)}: {step.description}")

            # assert_* 步骤转交 Evaluator 处理（始终刷新快照以获取最新状态）
            if step.action.startswith("assert_"):
                snapshot = await self.executor.refresh_snapshot()
                ar = await self._evaluate_step_assertion(step, snapshot, i)
                assertion_results.append(ar)
                sr = StepResult(
                    step_index=i,
                    status="passed" if ar.passed else "failed",
                    error=None if ar.passed else ar.reason,
                    duration_ms=0,
                )
                step_results.append(sr)
                if not ar.passed and step.action == "assert_visible":
                    # 关键断言失败，中止后续步骤
                    has_failure = True
                    break
                continue

            # 普通步骤通过 MCPExecutor 执行
            result = await self.executor.execute_step(step)
            result.step_index = i
            step_results.append(result)

            if result.status == "failed":
                has_failure = True
                logger.warning(f"步骤失败: {step.description} - {result.error}")
                if self.enable_screenshot_on_failure:
                    screenshot = await self.executor.take_failure_screenshot()
                    screenshots.append(screenshot)
                break  # 步骤失败时中止后续步骤

            if result.status == "healed":
                logger.info(f"步骤自愈成功: {step.description} ({result.healed_by})")

            # 步骤间短暂等待，让页面渲染完成
            await asyncio.sleep(0.3)

        # === Phase 2: 执行断言列表 ===
        if not has_failure:
            # 刷新快照用于断言评估
            snapshot = await self.executor.refresh_snapshot()
            for j, assertion in enumerate(test_case.assertions):
                ar = await self.evaluator.evaluate(
                    assertion=assertion,
                    page_snapshot=snapshot,
                    assertion_index=j,
                )
                assertion_results.append(ar)
                if not ar.passed and assertion.severity == "critical":
                    has_failure = True

        # === Phase 3: 执行清理步骤 ===
        if test_case.cleanup:
            for cleanup_step in test_case.cleanup:
                try:
                    await self.executor.execute_step(cleanup_step)
                except Exception as cleanup_err:
                    logger.warning(f"清理步骤失败: {cleanup_err}")

        # === Phase 4: 聚合结果 ===
        duration = int((time.monotonic() - start_time) * 1000)
        status = self._determine_status(step_results, assertion_results, has_failure)

        # 计算 LLM token 使用
        healer_tokens = getattr(self.executor, "self_healer", None)
        healer_token_count = healer_tokens.total_tokens_used if healer_tokens else 0
        eval_tokens = self.evaluator.total_tokens_used
        total_llm_tokens = healer_token_count + eval_tokens

        failure_reason = None
        if status != "passed":
            failure_reason = self._extract_failure_reason(step_results, assertion_results)

        return TestCaseResult(
            test_case_id=test_case.id,
            status=status,
            step_results=step_results,
            assertion_results=assertion_results,
            failure_reason=failure_reason,
            screenshots=screenshots,
            llm_token_usage=total_llm_tokens,
            duration_ms=duration,
        )

    async def _evaluate_step_assertion(self, step, snapshot: str, index: int) -> AssertionResult:
        """将 assert_* 类型的步骤转换为断言评估.

        把 step 的 action/element/value 转换为对应的规则断言。
        """
        from tests.ai_e2e.schemas.test_case_schema import (
            RuleAssertion,
            TestAssertion,
        )

        if step.action == "assert_visible" and step.element:
            assertion = TestAssertion(
                type="rule_based",
                rule_assertion=RuleAssertion(check="element_visible", element=step.element),
            )
        elif step.action == "assert_text":
            assertion = TestAssertion(
                type="rule_based",
                rule_assertion=RuleAssertion(check="text_contains", expected=step.value),
            )
        elif step.action == "assert_url":
            assertion = TestAssertion(
                type="rule_based",
                rule_assertion=RuleAssertion(check="url_matches", expected=step.value),
            )
        elif step.action == "assert_count" and step.element:
            assertion = TestAssertion(
                type="rule_based",
                rule_assertion=RuleAssertion(
                    check="element_count",
                    element=step.element,
                    expected=step.value,
                ),
            )
        else:
            # 不支持的 assert 类型，通过 LLM 评估
            assertion = TestAssertion(
                type="llm_judged",
                llm_assertion=step.description,
            )

        return await self.evaluator.evaluate(
            assertion=assertion,
            page_snapshot=snapshot,
            assertion_index=index,
        )

    def _determine_status(
        self,
        step_results: list[StepResult],
        assertion_results: list[AssertionResult],
        has_failure: bool,
    ) -> str:
        """根据步骤和断言结果确定最终状态."""
        if has_failure:
            return "failed"

        # 检查是否有 inconclusive 的断言
        has_inconclusive = any(
            not ar.passed and ar.confidence < self.evaluator.confidence_threshold
            for ar in assertion_results
        )
        if has_inconclusive:
            return "inconclusive"

        # 检查是否有失败的断言
        if any(not ar.passed for ar in assertion_results):
            return "failed"

        return "passed"

    def _extract_failure_reason(
        self,
        step_results: list[StepResult],
        assertion_results: list[AssertionResult],
    ) -> str:
        """提取失败原因摘要."""
        reasons: list[str] = []

        for sr in step_results:
            if sr.status == "failed" and sr.error:
                reasons.append(f"步骤{sr.step_index + 1}: {sr.error}")

        for ar in assertion_results:
            if not ar.passed:
                reasons.append(f"断言{ar.assertion_index + 1}: {ar.reason}")

        return "; ".join(reasons) if reasons else "未知原因"

    async def run_suite(self, suite: TestSuite) -> SuiteResult:
        """执行整个测试套件.

        Args:
            suite: 测试套件定义

        Returns:
            套件执行结果
        """
        start_time = time.monotonic()
        case_results: list[TestCaseResult] = []
        passed = failed = error = inconclusive = 0

        for case in suite.test_cases:
            logger.info(f"=== 执行测试用例: {case.name} ({case.id}) ===")
            result = await self.run_test_case(case)
            case_results.append(result)

            if result.status == "passed":
                passed += 1
            elif result.status == "failed":
                failed += 1
            elif result.status == "error":
                error += 1
            else:
                inconclusive += 1

            logger.info(f"=== 用例结果: {result.status} ({result.duration_ms}ms) ===")

        total_duration = int((time.monotonic() - start_time) * 1000)
        total_tokens = sum(cr.llm_token_usage for cr in case_results)

        return SuiteResult(
            suite_name=suite.suite_name,
            total=len(suite.test_cases),
            passed=passed,
            failed=failed,
            error=error,
            inconclusive=inconclusive,
            case_results=case_results,
            total_llm_tokens=total_tokens,
            total_duration_ms=total_duration,
        )
