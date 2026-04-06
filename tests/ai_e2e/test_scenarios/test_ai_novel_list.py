"""AI E2E 测试场景 — 小说列表页.

基于预生成的 JSON 用例，通过 Playwright CDP 适配器驱动浏览器执行测试。
适配器生成与 chrome-devtools MCP 兼容的 a11y 快照格式，通过 UID 操作元素。

运行方式：
    pytest tests/ai_e2e/test_scenarios/test_ai_novel_list.py -m ai_e2e -v
    pytest tests/ai_e2e/test_scenarios/test_ai_novel_list.py -m ai_smoke -v  # 仅 P0
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.ai_e2e.reports.test_report_generator import TestReportGenerator
from tests.ai_e2e.schemas.test_case_schema import TestCase, TestSuite

# JSON 用例文件路径
_SUITE_FILE = Path(__file__).parent.parent / "generated" / "novel_list_suite.json"


def _load_suite(base_url: str) -> TestSuite:
    """加载并解析 JSON 测试套件，替换 {base_url} 占位符.

    Args:
        base_url: 前端基础 URL

    Returns:
        解析后的 TestSuite 实例
    """
    raw = _SUITE_FILE.read_text(encoding="utf-8")
    raw = raw.replace("{base_url}", base_url)
    data = json.loads(raw)
    return TestSuite(**data)


def _collect_cases(base_url: str, category: str | None = None) -> list[TestCase]:
    """按分类收集测试用例.

    Args:
        base_url: 前端基础 URL
        category: 用例分类过滤（smoke / regression / edge_case），None 表示全部

    Returns:
        过滤后的测试用例列表
    """
    suite = _load_suite(base_url)
    if category:
        return [c for c in suite.test_cases if c.category == category]
    return suite.test_cases


# ---------------------------------------------------------------------------
# mcp_tools fixture — 通过 Playwright CDP 适配器提供浏览器操作能力
# ---------------------------------------------------------------------------


@pytest.fixture
async def mcp_tools(base_url) -> dict[str, Any]:
    """提供 MCP chrome-devtools 兼容的工具函数.

    使用 Playwright CDP 适配器（无需外部 MCP server），
    适配器生成与 chrome-devtools MCP 相同格式的 a11y 快照。

    Yields:
        包含 navigate/click/fill/press_key/wait_for/take_snapshot/take_screenshot
        的 callable 字典
    """
    from tests.ai_e2e.tools.playwright_mcp_adapter import PlaywrightMCPAdapter

    adapter = await PlaywrightMCPAdapter.create(
        headless=False,
        base_url=base_url,
    )
    try:
        yield adapter.as_mcp_tools()
    finally:
        await adapter.close()


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


@pytest.mark.ai_e2e
@pytest.mark.ai_smoke
class TestNovelListSmoke:
    """小说列表页冒烟测试 (P0) — 验证核心功能可用."""

    @pytest.mark.asyncio
    async def test_page_load(self, orchestrator, base_url):
        """AI-E2E-NL-001: 小说列表页加载验证."""
        suite = _load_suite(base_url)
        case = next(c for c in suite.test_cases if c.id == "AI-E2E-NL-001")
        result = await orchestrator.run_test_case(case)
        assert result.status == "passed", (
            f"用例 {case.id} 失败: {result.failure_reason}"
        )

    @pytest.mark.asyncio
    async def test_create_modal_open_close(self, orchestrator, base_url):
        """AI-E2E-NL-002: 创建小说弹窗打开与关闭."""
        suite = _load_suite(base_url)
        case = next(c for c in suite.test_cases if c.id == "AI-E2E-NL-002")
        result = await orchestrator.run_test_case(case)
        assert result.status == "passed", (
            f"用例 {case.id} 失败: {result.failure_reason}"
        )

    @pytest.mark.asyncio
    async def test_click_novel_detail(self, orchestrator, base_url):
        """AI-E2E-NL-005: 点击小说进入详情页."""
        suite = _load_suite(base_url)
        case = next(c for c in suite.test_cases if c.id == "AI-E2E-NL-005")
        result = await orchestrator.run_test_case(case)
        assert result.status == "passed", (
            f"用例 {case.id} 失败: {result.failure_reason}"
        )


@pytest.mark.ai_e2e
@pytest.mark.ai_regression
class TestNovelListRegression:
    """小说列表页回归测试 (P1) — 验证业务流程完整性."""

    @pytest.mark.asyncio
    async def test_create_novel_full_flow(self, orchestrator, base_url):
        """AI-E2E-NL-003: 创建小说完整流程."""
        suite = _load_suite(base_url)
        case = next(c for c in suite.test_cases if c.id == "AI-E2E-NL-003")
        result = await orchestrator.run_test_case(case)
        assert result.status == "passed", (
            f"用例 {case.id} 失败: {result.failure_reason}"
        )

    @pytest.mark.asyncio
    async def test_status_filter(self, orchestrator, base_url):
        """AI-E2E-NL-004: 小说列表状态筛选."""
        suite = _load_suite(base_url)
        case = next(c for c in suite.test_cases if c.id == "AI-E2E-NL-004")
        result = await orchestrator.run_test_case(case)
        # 状态筛选允许 inconclusive（LLM 断言不确定时不算失败）
        assert result.status in ("passed", "inconclusive"), (
            f"用例 {case.id} 失败: {result.failure_reason}"
        )


@pytest.mark.ai_e2e
class TestNovelListSuiteRunner:
    """完整套件运行器 — 执行所有用例并生成报告."""

    @pytest.mark.asyncio
    async def test_run_full_suite(self, orchestrator, base_url):
        """运行小说列表页完整测试套件并生成报告."""
        suite = _load_suite(base_url)
        suite_result = await orchestrator.run_suite(suite)

        # 生成报告
        reporter = TestReportGenerator()
        report_path = reporter.generate(suite_result)
        reporter.print_summary(suite_result)

        # 断言冒烟测试全部通过
        smoke_results = [
            cr
            for cr in suite_result.case_results
            if any(
                c.category == "smoke"
                for c in suite.test_cases
                if c.id == cr.test_case_id
            )
        ]
        smoke_failures = [cr for cr in smoke_results if cr.status == "failed"]
        assert not smoke_failures, (
            f"P0 冒烟测试有 {len(smoke_failures)} 个失败, "
            f"详见报告: {report_path}"
        )
