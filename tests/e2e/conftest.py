"""E2E测试配置文件"""
import os
import pytest
from playwright.sync_api import Page, Browser, BrowserContext
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def pytest_configure(config):
    """pytest配置钩子"""
    config.addinivalue_line(
        "markers", "ui: mark test as UI test"
    )
    config.addinivalue_line(
        "markers", "smoke: mark test as smoke test"
    )
    config.addinivalue_line(
        "markers", "regression: mark test as regression test"
    )
    config.addinivalue_line(
        "markers", "creation: mark test as creation flow test"
    )
    config.addinivalue_line(
        "markers", "planning: mark test as planning flow test"
    )
    config.addinivalue_line(
        "markers", "outline: mark test as outline flow test"
    )
    config.addinivalue_line(
        "markers", "chapter: mark test as chapter flow test"
    )


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """
    浏览器启动参数配置
    
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
        ]
    }


@pytest.fixture(scope="session")
def browser_context_args():
    """
    浏览器上下文参数配置
    
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
    基础URL配置
    
    Returns:
        str: 应用的基础URL
    """
    return os.getenv("FRONTEND_URL", "http://localhost:3000")


@pytest.fixture
def api_base_url():
    """
    API基础URL配置
    
    Returns:
        str: API的基础URL
    """
    return os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture
def page(browser: Browser, browser_context_args: dict, base_url: str) -> Page:
    """
    页面fixture - 为每个测试提供一个新的页面实例
    
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
    # TODO: 实现具体的认证逻辑
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
            "password": "testpassword123"
        },
        "novel": {
            "title": "测试小说",
            "genre": "仙侠",
            "tags": ["热血", "升级流"],
            "synopsis": "这是一个测试小说的简介内容。",
            "length_type": "长篇"
        },
        "chapter": {
            "number": 1,
            "title": "第一章 测试章节",
            "content": "这是测试章节的内容..."
        }
    }