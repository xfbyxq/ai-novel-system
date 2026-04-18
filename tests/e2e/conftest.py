"""
E2E测试配置文件

E2E测试用例编号方案:
+------------------+----------------------------------+---------------+
| 编号             | 测试模块                         | 依赖         |
+------------------+----------------------------------+---------------+
| E2E-01           | 小说创建 (test_小说创建.py)       | 无           |
| E2E-02           | 小说查看 (test_小说查看.py)       | E2E-01       |
| E2E-03           | 大纲查看 (test_大纲查看.py)       | E2E-01       |
| E2E-04           | 世界观查看 (test_世界观查看.py)    | E2E-01       |
| E2E-05           | 章节查看 (test_小说章节查看.py)    | E2E-01,07    |
| E2E-06           | 企划任务 (test_添加企划任务.py)   | E2E-01       |
| E2E-07           | 章节生成 (test_chapter_flow.py)   | E2E-01       |
| E2E-08           | 批量生成 (test_批量生成小说任务.py)| E2E-01       |
| E2E-09           | 创作流程 (test_creation_flow.py)  | E2E-01       |
| E2E-10           | 大纲流程 (test_outline_flow.py)   | E2E-01       |
| E2E-11           | 工作流 (test_working_flow.py)     | E2E-01,07    |
| E2E-12           | 最终流程 (test_final_flow.py)     | E2E-01~11    |
+------------------+----------------------------------+---------------+

测试执行顺序建议:
1. 先执行 E2E-01 (小说创建) - 基础测试
2. 然后并行执行 E2E-02~06 (查看类测试)
3. 接着执行 E2E-07~08 (生成类测试)
4. 最后执行 E2E-09~12 (端到端流程测试)
"""

import os
import uuid
import pytest
import requests
from playwright.sync_api import Page, Browser
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def pytest_configure(config):
    """pytest配置钩子."""
    # 测试用例标记
    config.addinivalue_line("markers", "e2e01: E2E-01 小说创建基础测试")
    config.addinivalue_line("markers", "e2e02: E2E-02 小说查看测试")
    config.addinivalue_line("markers", "e2e03: E2E-03 大纲查看测试")
    config.addinivalue_line("markers", "e2e04: E2E-04 世界观查看测试")
    config.addinivalue_line("markers", "e2e05: E2E-05 章节查看测试")
    config.addinivalue_line("markers", "e2e06: E2E-06 企划任务测试")
    config.addinivalue_line("markers", "e2e07: E2E-07 章节生成测试")
    config.addinivalue_line("markers", "e2e08: E2E-08 批量生成测试")
    config.addinivalue_line("markers", "e2e09: E2E-09 创作流程测试")
    config.addinivalue_line("markers", "e2e10: E2E-10 大纲流程测试")
    config.addinivalue_line("markers", "e2e11: E2E-11 工作流测试")
    config.addinivalue_line("markers", "e2e12: E2E-12 最终流程测试")
    
    # 功能标记
    config.addinivalue_line("markers", "ui: mark test as UI test")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")
    config.addinivalue_line("markers", "regression: mark test as regression test")
    config.addinivalue_line("markers", "creation: mark test as creation flow test")
    config.addinivalue_line("markers", "planning: mark test as planning flow test")
    config.addinivalue_line("markers", "outline: mark test as outline flow test")
    config.addinivalue_line("markers", "chapter: mark test as chapter flow test")


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """
    浏览器启动参数配置.

    Returns:
        dict: 浏览器启动参数
    """
    return {
        "headless": os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true",
        "slow_mo": int(os.getenv("PLAYWRIGHT_SLOW_MO", "1000")),
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    }


@pytest.fixture(scope="session")
def browser_context_args():
    """
    浏览器上下文参数配置.

    Returns:
        dict: 浏览器上下文参数
    """
    return {
        "viewport": {"width": 1920, "height": 1080},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
        "permissions": ["clipboard-read", "clipboard-write"],
    }


@pytest.fixture(scope="session")
def base_url():
    """
    基础URL配置.

    Returns:
        str: 应用的基础URL
    """
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture
def api_base_url():
    """
    API基础URL配置.

    Returns:
        str: API的基础URL
    """
    return os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture
def page(browser: Browser, browser_context_args: dict, base_url: str) -> Page:
    """
    页面fixture - 为每个测试提供一个新的页面实例.

    Args:
        browser: 浏览器实例
        browser_context_args: 浏览器上下文参数
        base_url: 基础URL

    Yields:
        Page: Playwright页面实例
    """
    # 创建新的浏览器上下文
    context = browser.new_context(**browser_context_args)

    # 设置默认超时
    context.set_default_timeout(10000)
    context.set_default_navigation_timeout(30000)

    # 创建新页面
    page = context.new_page()

    # 存储base_url供页面对象使用
    page.base_url = base_url

    # 导航到基础URL
    page.goto(base_url)

    # 等待页面加载
    page.wait_for_load_state("networkidle", timeout=10000)

    yield page

    # 测试结束后关闭上下文
    context.close()


@pytest.fixture
def authenticated_page(page: Page):
    """
    已认证的页面fixture
    可以在这里实现登录逻辑

    Args:
        page: 页面实例

    Returns:
        Page: 已认证的页面实例
    """
    # FIXME: 实现具体的认证逻辑 - 跟踪于 GitHub Issue #21
    # 例如：使用预设账户登录或设置认证cookie
    return page


@pytest.fixture
def test_data():
    """
    测试数据fixture

    Returns:
        dict: 常用测试数据
    """
    return {
        "valid_user": {
            "username": "testuser@example.com",
            "password": "testpassword123",
        },
        "novel": {
            "title": "测试小说",
            "genre": "仙侠",
            "tags": ["热血", "升级流"],
            "synopsis": "这是一个测试小说的简介内容。",
            "length_type": "长篇",
        },
        "chapter": {
            "number": 1,
            "title": "第一章 测试章节",
            "content": "这是测试章节的内容...",
        },
    }


@pytest.fixture
def test_novel_id(api_base_url: str):
    """
    创建一个测试小说并返回其ID.
    用于需要访问小说详情页的测试.

    Args:
        api_base_url: API基础URL

    Yields:
        str: 创建的小说ID
    """
    # 生成唯一的小说标题
    unique_title = f"E2E测试小说_{uuid.uuid4().hex[:8]}"

    # 通过API创建小说
    response = requests.post(
        f"{api_base_url}/api/v1/novels",
        json={
            "title": unique_title,
            "genre": "仙侠",
            "synopsis": "自动化E2E测试创建的小说",
        },
        timeout=10
    )

    if response.status_code in (200, 201):
        novel_id = response.json()["id"]
        yield str(novel_id)
        # 清理：删除测试小说
        try:
            requests.delete(f"{api_base_url}/api/v1/novels/{novel_id}", timeout=5)
        except Exception:
            pass  # 忽略清理失败
    else:
        # 如果创建失败，抛出异常
        raise RuntimeError(f"创建测试小说失败: {response.status_code} - {response.text}")


@pytest.fixture
def test_novel_page(page: Page, test_novel_id: str, base_url: str):
    """
    导航到测试小说详情页的Page fixture.

    Args:
        page: Playwright页面对象
        test_novel_id: 测试小说ID
        base_url: 基础URL

    Yields:
        Page: 已导航到小说详情页的Page对象
    """
    page.goto(f"{base_url}/novels/{test_novel_id}")
    page.wait_for_load_state("networkidle")
    yield page
