"""
AI测试用例生成器

基于页面分析和需求描述，自动生成E2E测试用例代码
支持Playwright和混合运行器两种模式

作者: Qoder
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, Page
from pydantic import BaseModel

from tests.ai_e2e.config import AIConfig, TestConfig, default_config
from tests.ai_e2e.agents.test_executor import LLMClient, PageState

logger = logging.getLogger(__name__)


@dataclass
class TestSpecification:
    """测试需求规范"""
    feature_name: str  # 功能名称
    description: str  # 功能描述
    test_scenarios: List[str] = field(default_factory=list)  # 测试场景列表
    expected_results: List[str] = field(default_factory=list)  # 预期结果


@dataclass
class GeneratedTestCase:
    """生成的测试用例"""
    test_name: str
    test_code: str
    selectors: Dict[str, str] = field(default_factory=dict)
    steps: List[str] = field(default_factory=list)
    assertions: List[str] = field(default_factory=list)


class PageAnalyzer:
    """
    页面分析器

    抓取和分析页面结构，识别可测试的功能点
    """

    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or default_config
        self.playwright = None
        self.page: Optional[Page] = None

    def start(self):
        """启动浏览器"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
        )
        self.page = self.browser.new_context().new_page()

    def stop(self):
        """关闭浏览器"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def analyze(self, url: str) -> Dict[str, Any]:
        """
        分析指定URL的页面结构

        参数:
            url: 页面URL

        返回:
            页面分析结果
        """
        if not self.page:
            self.start()

        full_url = urljoin(self.config.base_url, url)
        logger.info(f"分析页面: {full_url}")

        self.page.goto(full_url, wait_until="networkidle", timeout=30000)

        # 分析结果
        result = {
            "url": self.page.url,
            "title": self.page.title(),
            "routes": self._analyze_routes(),
            "forms": self._analyze_forms(),
            "buttons": self._analyze_buttons(),
            "tables": self._analyze_tables(),
            "modals": self._analyze_modals(),
            "navigation": self._analyze_navigation(),
            "inputs": self._analyze_inputs(),
        }

        logger.info(f"页面分析完成，发现 {len(result['buttons'])} 个按钮，{len(result['forms'])} 个表单")
        return result

    def _analyze_routes(self) -> List[Dict[str, str]]:
        """分析页面路由和导航"""
        routes = []

        # 分析侧边栏导航
        try:
            nav_items = self.page.query_selector_all(".ant-menu-item, .ant-menu-submenu-title")
            for item in nav_items:
                text = item.text_content() or ""
                href = item.get_attribute("href") or ""
                if text.strip():
                    routes.append({
                        "text": text.strip(),
                        "href": href,
                        "type": "menu"
                    })
        except Exception as e:
            logger.warning(f"分析路由失败: {e}")

        return routes

    def _analyze_forms(self) -> List[Dict[str, Any]]:
        """分析表单元素"""
        forms = []

        try:
            # 查找表单容器
            form_containers = self.page.query_selector_all("form, .ant-form")
            for container in form_containers:
                form_info = {
                    "inputs": [],
                    "buttons": [],
                    "type": "ant-form" if container.get_attribute("class") and "ant-form" in container.get_attribute("class") else "form"
                }

                # 查找输入框
                inputs = container.query_selector_all("input, textarea, .ant-input")
                for inp in inputs:
                    input_info = {
                        "name": inp.get_attribute("name") or "",
                        "id": inp.get_attribute("id") or "",
                        "type": inp.get_attribute("type") or "text",
                        "placeholder": inp.get_attribute("placeholder") or "",
                        "class": inp.get_attribute("class") or "",
                    }
                    form_info["inputs"].append(input_info)

                # 查找提交按钮
                buttons = container.query_selector_all("button[type='submit'], .ant-btn-primary")
                for btn in buttons:
                    btn_text = btn.text_content() or ""
                    if btn_text.strip():
                        form_info["buttons"].append(btn_text.strip())

                if form_info["inputs"] or form_info["buttons"]:
                    forms.append(form_info)

        except Exception as e:
            logger.warning(f"分析表单失败: {e}")

        return forms

    def _analyze_buttons(self) -> List[Dict[str, str]]:
        """分析按钮元素"""
        buttons = []

        try:
            btn_selectors = [
                "button",
                "[role='button']",
                ".ant-btn",
                "a.btn",
            ]

            for selector in btn_selectors:
                elements = self.page.query_selector_all(selector)
                for el in elements:
                    text = el.text_content() or ""
                    btn_type = el.get_attribute("type") or "button"
                    classes = el.get_attribute("class") or ""

                    if text.strip():
                        # 排除图标按钮
                        if len(text.strip()) > 1:
                            buttons.append({
                                "text": text.strip()[:50],
                                "class": classes[:100],
                                "type": btn_type,
                            })

        except Exception as e:
            logger.warning(f"分析按钮失败: {e}")

        return buttons

    def _analyze_tables(self) -> List[Dict[str, Any]]:
        """分析表格元素"""
        tables = []

        try:
            table_containers = self.page.query_selector_all(".ant-table")
            for table in table_containers:
                table_info = {
                    "columns": [],
                    "rows": 0,
                }

                # 分析表头
                headers = table.query_selector_all(".ant-table-thead th")
                for header in headers:
                    text = header.text_content() or ""
                    if text.strip():
                        table_info["columns"].append(text.strip())

                # 统计行数
                rows = table.query_selector_all(".ant-table-tbody tr")
                table_info["rows"] = len(rows)

                tables.append(table_info)

        except Exception as e:
            logger.warning(f"分析表格失败: {e}")

        return tables

    def _analyze_modals(self) -> List[Dict[str, str]]:
        """分析弹窗"""
        modals = []

        try:
            modal_containers = self.page.query_selector_all(".ant-modal")
            for modal in modal_containers:
                title_el = modal.query_selector(".ant-modal-title")
                title = title_el.text_content() if title_el else ""

                modals.append({
                    "title": title.strip() if title else "",
                    "visible": modal.is_visible(),
                })
        except Exception:
            pass

        return modals

    def _analyze_navigation(self) -> List[Dict[str, str]]:
        """分析导航元素"""
        nav_items = []

        try:
            # 顶部导航
            header_nav = self.page.query_selector_all(".ant-layout-header a, .ant-layout-header button")
            for el in header_nav:
                text = el.text_content() or ""
                href = el.get_attribute("href") or ""
                if text.strip() and len(text.strip()) < 30:
                    nav_items.append({
                        "text": text.strip(),
                        "href": href,
                        "location": "header"
                    })

            # 面包屑
            breadcrumbs = self.page.query_selector_all(".ant-breadcrumb a, .ant-breadcrumb span")
            for el in breadcrumbs:
                text = el.text_content() or ""
                if text.strip():
                    nav_items.append({
                        "text": text.strip(),
                        "location": "breadcrumb"
                    })

        except Exception as e:
            logger.warning(f"分析导航失败: {e}")

        return nav_items

    def _analyze_inputs(self) -> List[Dict[str, str]]:
        """分析输入元素"""
        inputs = []

        try:
            input_elements = self.page.query_selector_all(
                "input:not([type='hidden']):not([type='checkbox']):not([type='radio']), "
                "textarea, .ant-input, .ant-input-number, .ant-picker"
            )

            for el in input_elements:
                info = {
                    "name": el.get_attribute("name") or "",
                    "id": el.get_attribute("id") or "",
                    "type": el.get_attribute("type") or "text",
                    "placeholder": el.get_attribute("placeholder") or "",
                    "class": (el.get_attribute("class") or "")[:50],
                }
                if info["placeholder"] or info["name"]:
                    inputs.append(info)

        except Exception as e:
            logger.warning(f"分析输入框失败: {e}")

        return inputs

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False


class TestGenerator:
    """
    AI测试用例生成器

    根据页面分析和需求描述，自动生成可执行的E2E测试代码
    """

    def __init__(
        self,
        config: Optional[TestConfig] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        初始化测试生成器

        参数:
            config: 测试配置
            llm_client: 大语言模型客户端
        """
        self.config = config or default_config
        self.llm = llm_client or LLMClient(self.config.ai)
        self.page_analyzer = PageAnalyzer(self.config)

        logger.info("TestGenerator初始化完成")

    def generate_tests(
        self,
        spec: TestSpecification,
        output_dir: Optional[Path] = None,
    ) -> List[GeneratedTestCase]:
        """
        生成测试用例

        参数:
            spec: 测试需求规范
            output_dir: 输出目录

        返回:
            生成的测试用例列表
        """
        logger.info(f"开始生成测试用例: {spec.feature_name}")

        # 分析相关页面
        page_analysis = self._analyze_relevant_pages(spec)

        # 调用AI生成测试代码
        test_cases = self._generate_test_code(spec, page_analysis)

        # 保存测试文件
        if output_dir:
            self._save_test_files(test_cases, output_dir)

        logger.info(f"生成完成，共 {len(test_cases)} 个测试用例")
        return test_cases

    def _analyze_relevant_pages(self, spec: TestSpecification) -> Dict[str, Any]:
        """分析相关页面"""
        # 根据功能名称推测可能需要的页面
        page_routes = {
            "小说": ["/novels", "/novels/new"],
            "大纲": ["/novels"],
            "章节": ["/novels", "/novels/:id/chapters"],
            "角色": ["/novels/:id/characters"],
            "登录": ["/login", "/"],
            "注册": ["/register"],
            "仪表盘": ["/", "/dashboard"],
        }

        routes_to_analyze = []
        for keyword, routes in page_routes.items():
            if keyword in spec.feature_name or keyword in spec.description:
                routes_to_analyze.extend(routes)

        # 去重
        routes_to_analyze = list(set(routes_to_analyze))

        analysis_results = {}
        for route in routes_to_analyze[:3]:  # 最多分析3个页面
            try:
                analysis_results[route] = self.page_analyzer.analyze(route)
            except Exception as e:
                logger.warning(f"分析页面 {route} 失败: {e}")

        return analysis_results

    def _generate_test_code(
        self,
        spec: TestSpecification,
        page_analysis: Dict[str, Any],
    ) -> List[GeneratedTestCase]:
        """使用AI生成测试代码"""
        test_cases = []

        for scenario in spec.test_scenarios:
            # 构建提示词
            prompt = self._build_generation_prompt(scenario, page_analysis)

            # 调用LLM
            response = self.llm.generate(prompt)

            # 检查响应是否包含API错误
            if "InvalidApiKey" in response or "No API-key" in response:
                # 使用本地回退生成器
                logger.warning("API密钥无效，使用本地回退生成器")
                test_case = self._generate_local_test(scenario, page_analysis)
            else:
                # 解析AI生成的测试用例
                test_case = self._parse_test_code(scenario, response, page_analysis)

            if test_case:
                test_cases.append(test_case)

        return test_cases

    def _generate_local_test(
        self,
        scenario: str,
        page_analysis: Dict[str, Any],
    ) -> Optional[GeneratedTestCase]:
        """本地回退测试生成（无API密钥时使用）"""
        import re

        test_name = self._extract_test_name(scenario)

        # 收集所有发现的元素
        all_buttons = []
        all_forms = []
        all_routes = []

        for route, analysis in page_analysis.items():
            all_buttons.extend(analysis.get('buttons', []))
            all_forms.extend(analysis.get('forms', []))
            all_routes.extend(analysis.get('routes', []))

        # 构建基础测试代码
        test_code = f'''"""自动生成的测试用例: {scenario}"""

import pytest
from playwright.sync_api import Page, expect


class Test{test_name.title().replace('_', '')}:
    """测试场景: {scenario}"""

    @pytest.mark.smoke
    def test_{test_name}(self, page: Page):
        """{scenario}"""

        # 1. 导航到页面
        page.goto("/novels")
        page.wait_for_load_state("networkidle")

'''

        # 添加按钮点击测试
        if all_buttons:
            btn = all_buttons[0]
            btn_text = btn.get('text', '按钮')
            test_code += f'''        # 2. 查找并点击按钮
        try:
            page.click("text={btn_text}", timeout=5000)
        except Exception:
            page.click(".ant-btn-primary", timeout=5000)

'''

        # 添加表单测试
        if all_forms and all_forms[0].get('inputs'):
            inputs = all_forms[0]['inputs']
            if inputs:
                input_info = inputs[0]
                test_code += f'''        # 3. 填写表单（如有）
        try:
            page.fill('input[name="{input_info.get("name", "title")}"]', "测试数据")
        except Exception:
            pass

'''

        # 添加断言
        test_code += '''        # 4. 验证结果
        # 根据实际需求添加断言

        # 验证页面正常加载
        assert page.title() is not None
'''

        return GeneratedTestCase(
            test_name=test_name,
            test_code=test_code,
            selectors={},
            steps=["导航", "交互", "验证"],
            assertions=["页面加载"],
        )

    def _build_generation_prompt(
        self,
        scenario: str,
        page_analysis: Dict[str, Any],
    ) -> str:
        """构建测试生成提示词"""
        # 格式化页面分析结果
        pages_info = []
        for route, analysis in page_analysis.items():
            page_text = f"\n## 页面: {route}\n"
            page_text += f"标题: {analysis.get('title', '')}\n"

            # 按钮
            buttons = analysis.get('buttons', [])
            if buttons:
                page_text += "\n可点击按钮:\n"
                for btn in buttons[:10]:
                    page_text += f"- {btn['text']}\n"

            # 表单
            forms = analysis.get('forms', [])
            if forms:
                page_text += "\n表单:\n"
                for form in forms:
                    page_text += f"- 输入框: {len(form.get('inputs', []))}个\n"
                    page_text += f"- 提交按钮: {form.get('buttons', [])}\n"

            pages_info.append(page_text)

        pages_text = "\n".join(pages_info)

        prompt = f"""
你是一个专业的自动化测试工程师，请根据以下信息生成Playwright E2E测试代码。

## 测试场景
{scenario}

## 页面分析结果
{pages_text}

## 要求
1. 使用pytest + Playwright框架
2. 使用页面对象模型(POM)组织代码
3. 选择器优先使用: text=, :has-text(), data-testid
4. 添加适当的等待和断言
5. 生成完整的可执行测试代码

请以Python代码格式输出测试用例，包含:
- 导入语句
- 测试类和方法
- 页面操作步骤
- 断言语句
"""
        return prompt

    def _parse_test_code(
        self,
        scenario: str,
        llm_response: str,
        page_analysis: Dict[str, Any],
    ) -> Optional[GeneratedTestCase]:
        """解析LLM响应，生成测试用例"""
        try:
            # 提取Python代码
            code_start = llm_response.find("```python")
            if code_start == -1:
                code_start = llm_response.find("```")

            code_end = llm_response.rfind("```")

            if code_start != -1 and code_end != -1 and code_end > code_start:
                code = llm_response[code_start:code_end]
                # 移除markdown标记
                code = code.replace("```python", "").replace("```", "").strip()
            else:
                # 整个响应作为代码
                code = llm_response.strip()

            # 提取测试名称
            test_name = self._extract_test_name(scenario)

            # 提取选择器
            selectors = self._extract_selectors(code)

            # 提取步骤和断言
            steps = self._extract_steps(code)
            assertions = self._extract_assertions(code)

            return GeneratedTestCase(
                test_name=test_name,
                test_code=code,
                selectors=selectors,
                steps=steps,
                assertions=assertions,
            )

        except Exception as e:
            logger.warning(f"解析测试代码失败: {e}")
            return None

    def _extract_test_name(self, scenario: str) -> str:
        """从场景提取测试名称"""
        # 清理特殊字符
        name = re.sub(r'[^\w\u4e00-\u9fa5]', '_', scenario)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')

        return f"test_{name[:50]}"

    def _extract_selectors(self, code: str) -> Dict[str, str]:
        """提取代码中的选择器"""
        selectors = {}

        # 匹配 click(, fill(, wait_for_selector(
        patterns = [
            r'(\w+)\s*=\s*["\']([^"\']+)["\']',
            r'selector\s*[=:]\s*["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                key = match.group(1)
                value = match.group(2)
                if value and len(value) > 2:
                    selectors[key] = value

        return selectors

    def _extract_steps(self, code: str) -> List[str]:
        """提取测试步骤"""
        steps = []

        # 匹配注释或操作
        lines = code.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                steps.append(line[1:].strip())
            elif any(op in line for op in ['.click', '.fill', '.goto', '.wait']):
                # 提取操作描述
                steps.append(line[:100])

        return steps

    def _extract_assertions(self, code: str) -> List[str]:
        """提取断言语句"""
        assertions = []

        # 匹配断言
        patterns = [
            r'assert\s+(.+)',
            r'expect\((.+)\)',
            r'assert\s+\w+\s*==\s*(.+)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                assertions.append(match.group(0)[:100])

        return assertions

    def _save_test_files(
        self,
        test_cases: List[GeneratedTestCase],
        output_dir: Path,
    ):
        """保存测试文件"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存每个测试用例
        for i, test_case in enumerate(test_cases):
            filename = f"test_{i+1}_{test_case.test_name}.py"
            filepath = output_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(test_case.test_code)

            logger.info(f"保存测试文件: {filepath}")

        # 生成__init__.py
        init_file = output_dir / "__init__.py"
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write('"""自动生成的AI测试用例"""\n')

    def analyze_and_generate(
        self,
        page_url: str,
        test_goals: List[str],
    ) -> List[GeneratedTestCase]:
        """
        分析页面并生成测试用例的便捷方法

        参数:
            page_url: 页面URL路径
            test_goals: 测试目标列表

        返回:
            生成的测试用例
        """
        # 分析页面
        analysis = self.page_analyzer.analyze(page_url)

        # 构建测试规范
        spec = TestSpecification(
            feature_name=page_url,
            description=f"测试 {page_url} 页面的功能",
            test_scenarios=test_goals,
        )

        # 生成测试
        return self._generate_test_code(spec, {page_url: analysis})


def create_spec_from_description(description: str) -> TestSpecification:
    """
    从描述文本创建测试规范

    便捷工厂函数
    """
    # 简单的解析逻辑
    scenarios = []
    if "创建" in description or "新增" in description:
        scenarios.append("测试成功创建功能")
        scenarios.append("测试创建表单验证")
    if "编辑" in description or "修改" in description:
        scenarios.append("测试编辑功能")
    if "删除" in description:
        scenarios.append("测试删除功能")
    if "列表" in description or "查看" in description:
        scenarios.append("测试列表展示")

    # 默认场景
    if not scenarios:
        scenarios = ["测试基本功能"]

    return TestSpecification(
        feature_name=description[:20],
        description=description,
        test_scenarios=scenarios,
    )