"""AI E2E 测试用例数据结构定义.

基于 Pydantic 的结构化测试用例 Schema，支持：
- ElementRef: 语义元素引用（运行时通过 a11y 快照解析为 UID）
- TestStep: 单个测试步骤（映射到 MCP 工具调用）
- TestAssertion: 混合断言（规则 + LLM 语义）
- TestCase / TestSuite: 测试用例和套件
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ElementRef(BaseModel):
    """元素引用 — 用语义描述定位，运行时解析为 a11y UID.

    chrome-devtools MCP 使用 a11y 快照 UID 定位元素，UID 是临时的，
    因此测试用例中用 role + name 的语义描述来标识目标元素，
    由 SnapshotResolver 在运行时匹配到当前快照的 UID。
    """

    role: str | None = None
    """a11y 角色，如 button / textbox / combobox / menuitem 等"""

    name: str
    """元素的可访问名称或文本内容，如 '创建小说' / '* 标题'"""

    fallback_name: str | None = None
    """备选名称 — UI 文本变更后的兜底匹配"""


class TestStep(BaseModel):
    """单个测试步骤 — 运行时通过快照 UID 映射到 MCP 工具调用.

    action 与 MCP 工具的映射关系：
    - navigate → mcp__chrome-devtools__navigate_page
    - click    → mcp__chrome-devtools__click(uid)
    - fill     → mcp__chrome-devtools__fill(uid, value)
    - press_key → mcp__chrome-devtools__press_key(key)
    - wait_for → mcp__chrome-devtools__wait_for(text)
    - screenshot / snapshot → 对应 MCP 截图/快照工具
    - assert_* → 由 Evaluator 在快照上验证，不直接调用 MCP
    """

    __test__ = False

    __test__ = False

    action: Literal[
        "navigate",
        "click",
        "fill",
        "press_key",
        "wait_for",
        "assert_visible",
        "assert_text",
        "assert_url",
        "assert_count",
        "screenshot",
        "snapshot",
    ]
    """操作类型"""

    element: ElementRef | None = None
    """语义元素引用 — navigate / wait_for / screenshot / snapshot 时可为 None"""

    url: str | None = None
    """目标 URL — 仅 navigate 使用"""

    value: str | None = None
    """操作值 — fill 的输入值 / press_key 的按键 / wait_for 的等待文本"""

    description: str
    """步骤的中文自然语言描述"""

    timeout_ms: int = 10000
    """超时时间（毫秒）"""


class RuleAssertion(BaseModel):
    """规则断言 — 确定性验证，零 LLM 开销."""

    check: Literal[
        "element_visible",
        "element_hidden",
        "text_contains",
        "url_matches",
        "element_count",
    ]
    """断言检查类型"""

    element: ElementRef | None = None
    """目标元素（语义引用）"""

    expected: str | int | None = None
    """期望值 — text_contains 的文本 / url_matches 的模式 / element_count 的数量"""


class TestAssertion(BaseModel):
    """断言定义 — 支持规则、LLM、混合三种模式.

    - rule_based: 确定性 100%，零 token 开销
    - llm_judged: LLM 语义判断，灵活但有 token 成本
    - hybrid: 规则优先，不确定时 LLM 辅助
    """

    __test__ = False

    __test__ = False

    type: Literal["rule_based", "llm_judged", "hybrid"]
    """断言模式"""

    rule_assertion: RuleAssertion | None = None
    """规则断言定义 — rule_based / hybrid 模式使用"""

    llm_assertion: str | None = None
    """自然语言断言描述 — llm_judged / hybrid 模式使用"""

    severity: Literal["critical", "major", "minor"] = "major"
    """断言严重级别"""


class TestCase(BaseModel):
    """完整测试用例."""

    __test__ = False

    id: str
    """用例编号，如 'AI-E2E-NL-001'"""

    name: str
    """中文测试名称"""

    description: str
    """测试目标描述"""

    page: str
    """关联页面标识，如 'novel_list'"""

    category: Literal["smoke", "regression", "edge_case"]
    """测试分类"""

    priority: Literal["P0", "P1", "P2"]
    """优先级 — P0 为冒烟必跑"""

    preconditions: list[str] = Field(default_factory=list)
    """前置条件描述列表"""

    steps: list[TestStep]
    """测试步骤序列"""

    assertions: list[TestAssertion] = Field(default_factory=list)
    """步骤执行完毕后的断言列表"""

    cleanup: list[TestStep] | None = None
    """清理步骤（可选）"""

    tags: list[str] = Field(default_factory=list)
    """pytest 标记列表"""


class StepResult(BaseModel):
    """单步执行结果."""

    step_index: int
    """步骤序号"""

    status: Literal["passed", "failed", "skipped", "healed"]
    """执行状态 — healed 表示通过自愈成功"""

    resolved_uid: str | None = None
    """实际使用的 a11y UID"""

    error: str | None = None
    """错误信息"""

    healed_by: str | None = None
    """自愈使用的方法描述"""

    duration_ms: int = 0
    """步骤耗时（毫秒）"""


class AssertionResult(BaseModel):
    """断言执行结果."""

    assertion_index: int
    """断言序号"""

    passed: bool
    """是否通过"""

    reason: str = ""
    """判断理由"""

    confidence: float = 1.0
    """置信度 — 规则断言为 1.0，LLM 断言为模型返回值"""


class TestCaseResult(BaseModel):
    """测试用例执行结果."""

    __test__ = False

    test_case_id: str
    """关联的测试用例 ID"""

    status: Literal["passed", "failed", "error", "inconclusive"]
    """整体结果"""

    step_results: list[StepResult] = Field(default_factory=list)
    """每步执行结果"""

    assertion_results: list[AssertionResult] = Field(default_factory=list)
    """断言结果"""

    failure_reason: str | None = None
    """失败原因摘要"""

    screenshots: list[str] = Field(default_factory=list)
    """截图路径列表"""

    llm_token_usage: int = 0
    """LLM token 消耗量（仅自愈和断言）"""

    duration_ms: int = 0
    """总耗时（毫秒）"""


class SuiteResult(BaseModel):
    """测试套件执行结果."""

    suite_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    inconclusive: int = 0
    case_results: list[TestCaseResult] = Field(default_factory=list)
    total_llm_tokens: int = 0
    total_duration_ms: int = 0


class TestSuite(BaseModel):
    """测试套件 — 由 LLM 离线生成并存储为 JSON."""

    __test__ = False

    suite_name: str
    """套件名称"""

    generated_at: str
    """生成时间（ISO 格式）"""

    generator_model: str
    """使用的 LLM 模型标识"""

    page_target: str
    """目标页面"""

    test_cases: list[TestCase]
    """测试用例列表"""
