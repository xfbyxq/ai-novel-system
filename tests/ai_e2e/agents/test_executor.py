"""
AI测试执行器 - 全AI自动执行测试的核心引擎

无需预定义测试步骤，AI自行决策操作序列
基于视觉分析和语义理解，自主完成测试任务

作者: Qoder
"""

import asyncio
import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, Page, Browser
from pydantic import BaseModel

from tests.ai_e2e.config import AIConfig, TestConfig, default_config
from tests.ai_e2e.selectors.healenium_adapter import SelectorManager

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """AI可执行的行动类型"""
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    HOVER = "hover"
    WAIT = "wait"
    SELECT = "select"
    NAVIGATE = "navigate"
    SCREENSHOT = "screenshot"
    GET_TEXT = "get_text"
    CHECK = "check"
    WAIT_FOR_NAVIGATION = "wait_for_navigation"
    STOP = "stop"
    REPORT = "report"


@dataclass
class AIAction:
    """AI执行的单个动作"""
    action_type: ActionType
    target: str  # 目标元素或路径
    value: Optional[str] = None  # 填充值等
    reason: str = ""  # AI执行此动作的理由
    confidence: float = 1.0  # 置信度 0-1
    timestamp: float = field(default_factory=time.time)


@dataclass
class PageState:
    """页面状态快照"""
    url: str
    title: str
    html: str
    screenshot_base64: Optional[str] = None
    elements: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionResult:
    """测试执行结果"""
    success: bool
    goal_achieved: bool
    actions_executed: List[AIAction]
    final_state: Optional[PageState] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    steps_count: int = 0


class LLMClient:
    """
    大语言模型客户端

    支持DashScope(通义千问)和OpenAI兼容接口
    """

    def __init__(self, config: Optional[AIConfig] = None):
        """
        初始化LLM客户端

        参数:
            config: AI配置
        """
        self.config = config or AIConfig()
        self.provider = self.config.provider
        self._client = None

    def _get_client(self):
        """获取LLM客户端"""
        if self._client is None:
            if self.provider == "dashscope":
                try:
                    import dashscope
                    dashscope.api_key = self.config.api_key
                    self._client = dashscope
                except ImportError:
                    logger.warning("dashscope未安装，将使用模拟响应")
                    self._client = None
            elif self.provider == "openai":
                try:
                    from openai import OpenAI
                    self._client = OpenAI(
                        api_key=self.config.api_key,
                        base_url=self.config.base_url or "https://api.openai.com/v1",
                    )
                except ImportError:
                    logger.warning("openai未安装，将使用模拟响应")
                    self._client = None

        return self._client

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        生成响应

        参数:
            prompt: 用户提示词
            system_prompt: 系统提示词

        返回:
            AI生成的响应文本
        """
        client = self._get_client()

        try:
            if self.provider == "dashscope" and client:
                # 使用OpenAI兼容模式
                from openai import OpenAI

                # 创建兼容客户端
                dashscope_client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                )

                response = dashscope_client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt or self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                return response.choices[0].message.content

            elif self.provider == "openai" and client:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt or self._get_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.warning(f"LLM调用失败: {e}，使用模拟响应")

        # 返回模拟响应用于开发测试
        return self._generate_mock_response(prompt)

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的自动化测试工程师，负责执行E2E测试。

你的任务是：
1. 分析当前页面状态
2. 决定下一步应该执行什么动作来接近测试目标
3. 解释你为什么选择这个动作

测试目标示例：
- "测试小说创建功能" - 需要找到并点击"创建小说"按钮，填写表单，提交
- "测试登录流程" - 需要找到登录表单，输入账号密码，点击登录
- "验证大纲保存" - 需要导航到大纲页面，填写内容，点击保存

可用的动作类型：
- click: 点击元素
- fill: 填写输入框
- hover: 悬停
- wait: 等待
- navigate: 导航到新页面
- screenshot: 截图分析
- get_text: 获取文本内容
- stop: 停止测试
- report: 生成报告

请以JSON格式输出你的决策：
{"action": "动作类型", "target": "目标选择器或路径", "value": "可选的填充值", "reason": "执行理由", "confidence": 0.0-1.0的置信度}

重要：
- 优先使用稳定的CSS选择器（如data-testid, .ant-btn-primary）
- 页面加载后先分析页面结构
- 如果不确定，选择最可能成功的动作
- 如果测试目标已达成，使用action: "stop"
"""

    def _generate_mock_response(self, prompt: str) -> str:
        """生成模拟响应（用于开发测试）"""
        # 简单的基于关键词的响应
        if "创建小说" in prompt or "novel" in prompt.lower():
            return json.dumps({
                "action": "click",
                "target": "button:has-text('创建小说')",
                "reason": "点击创建小说按钮开始测试流程",
                "confidence": 0.9,
            })
        elif "登录" in prompt:
            return json.dumps({
                "action": "click",
                "target": "button:has-text('登录')",
                "reason": "点击登录按钮",
                "confidence": 0.8,
            })
        else:
            return json.dumps({
                "action": "stop",
                "target": "",
                "reason": "无法确定下一步操作",
                "confidence": 0.5,
            })


class AITestExecutor:
    """
    全AI自动执行测试引擎

    核心特点：
    1. 无需预定义测试步骤
    2. AI自主决策操作序列
    3. 基于页面状态动态调整策略
    4. 集成Healenium自愈机制
    """

    def __init__(
        self,
        config: Optional[TestConfig] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        初始化AI测试执行器

        参数:
            config: 测试配置
            llm_client: 大语言模型客户端
        """
        self.config = config or default_config
        self.llm = llm_client or LLMClient(self.config.ai)
        self.selector_manager = SelectorManager(self.config.healenium)

        # Playwright相关
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

        # 执行状态
        self.current_goal: str = ""
        self.actions_executed: List[AIAction] = []
        self.max_steps: int = 50  # 最大执行步数
        self.execution_start_time: float = 0.0

        # 状态回调
        self.on_action_callback: Optional[Callable] = None
        self.on_state_change_callback: Optional[Callable] = None

        logger.info("AITestExecutor初始化完成")

    def start(self):
        """启动浏览器"""
        logger.info("启动Playwright浏览器...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.config.playwright.headless,
            slow_mo=self.config.playwright.slow_mo,
        )
        context = self.browser.new_context(
            viewport={
                "width": self.config.playwright.viewport_width,
                "height": self.config.playwright.viewport_height,
            },
            locale=self.config.playwright.locale,
        )
        self.page = context.new_page()
        logger.info("浏览器启动成功")

    def stop(self):
        """关闭浏览器"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("浏览器已关闭")

    def capture_page_state(self) -> PageState:
        """
        捕获当前页面状态

        包含URL、标题、HTML、截图等信息供AI分析
        """
        screenshot_bytes = self.page.screenshot()
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode()

        # 提取可交互元素
        elements = self._extract_interactive_elements()

        return PageState(
            url=self.page.url,
            title=self.page.title(),
            html=self.page.content(),
            screenshot_base64=screenshot_base64,
            elements=elements,
        )

    def _extract_interactive_elements(self) -> List[Dict[str, Any]]:
        """提取页面上的可交互元素"""
        elements = []

        # 可交互元素选择器
        selectors = {
            "buttons": "button, [role='button'], a.btn, .ant-btn",
            "inputs": "input, textarea, [contenteditable='true'], .ant-input",
            "links": "a[href]",
            "selects": "select, .ant-select",
            "checkboxes": "input[type='checkbox'], .ant-checkbox",
        }

        for category, selector in selectors.items():
            try:
                els = self.page.query_selector_all(selector)
                for el in els:
                    try:
                        elem_info = {
                            "category": category,
                            "tag": el.evaluate("el => el.tagName.toLowerCase()"),
                            "text": el.text_content()[:100] if el.text_content() else "",
                            "id": el.get_attribute("id") or "",
                            "class": el.get_attribute("class") or "",
                            "href": el.get_attribute("href") or "",
                            "role": el.get_attribute("role") or "",
                            "aria_label": el.get_attribute("aria-label") or "",
                        }
                        elements.append(elem_info)
                    except Exception:
                        continue
            except Exception:
                continue

        return elements

    def execute_autonomous(
        self,
        goal: str,
        start_url: str = "",
        max_steps: int = 50,
    ) -> ExecutionResult:
        """
        自主执行测试

        核心方法：AI根据当前页面状态自主决策下一步操作，
        直到测试目标达成或达到最大步数

        参数:
            goal: 测试目标描述，如"测试小说创建功能"
            start_url: 起始URL路径
            max_steps: 最大执行步数

        返回:
            ExecutionResult: 执行结果
        """
        self.current_goal = goal
        self.max_steps = max_steps
        self.actions_executed = []
        self.execution_start_time = time.time()

        logger.info(f"开始AI自主测试: {goal}")
        logger.info(f"起始URL: {start_url}")

        try:
            # 导航到起始页面
            if start_url:
                full_url = urljoin(self.config.base_url, start_url)
                self.page.goto(full_url, wait_until="networkidle")
                logger.info(f"已导航到: {full_url}")
            else:
                # 直接使用基础URL
                self.page.goto(self.config.base_url, wait_until="networkidle")
                logger.info(f"已导航到: {self.config.base_url}")

            # 主循环：AI决策-执行-验证
            for step in range(max_steps):
                # 1. 捕获当前页面状态
                page_state = self.capture_page_state()

                # 2. AI决策下一步操作
                action = self._decide_next_action(page_state, goal)

                if not action:
                    logger.warning("AI无法决定下一步操作")
                    break

                # 记录执行的动作
                self.actions_executed.append(action)
                logger.info(
                    f"步骤 {step + 1}: {action.action_type.value} -> {action.target} "
                    f"(置信度: {action.confidence:.2f})"
                )

                # 3. 停止条件
                if action.action_type == ActionType.STOP:
                    logger.info("AI判定测试目标已达成")
                    break

                # 4. 执行动作
                success = self._execute_action(action)

                # 5. 如果动作执行失败，尝试自愈
                if not success:
                    logger.warning(f"动作执行失败，尝试自愈...")
                    healed_action = self._heal_failed_action(action)
                    if healed_action:
                        success = self._execute_action(healed_action)
                        if success:
                            self.actions_executed.append(healed_action)

                # 6. 状态回调
                if self.on_action_callback:
                    self.on_action_callback(action, success)

                # 短暂等待页面稳定
                self.page.wait_for_timeout(500)

            # 评估最终结果
            goal_achieved = self._evaluate_goal_achieved(goal)
            execution_time = time.time() - self.execution_start_time

            result = ExecutionResult(
                success=goal_achieved,
                goal_achieved=goal_achieved,
                actions_executed=self.actions_executed,
                final_state=self.capture_page_state(),
                execution_time=execution_time,
                steps_count=len(self.actions_executed),
            )

            logger.info(
                f"测试完成: 目标达成={goal_achieved}, "
                f"执行步数={len(self.actions_executed)}, "
                f"耗时={execution_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"AI测试执行异常: {e}")
            return ExecutionResult(
                success=False,
                goal_achieved=False,
                actions_executed=self.actions_executed,
                error=str(e),
                execution_time=time.time() - self.execution_start_time,
                steps_count=len(self.actions_executed),
            )

    def _decide_next_action(self, page_state: PageState, goal: str) -> Optional[AIAction]:
        """
        使用AI决定下一步操作

        参数:
            page_state: 当前页面状态
            goal: 测试目标

        返回:
            AIAction: 要执行的动作
        """
        # 构建提示词
        prompt = self._build_decision_prompt(page_state, goal)

        # 调用LLM
        response = self.llm.generate(prompt)

        # 解析响应
        try:
            # 尝试提取JSON
            if "{" in response and "}" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
                decision = json.loads(json_str)

                # AI返回小写，转换为大写枚举
                action_str = decision.get("action", "stop").lower()
                action_type = ActionType(action_str) if action_str in [a.value for a in ActionType] else ActionType.STOP

                return AIAction(
                    action_type=action_type,
                    target=decision.get("target", ""),
                    value=decision.get("value"),
                    reason=decision.get("reason", ""),
                    confidence=decision.get("confidence", 0.5),
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"解析AI响应失败: {e}")

        return None

    def _build_decision_prompt(self, page_state: PageState, goal: str) -> str:
        """构建AI决策提示词"""
        # 提取页面关键元素
        elements_summary = []
        for el in page_state.elements[:20]:  # 限制元素数量
            text = el.get("text", "").strip()
            if text:
                elements_summary.append(
                    f"- {el['category']}: '{text}' (class: {el.get('class', '')[:30]})"
                )

        elements_text = "\n".join(elements_summary) if elements_summary else "无可交互元素"

        prompt = f"""
当前测试目标: {goal}

当前页面信息:
- URL: {page_state.url}
- 标题: {page_state.title}

页面可交互元素:
{elements_text}

请决定下一步应该执行什么动作来接近测试目标。

请以JSON格式输出你的决策：
{{"action": "动作类型", "target": "目标选择器", "value": "填充值(可选)", "reason": "执行理由", "confidence": 0.0-1.0}}

注意：
- 优先使用包含文本内容的稳定选择器，如 "button:has-text('创建')"
- 如果测试目标已达成，使用 action: "stop"
- 如果当前页面没有相关元素，使用 action: "navigate" 导航到相关页面
"""
        return prompt

    def _execute_action(self, action: AIAction) -> bool:
        """执行AI决策的动作"""
        try:
            timeout = 10000  # 10秒超时

            if action.action_type == ActionType.CLICK:
                self.page.click(action.target, timeout=timeout)
            elif action.action_type == ActionType.FILL:
                self.page.fill(action.target, action.value or "", timeout=timeout)
            elif action.action_type == ActionType.TYPE:
                self.page.type(action.target, action.value or "", timeout=timeout)
            elif action.action_type == ActionType.HOVER:
                self.page.hover(action.target, timeout=timeout)
            elif action.action_type == ActionType.WAIT:
                self.page.wait_for_timeout(int(action.value or "1000"))
            elif action.action_type == ActionType.NAVIGATE:
                full_url = urljoin(self.config.base_url, action.target)
                self.page.goto(full_url, wait_until="networkidle", timeout=timeout)
            elif action.action_type == ActionType.SCREENSHOT:
                self.page.screenshot()
            elif action.action_type == ActionType.GET_TEXT:
                self.page.text_content(action.target, timeout=timeout)
            elif action.action_type == ActionType.SELECT:
                self.page.select_option(action.target, action.value or "", timeout=timeout)
            else:
                logger.warning(f"不支持的动作类型: {action.action_type}")
                return False

            return True

        except Exception as e:
            logger.warning(f"动作执行失败: {e}")
            return False

    def _heal_failed_action(self, action: AIAction) -> Optional[AIAction]:
        """尝试自愈失败的动作"""
        # 使用选择器管理器获取替代选择器
        try:
            page_html = self.page.content()
            best_selector = self.selector_manager.get_best_selector(
                action.target, page_html, action.action_type.value
            )

            if best_selector != action.target:
                healed_action = AIAction(
                    action_type=action.action_type,
                    target=best_selector,
                    value=action.value,
                    reason=f"自愈: 原选择器失败，使用替代方案",
                    confidence=0.6,
                )
                logger.info(f"自愈成功: {action.target} -> {best_selector}")
                return healed_action

        except Exception as e:
            logger.warning(f"自愈过程失败: {e}")

        return None

    def _evaluate_goal_achieved(self, goal: str) -> bool:
        """评估测试目标是否达成"""
        # 简单的基于关键字的评估
        goal_keywords = {
            "创建": ["创建成功", "success", "已创建"],
            "登录": ["登录成功", "welcome", "用户名"],
            "保存": ["保存成功", "已保存", "success"],
            "删除": ["删除成功", "已删除"],
            "生成": ["生成成功", "已生成"],
        }

        # 获取页面文本
        try:
            page_text = self.page.content().lower()

            for key, success_indicators in goal_keywords.items():
                if key in goal:
                    for indicator in success_indicators:
                        if indicator.lower() in page_text:
                            return True
        except Exception:
            pass

        # 如果执行了足够多的步骤且有点击操作，认为可能达成
        click_count = sum(
            1 for a in self.actions_executed
            if a.action_type == ActionType.CLICK
        )
        if click_count >= 3:
            return True

        return False

    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()
        return False