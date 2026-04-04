"""Agent依赖注入容器."""

from functools import lru_cache
from typing import Optional

from agents.crew_manager import NovelCrewManager
from agents.outline_quality_evaluator import OutlineQualityEvaluator
from agents.outline_refiner import OutlineRefiner
from llm.cost_tracker import CostTracker
from llm.qwen_client import QwenClient


class AgentDependencies:
    """Agent依赖管理器."""

    def __init__(self):
        """初始化方法."""
        self._qwen_client: Optional[QwenClient] = None
        self._cost_tracker: Optional[CostTracker] = None
        self._crew_manager: Optional[NovelCrewManager] = None
        self._outline_refiner: Optional[OutlineRefiner] = None
        self._outline_evaluator: Optional[OutlineQualityEvaluator] = None

    @property
    def qwen_client(self) -> QwenClient:
        """获取Qwen客户端实例."""
        if self._qwen_client is None:
            self._qwen_client = QwenClient()
        return self._qwen_client

    @property
    def cost_tracker(self) -> CostTracker:
        """获取成本跟踪器实例."""
        if self._cost_tracker is None:
            self._cost_tracker = CostTracker()
        return self._cost_tracker

    @property
    def crew_manager(self) -> NovelCrewManager:
        """获取Crew管理器实例."""
        if self._crew_manager is None:
            self._crew_manager = NovelCrewManager(
                qwen_client=self.qwen_client, cost_tracker=self.cost_tracker
            )
        return self._crew_manager

    @property
    def outline_refiner(self) -> OutlineRefiner:
        """获取大纲细化器实例."""
        if self._outline_refiner is None:
            self._outline_refiner = OutlineRefiner(
                client=self.qwen_client, cost_tracker=self.cost_tracker
            )
        return self._outline_refiner

    @property
    def outline_evaluator(self) -> OutlineQualityEvaluator:
        """获取大纲质量评估器实例."""
        if self._outline_evaluator is None:
            self._outline_evaluator = OutlineQualityEvaluator(
                client=self.qwen_client, cost_tracker=self.cost_tracker
            )
        return self._outline_evaluator

    def reset(self):
        """重置所有依赖实例."""
        self._qwen_client = None
        self._cost_tracker = None
        self._crew_manager = None
        self._outline_refiner = None
        self._outline_evaluator = None


# 全局依赖容器实例
@lru_cache(maxsize=1)
def get_agent_dependencies() -> AgentDependencies:
    """获取全局Agent依赖容器（单例模式）."""
    return AgentDependencies()


# 便捷的依赖获取函数
def get_crew_manager() -> NovelCrewManager:
    """获取Crew管理器实例."""
    return get_agent_dependencies().crew_manager


def get_outline_refiner() -> OutlineRefiner:
    """获取大纲细化器实例."""
    return get_agent_dependencies().outline_refiner


def get_outline_evaluator() -> OutlineQualityEvaluator:
    """获取大纲质量评估器实例."""
    return get_agent_dependencies().outline_evaluator


def get_qwen_client() -> QwenClient:
    """获取Qwen客户端实例."""
    return get_agent_dependencies().qwen_client


def get_cost_tracker() -> CostTracker:
    """获取成本跟踪器实例."""
    return get_agent_dependencies().cost_tracker
