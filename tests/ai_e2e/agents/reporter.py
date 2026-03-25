"""
测试报告生成器

生成AI测试执行报告，支持多种格式输出

作者: Qoder
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests.ai_e2e.config import TestConfig
from tests.ai_e2e.agents.test_executor import ExecutionResult
from tests.ai_e2e.selectors.healenium_adapter import HealeniumAdapter

logger = logging.getLogger(__name__)


@dataclass
class TestReport:
    """测试报告"""
    timestamp: str
    mode: str
    success: bool
    execution_time: float
    goal: str = ""
    total_steps: int = 0
    successful_steps: int = 0
    healed_count: int = 0
    actions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TestReporter:
    """
    测试报告生成器

    生成详细的测试执行报告，包括统计信息、趋势分析等
    """

    def __init__(self, config: Optional[TestConfig] = None):
        """
        初始化报告生成器

        参数:
            config: 测试配置
        """
        self.config = config or TestConfig()
        self.report_dir = self.config.report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        mode: str,
        goal: str,
        result: ExecutionResult,
        execution_time: float,
        additional_info: Optional[Dict[str, Any]] = None,
    ) -> TestReport:
        """
        生成测试报告

        参数:
            mode: 测试模式
            goal: 测试目标
            result: 执行结果
            execution_time: 执行时间
            additional_info: 额外信息

        返回:
            TestReport: 测试报告
        """
        report = TestReport(
            timestamp=datetime.now().isoformat(),
            mode=mode,
            success=result.success,
            goal=goal,
            execution_time=execution_time,
            total_steps=len(result.actions_executed),
            successful_steps=sum(
                1 for a in result.actions_executed
                if a.action_type.value != "stop"
            ),
            actions=[
                {
                    "type": a.action_type.value,
                    "target": a.target,
                    "value": a.value,
                    "reason": a.reason,
                    "confidence": a.confidence,
                }
                for a in result.actions_executed
            ],
            errors=[result.error] if result.error else [],
        )

        # 添加额外信息
        if additional_info:
            report.metadata.update(additional_info)

        return report

    def save_report(self, report: TestReport, format: str = "json") -> Path:
        """
        保存报告

        参数:
            report: 测试报告
            format: 报告格式 (json, html)

        返回:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if format == "json":
            return self._save_json_report(report, timestamp)
        elif format == "html":
            return self._save_html_report(report, timestamp)
        else:
            raise ValueError(f"不支持的格式: {format}")

    def _save_json_report(self, report: TestReport, timestamp: str) -> Path:
        """保存JSON格式报告"""
        filename = f"test_report_{timestamp}.json"
        filepath = self.report_dir / filename

        report_dict = {
            "timestamp": report.timestamp,
            "mode": report.mode,
            "success": report.success,
            "goal": report.goal,
            "execution_time": report.execution_time,
            "total_steps": report.total_steps,
            "successful_steps": report.successful_steps,
            "healed_count": report.healed_count,
            "actions": report.actions,
            "errors": report.errors,
            "metadata": report.metadata,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON报告已保存: {filepath}")
        return filepath

    def _save_html_report(self, report: TestReport, timestamp: str) -> Path:
        """保存HTML格式报告"""
        filename = f"test_report_{timestamp}.html"
        filepath = self.report_dir / filename

        html_content = self._generate_html(report)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"HTML报告已保存: {filepath}")
        return filepath

    def _generate_html(self, report: TestReport) -> str:
        """生成HTML报告"""
        # 状态样式
        status_color = "green" if report.success else "red"
        status_text = "成功" if report.success else "失败"

        # 构建操作表格
        actions_rows = ""
        for i, action in enumerate(report.actions, 1):
            actions_rows += f"""
            <tr>
                <td>{i}</td>
                <td>{action['type']}</td>
                <td>{action['target']}</td>
                <td>{action.get('value', '-')}</td>
                <td>{action.get('reason', '-')[:50]}</td>
                <td>{action.get('confidence', 0):.2f}</td>
            </tr>
            """

        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI E2E 测试报告</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            color: white;
            font-weight: bold;
            background: {status_color};
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .error {{
            background: #fff5f5;
            color: #c00;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AI E2E 测试报告</h1>
        <p>测试目标: {report.goal}</p>
        <p>时间: {report.timestamp}</p>
        <span class="status">{status_text}</span>
    </div>

    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{report.total_steps}</div>
            <div class="stat-label">总步骤</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report.successful_steps}</div>
            <div class="stat-label">成功步骤</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report.healed_count}</div>
            <div class="stat-label">自愈次数</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report.execution_time:.2f}s</div>
            <div class="stat-label">执行时间</div>
        </div>
    </div>

    <h2>执行步骤详情</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>操作类型</th>
                <th>目标</th>
                <th>值</th>
                <th>理由</th>
                <th>置信度</th>
            </tr>
        </thead>
        <tbody>
            {actions_rows}
        </tbody>
    </table>
"""

        # 添加错误信息
        if report.errors:
            html += f"""
    <div class="error">
        <h3>错误信息</h3>
        <pre>{chr(10).join(report.errors)}</pre>
    </div>
"""

        html += """
</body>
</html>
"""
        return html

    def generate_summary_report(self, report_paths: List[Path]) -> Dict[str, Any]:
        """
        生成汇总报告

        参数:
            report_paths: 报告文件路径列表

        返回:
            汇总统计数据
        """
        total_runs = 0
        successful_runs = 0
        total_time = 0.0

        for path in report_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    total_runs += 1
                    if data.get("success"):
                        successful_runs += 1
                    total_time += data.get("execution_time", 0)
            except Exception as e:
                logger.warning(f"读取报告失败 {path}: {e}")

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "success_rate": successful_runs / total_runs if total_runs > 0 else 0,
            "total_time": total_time,
            "average_time": total_time / total_runs if total_runs > 0 else 0,
        }