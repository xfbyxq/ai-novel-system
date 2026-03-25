"""
AI增强型E2E测试模块

基于Playwright + Healenium混合架构的智能测试框架
支持AI自动生成测试用例、全AI自动执行、测试自愈机制
"""

__version__ = "1.0.0"

from tests.ai_e2e.runners.hybrid_runner import HybridRunner
from tests.ai_e2e.agents.test_executor import AITestExecutor
from tests.ai_e2e.agents.test_generator import TestGenerator

__all__ = [
    "HybridRunner",
    "AITestExecutor",
    "TestGenerator",
]