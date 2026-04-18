"""测试报告生成器 — 将 SuiteResult 输出为结构化 JSON 报告."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tests.ai_e2e.schemas.test_case_schema import SuiteResult


class TestReportGenerator:
    """将测试套件执行结果输出为 JSON 报告文件."""

    __test__ = False

    def __init__(self, report_dir: str = "ai_test_reports/results"):
        """初始化报告生成器.

        Args:
            report_dir: 报告输出目录
        """
        self.report_dir = Path(report_dir)

    def generate(self, suite_result: SuiteResult) -> str:
        """生成 JSON 报告文件.

        Args:
            suite_result: 套件执行结果

        Returns:
            报告文件路径
        """
        self.report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{suite_result.suite_name}_{timestamp}.json"
        report_path = self.report_dir / filename

        # 构建报告数据
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "suite_name": suite_result.suite_name,
                "total": suite_result.total,
                "passed": suite_result.passed,
                "failed": suite_result.failed,
                "error": suite_result.error,
                "inconclusive": suite_result.inconclusive,
                "pass_rate": (
                    f"{suite_result.passed / suite_result.total * 100:.1f}%"
                    if suite_result.total > 0
                    else "N/A"
                ),
                "total_llm_tokens": suite_result.total_llm_tokens,
                "total_duration_ms": suite_result.total_duration_ms,
            },
            "case_results": [cr.model_dump() for cr in suite_result.case_results],
        }

        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return str(report_path)

    def print_summary(self, suite_result: SuiteResult) -> None:
        """在控制台打印结果摘要."""
        total = suite_result.total
        print(f"\n{'=' * 60}")
        print(f"  AI E2E 测试报告: {suite_result.suite_name}")
        print(f"{'=' * 60}")
        print(f"  总用例: {total}")
        print(f"  通过:   {suite_result.passed}")
        print(f"  失败:   {suite_result.failed}")
        print(f"  错误:   {suite_result.error}")
        print(f"  不确定: {suite_result.inconclusive}")
        if total > 0:
            print(f"  通过率: {suite_result.passed / total * 100:.1f}%")
        print(f"  LLM Tokens: {suite_result.total_llm_tokens}")
        print(f"  耗时: {suite_result.total_duration_ms}ms")
        print(f"{'=' * 60}")

        # 打印失败用例详情
        failed_cases = [cr for cr in suite_result.case_results if cr.status != "passed"]
        if failed_cases:
            print("\n  失败用例:")
            for cr in failed_cases:
                print(f"    [{cr.status}] {cr.test_case_id}: {cr.failure_reason}")
        print()
