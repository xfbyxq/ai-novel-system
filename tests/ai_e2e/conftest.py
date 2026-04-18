"""AI E2E 测试配置 — fixtures、markers 和 MCP 工具注入.

MCP 工具通过 conftest 注入到测试组件中，测试代码不直接依赖 MCP 框架。
实际的 MCP 工具调用需要在 Qoder 环境中通过 LoadMcp 加载 chrome-devtools server。
"""

from __future__ import annotations

import os

import pytest

from tests.ai_e2e.agents.llm_evaluator import LLMEvaluator
from tests.ai_e2e.agents.self_healer import SelfHealer
from tests.ai_e2e.agents.ui_test_orchestrator import UITestOrchestrator
from tests.ai_e2e.tools.mcp_executor import MCPExecutor
from tests.ai_e2e.tools.snapshot_resolver import SnapshotResolver


def pytest_configure(config: pytest.Config) -> None:
    """注册 AI E2E 测试标记."""
    config.addinivalue_line("markers", "ai_e2e: AI-driven E2E test using LLM + MCP")
    config.addinivalue_line("markers", "ai_smoke: AI smoke test (P0 only)")
    config.addinivalue_line("markers", "ai_regression: AI regression test")


@pytest.fixture(scope="session")
def base_url() -> str:
    """前端基础 URL."""
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """后端 API 基础 URL."""
    return os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def qwen_client():
    """QwenClient 单例实例."""
    from llm.qwen_client import qwen_client

    return qwen_client


@pytest.fixture(scope="session")
def snapshot_resolver() -> SnapshotResolver:
    """快照解析器实例."""
    return SnapshotResolver()


@pytest.fixture
def self_healer(qwen_client) -> SelfHealer:
    """LLM 自愈器实例."""
    return SelfHealer(qwen_client=qwen_client, temperature=0.1)


@pytest.fixture
def llm_evaluator(qwen_client, snapshot_resolver) -> LLMEvaluator:
    """LLM 断言评估器实例."""
    return LLMEvaluator(
        qwen_client=qwen_client,
        resolver=snapshot_resolver,
        confidence_threshold=0.7,
        temperature=0.1,
    )


@pytest.fixture
def mcp_executor(snapshot_resolver, self_healer, mcp_tools) -> MCPExecutor:
    """MCP 执行器实例 — 通过 mcp_tools fixture 注入 MCP 工具函数.

    mcp_tools fixture 需要由具体测试环境提供，
    包含所有必要的 MCP 工具 callable。
    """
    return MCPExecutor(
        mcp_navigate=mcp_tools["navigate"],
        mcp_click=mcp_tools["click"],
        mcp_fill=mcp_tools["fill"],
        mcp_press_key=mcp_tools["press_key"],
        mcp_wait_for=mcp_tools["wait_for"],
        mcp_take_snapshot=mcp_tools["take_snapshot"],
        mcp_take_screenshot=mcp_tools["take_screenshot"],
        resolver=snapshot_resolver,
        self_healer=self_healer,
        retry_count=2,
    )


@pytest.fixture
def orchestrator(mcp_executor, llm_evaluator) -> UITestOrchestrator:
    """UI 测试编排器实例."""
    return UITestOrchestrator(
        executor=mcp_executor,
        evaluator=llm_evaluator,
        case_timeout=120,
        enable_screenshot_on_failure=True,
    )
