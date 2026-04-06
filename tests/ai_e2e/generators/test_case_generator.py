"""测试用例离线生成器 — 调用 LLM 基于页面元数据生成结构化测试用例 JSON.

独立脚本，不在 pytest 运行时调用。生成的 JSON 存储到 generated/ 目录。

使用方式：
    python -m tests.ai_e2e.generators.test_case_generator \
        --page novel_list \
        --output tests/ai_e2e/generated/novel_list_suite.json
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tests.ai_e2e.meta.page_meta_extractor import PageMetaExtractor
from tests.ai_e2e.schemas.test_case_schema import TestSuite

# 页面标识 → Page Object 文件路径的映射
_PAGE_FILE_MAP = {
    "novel_list": "tests/e2e/pages/novel_list_page.py",
    "novel_detail": "tests/e2e/pages/novel_detail_page.py",
    "base": "tests/e2e/pages/base_page.py",
    "revision": "tests/e2e/pages/revision_page.py",
}

# LLM 生成测试用例的 system prompt
_SYSTEM_PROMPT = """\
你是一个资深 QA 测试工程师，\
精通 Ant Design 6 组件库和 React 19 应用的 E2E 测试。

你的任务是根据提供的页面元数据，生成结构化的 UI 自动化测试用例。

## 测试用例 JSON Schema 规范

每个测试步骤的 element 字段使用语义描述（非 CSS 选择器），格式：
{"role": "button/textbox/combobox/...", "name": "元素文本", "fallback_name": "备选文本"}

可用的 action 类型：
- navigate: 导航到 URL（使用 url 字段）
- click: 点击元素（使用 element 字段）
- fill: 填充输入框（使用 element + value 字段）
- press_key: 按键（使用 value 字段，如 "Enter"）
- wait_for: 等待文本出现（使用 value 字段）
- assert_visible: 断言元素可见（使用 element 字段）
- assert_text: 断言页面包含文本（使用 value 字段）
- screenshot: 截图

断言类型：
- rule_based: 规则断言（确定性验证）
- llm_judged: LLM 语义判断（灵活但消耗 token）
- hybrid: 规则优先，LLM 辅助

## 生成要求

1. 按等价类划分和边界值分析设计测试场景
2. 每个用例必须有 cleanup 步骤（如关闭模态框）
3. P0 级别用于冒烟测试（核心流程），P1 级别用于回归，P2 级别用于边界情况
4. element 的 name 应基于页面实际显示文本，参考 SELECTORS 中的 has-text 等线索
5. 严格输出 JSON 格式的 TestSuite 对象"""


class TestCaseGenerator:
    """离线测试用例生成器 — 调用 LLM 生成 TestSuite JSON."""

    __test__ = False

    def __init__(self, qwen_client: Any = None):
        """初始化生成器.

        Args:
            qwen_client: QwenClient 实例，为 None 时延迟导入
        """
        self._client = qwen_client
        self.extractor = PageMetaExtractor()

    @property
    def client(self) -> Any:
        """延迟导入 QwenClient."""
        if self._client is None:
            from llm.qwen_client import qwen_client

            self._client = qwen_client
        return self._client

    async def generate_suite(
        self,
        page_name: str,
        focus: str = "comprehensive",
    ) -> TestSuite:
        """生成测试套件.

        Args:
            page_name: 页面标识（如 "novel_list"）
            focus: 生成焦点: comprehensive / smoke / edge_case

        Returns:
            生成的 TestSuite 对象
        """
        # 提取页面元数据
        page_file = _PAGE_FILE_MAP.get(page_name)
        if not page_file:
            raise ValueError(f"未知页面: {page_name}，可选: {list(_PAGE_FILE_MAP.keys())}")

        meta = self.extractor.extract(page_file)
        meta_json = json.dumps(meta, ensure_ascii=False, indent=2)

        # 构建 user prompt
        user_prompt = (
            f"## 页面: {page_name}\n\n"
            f"### 页面元数据\n```json\n{meta_json}\n```\n\n"
            f"### 生成要求\n"
            f"- 焦点: {focus}\n"
            f"- 请生成一个完整的 TestSuite JSON 对象\n"
            f"- suite_name: '{page_name}_suite'\n"
            f"- page_target: '{page_name}'\n"
        )

        if focus == "smoke":
            user_prompt += "- 仅生成 3-5 个 P0 级别的核心流程测试用例\n"
        elif focus == "edge_case":
            user_prompt += "- 聚焦边界值和异常情况，生成 5-8 个 P2 级别用例\n"
        else:
            user_prompt += "- 生成 8-12 个覆盖 P0/P1/P2 的完整测试用例\n"

        # 调用 LLM 生成
        result = await self.client.chat(
            prompt=user_prompt,
            system=_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=8192,
        )

        content = result.get("content", "")

        # 从 LLM 输出中提取 JSON
        suite_json = self._extract_json(content)

        # 补充生成信息
        suite_json["generated_at"] = datetime.now(timezone.utc).isoformat()
        suite_json["generator_model"] = getattr(self.client, "model", "unknown")

        return TestSuite.model_validate(suite_json)

    def _extract_json(self, text: str) -> dict:
        """从 LLM 输出文本中提取 JSON 对象.

        支持直接 JSON 和 markdown 代码块包裹两种格式。
        """
        text = text.strip()

        # 尝试 markdown 代码块
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        # 找到第一个 { 和最后一个 }
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            text = text[brace_start : brace_end + 1]

        return json.loads(text)

    async def generate_and_save(
        self,
        page_name: str,
        output_path: str,
        focus: str = "comprehensive",
    ) -> TestSuite:
        """生成测试套件并保存为 JSON 文件.

        Args:
            page_name: 页面标识
            output_path: 输出文件路径
            focus: 生成焦点

        Returns:
            生成的 TestSuite
        """
        suite = await self.generate_suite(page_name, focus)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            suite.model_dump_json(indent=2, by_alias=True),
            encoding="utf-8",
        )

        return suite


async def _main() -> None:
    """命令行入口."""
    import argparse

    parser = argparse.ArgumentParser(description="AI E2E 测试用例离线生成器")
    parser.add_argument("--page", required=True, help="页面标识 (novel_list 等)")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument(
        "--focus",
        default="comprehensive",
        choices=["comprehensive", "smoke", "edge_case"],
        help="生成焦点",
    )
    args = parser.parse_args()

    generator = TestCaseGenerator()
    suite = await generator.generate_and_save(args.page, args.output, args.focus)
    print(f"生成完成: {len(suite.test_cases)} 个测试用例 → {args.output}")


if __name__ == "__main__":
    asyncio.run(_main())
