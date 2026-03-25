#!/usr/bin/env python3
"""
AI增强型E2E测试运行器

本地自动化测试执行脚本
支持：AI自动执行、测试生成、自愈机制

使用方法:
    python scripts/ai_e2e_runner.py --mode autonomous --goal "测试小说创建功能"
    python scripts/ai_e2e_runner.py --mode generate --feature "小说管理"
    python scripts/ai_e2e_runner.py --mode heal --test-file tests/e2e/test_scenarios/test_creation_flow.py

作者: Qoder
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.ai_e2e.config import TestConfig, default_config
from tests.ai_e2e.agents.test_executor import AITestExecutor
from tests.ai_e2e.agents.test_generator import TestGenerator, TestSpecification, create_spec_from_description
from tests.ai_e2e.agents.self_healer import SelfHealer
from tests.ai_e2e.runners.hybrid_runner import HybridRunner, create_action

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIE2ERunner:
    """
    AI E2E测试运行器主类

    整合所有AI测试功能，提供统一的命令行接口
    """

    def __init__(self, config: TestConfig = None):
        """
        初始化运行器

        参数:
            config: 测试配置
        """
        self.config = config or default_config
        self.config.report_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"AI E2E Runner 初始化")
        logger.info(f"测试目标: {self.config.base_url}")

    def run_autonomous(
        self,
        goal: str,
        start_url: str = "",
        max_steps: int = 50,
    ) -> dict:
        """
        运行AI自主测试

        参数:
            goal: 测试目标描述
            start_url: 起始URL路径
            max_steps: 最大执行步数

        返回:
            测试执行结果
        """
        logger.info("=" * 60)
        logger.info(f"开始AI自主测试: {goal}")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            # 创建AI测试执行器
            executor = AITestExecutor(self.config)

            # 执行测试
            with executor:
                result = executor.execute_autonomous(
                    goal=goal,
                    start_url=start_url,
                    max_steps=max_steps,
                )

            execution_time = time.time() - start_time

            # 生成报告
            report = self._generate_report(
                mode="autonomous",
                goal=goal,
                result=result,
                execution_time=execution_time,
            )

            # 保存报告
            self._save_report(report)

            # 打印摘要
            self._print_summary(report)

            return report

        except Exception as e:
            logger.error(f"AI测试执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "mode": "autonomous",
                "goal": goal,
            }

    def run_generation(
        self,
        feature: str,
        page_url: str = "/novels",
        test_goals: list = None,
    ) -> dict:
        """
        运行AI测试用例生成

        参数:
            feature: 功能名称
            page_url: 页面URL路径
            test_goals: 测试目标列表

        返回:
            生成结果
        """
        logger.info("=" * 60)
        logger.info(f"开始AI测试生成: {feature}")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            # 创建测试生成器
            generator = TestGenerator(self.config)

            # 默认测试目标
            if not test_goals:
                test_goals = [
                    "测试功能入口是否可见",
                    "测试功能是否可以正常操作",
                    "测试操作结果是否符合预期",
                ]

            # 创建测试规范
            spec = create_spec_from_description(feature)
            spec.test_scenarios = test_goals

            # 生成测试
            output_dir = self.config.report_dir / "generated_tests"
            test_cases = generator.generate_tests(spec, output_dir)

            execution_time = time.time() - start_time

            # 生成报告
            report = {
                "mode": "generation",
                "feature": feature,
                "page_url": page_url,
                "success": True,
                "test_cases_count": len(test_cases),
                "output_dir": str(output_dir),
                "test_cases": [
                    {
                        "name": tc.test_name,
                        "steps_count": len(tc.steps),
                    }
                    for tc in test_cases
                ],
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }

            # 保存报告
            self._save_report(report, prefix="generate")

            # 打印摘要
            logger.info(f"生成完成: {len(test_cases)} 个测试用例")
            logger.info(f"输出目录: {output_dir}")

            return report

        except Exception as e:
            logger.error(f"测试生成失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "mode": "generation",
                "feature": feature,
            }

    def run_healing(
        self,
        selector: str,
        page_url: str = "",
        action: str = "click",
    ) -> dict:
        """
        运行元素定位修复测试

        参数:
            selector: 失效的选择器
            page_url: 页面URL路径
            action: 操作类型

        返回:
            修复结果
        """
        logger.info("=" * 60)
        logger.info(f"开始元素修复测试")
        logger.info(f"原选择器: {selector}")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            from playwright.sync_api import sync_playwright

            # 启动浏览器
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # 导航到页面
                if page_url:
                    full_url = self._get_full_url(page_url)
                    page.goto(full_url, wait_until="networkidle")
                    page_html = page.content()
                else:
                    page_html = "<html></html>"

                # 创建自愈器并修复
                healer = SelfHealer(self.config.healenium, self.config.ai)
                result = healer.heal(
                    failed_selector=selector,
                    page_html=page_html,
                    action=action,
                )

                browser.close()

            execution_time = time.time() - start_time

            # 生成报告
            report = {
                "mode": "healing",
                "original_selector": selector,
                "page_url": page_url,
                "action": action,
                "success": result.success,
                "healed_selector": result.healed_selector,
                "method": result.method,
                "confidence": result.confidence,
                "alternatives": result.alternatives,
                "error": result.error,
                "healer_stats": healer.get_statistics(),
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }

            # 保存报告
            self._save_report(report, prefix="heal")

            # 打印结果
            if result.success:
                logger.info(f"修复成功!")
                logger.info(f"新选择器: {result.healed_selector}")
                logger.info(f"修复方法: {result.method}")
                logger.info(f"置信度: {result.confidence:.2f}")
            else:
                logger.warning(f"修复失败: {result.error}")

            return report

        except Exception as e:
            logger.error(f"元素修复测试失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "mode": "healing",
                "selector": selector,
            }

    def run_hybrid(
        self,
        actions: list,
        start_url: str = "",
    ) -> dict:
        """
        运行混合运行器测试

        参数:
            actions: 操作列表 [{"type": "click", "selector": "..."}]
            start_url: 起始URL

        返回:
            测试结果
        """
        logger.info("=" * 60)
        logger.info("开始混合运行器测试")
        logger.info("=" * 60)

        start_time = time.time()

        try:
            # 创建混合运行器
            runner = HybridRunner(self.config)

            # 转换操作
            test_actions = [
                create_action(
                    action_type=a["type"],
                    selector=a["selector"],
                    value=a.get("value"),
                )
                for a in actions
            ]

            # 执行测试
            with runner:
                success = runner.run_test_flow(test_actions, start_url)

            execution_time = time.time() - start_time

            # 获取测试报告
            test_report = runner.get_test_report()

            # 生成报告
            report = {
                "mode": "hybrid",
                "success": success,
                "test_report": test_report,
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }

            # 保存报告
            self._save_report(report, prefix="hybrid")

            # 打印摘要
            logger.info(f"测试完成: {'成功' if success else '失败'}")
            logger.info(f"总步骤: {test_report['total_steps']}")
            logger.info(f"成功步骤: {test_report['successful_steps']}")
            logger.info(f"自愈次数: {test_report['healed_count']}")

            return report

        except Exception as e:
            logger.error(f"混合运行器测试失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "mode": "hybrid",
            }

    def start_healenium_server(self) -> bool:
        """
        尝试启动Healenium Server（Docker方式）

        返回:
            是否成功启动
        """
        import subprocess

        logger.info("检查Healenium Server状态...")

        try:
            # 检查Docker是否可用
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.warning("Docker不可用，跳过Healenium启动")
                return False

            # 检查Healenium是否已运行
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", "name=healenium"],
                capture_output=True,
                text=True,
            )

            if "healenium" in result.stdout:
                logger.info("Healenium容器已存在")
                # 尝试启动
                subprocess.run(
                    ["docker", "start", "healenium"],
                    capture_output=True,
                )
            else:
                # 创建并启动Healenium容器
                logger.info("启动Healenium Server...")
                subprocess.run([
                    "docker", "run", "-d",
                    "--name", "healenium",
                    "-p", "8088:8088",
                    "healenium/helium-backend:latest",
                ], check=False)

            # 等待服务就绪
            time.sleep(5)
            logger.info("Healenium Server已启动 (localhost:8088)")

            return True

        except Exception as e:
            logger.warning(f"启动Healenium失败: {e}")
            return False

    def _get_full_url(self, path: str) -> str:
        """获取完整URL"""
        base = self.config.base_url.rstrip("/")
        path = path.lstrip("/")
        return f"{base}/{path}"

    def _generate_report(
        self,
        mode: str,
        goal: str,
        result,
        execution_time: float,
    ) -> dict:
        """生成测试报告"""
        from tests.ai_e2e.agents.test_executor import ExecutionResult

        if isinstance(result, ExecutionResult):
            return {
                "mode": mode,
                "goal": goal,
                "success": result.success,
                "goal_achieved": result.goal_achieved,
                "steps_count": result.steps_count,
                "execution_time": execution_time,
                "actions": [
                    {
                        "type": a.action_type.value,
                        "target": a.target,
                        "reason": a.reason,
                        "confidence": a.confidence,
                    }
                    for a in result.actions_executed
                ],
                "error": result.error,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "mode": mode,
                "goal": goal,
                "success": False,
                "error": str(result),
                "timestamp": datetime.now().isoformat(),
            }

    def _save_report(self, report: dict, prefix: str = "test"):
        """保存测试报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.json"
        filepath = self.config.report_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"报告已保存: {filepath}")

    def _print_summary(self, report: dict):
        """打印测试摘要"""
        logger.info("=" * 60)
        logger.info("测试执行摘要")
        logger.info("=" * 60)
        logger.info(f"模式: {report.get('mode', 'unknown')}")
        logger.info(f"成功: {report.get('success', False)}")

        if 'goal' in report:
            logger.info(f"目标: {report['goal']}")

        if 'steps_count' in report:
            logger.info(f"执行步数: {report['steps_count']}")

        if 'execution_time' in report:
            logger.info(f"执行时间: {report['execution_time']:.2f}s")

        if 'error' in report and report['error']:
            logger.error(f"错误: {report['error']}")

        logger.info("=" * 60)


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="AI增强型E2E测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # AI自主测试
  python scripts/ai_e2e_runner.py --mode autonomous --goal "测试小说创建功能"

  # 测试用例生成
  python scripts/ai_e2e_runner.py --mode generate --feature "小说管理"

  # 元素修复测试
  python scripts/ai_e2e_runner.py --mode heal --selector ".ant-btn-primary"

  # 混合运行器测试
  python scripts/ai_e2e_runner.py --mode hybrid --actions '[{"type":"click","selector":"button"}]'
        """
    )

    parser.add_argument(
        "--mode",
        choices=["autonomous", "generate", "heal", "hybrid"],
        default="autonomous",
        help="运行模式",
    )

    parser.add_argument("--goal", help="测试目标描述(autonomous模式)")
    parser.add_argument("--start-url", help="起始URL路径", default="")

    parser.add_argument("--feature", help="功能名称(generate模式)")

    parser.add_argument("--selector", help="失效的选择器(heal模式)")
    parser.add_argument("--action", help="操作类型", default="click")

    parser.add_argument("--actions", help="操作列表(JSON格式,hybrid模式)")

    parser.add_argument("--max-steps", type=int, help="最大执行步数", default=50)

    parser.add_argument(
        "--config",
        help="配置文件路径",
    )

    parser.add_argument(
        "--base-url",
        help="测试目标URL",
        default=os.getenv("TEST_BASE_URL", "http://localhost:3000"),
    )

    parser.add_argument(
        "--start-healenium",
        action="store_true",
        help="启动Healenium Server",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出",
    )

    args = parser.parse_args()

    # 配置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 加载配置
    config = TestConfig.from_env()
    config.base_url = args.base_url

    # 创建运行器
    runner = AIE2ERunner(config)

    # 启动Healenium（可选）
    if args.start_healenium:
        runner.start_healenium_server()

    # 执行对应模式
    if args.mode == "autonomous":
        if not args.goal:
            parser.error("--goal 为必填参数")

        result = runner.run_autonomous(
            goal=args.goal,
            start_url=args.start_url,
            max_steps=args.max_steps,
        )

    elif args.mode == "generate":
        if not args.feature:
            parser.error("--feature 为必填参数")

        result = runner.run_generation(feature=args.feature)

    elif args.mode == "heal":
        if not args.selector:
            parser.error("--selector 为必填参数")

        result = runner.run_healing(
            selector=args.selector,
            page_url=args.start_url,
            action=args.action,
        )

    elif args.mode == "hybrid":
        if not args.actions:
            parser.error("--actions 为必填参数")

        actions = json.loads(args.actions)
        result = runner.run_hybrid(
            actions=actions,
            start_url=args.start_url,
        )

    # 退出码
    sys.exit(0 if result.get("success", False) else 1)


if __name__ == "__main__":
    main()