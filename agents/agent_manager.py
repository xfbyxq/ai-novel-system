"""Agent管理器 - 负责初始化和管理所有Agent."""

import asyncio
from typing import Dict, Optional

from agents.agent_communicator import AgentCommunicator
from agents.agent_scheduler import AgentScheduler, BaseAgent
from agents.specific_agents import (
    MarketAnalysisAgent,
    ContentPlanningAgent,
    WritingAgent,
    EditingAgent,
    PublishingAgent,
)

# Use the project-wide logger
from core.logging_config import logger
from llm.qwen_client import QwenClient
from llm.cost_tracker import CostTracker


class AgentManager:
    """Agent管理器，负责初始化和管理所有Agent."""

    _instance = None

    def __new__(cls):
        """单例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化Agent管理器."""
        if not hasattr(self, "initialized"):
            self.initialized = False
            self.communicator = None
            self.scheduler = None
            self.agents = {}
            self.client = None
            self.cost_tracker = None

    async def initialize(self):
        """初始化Agent系统。

        - 创建通信管理器
        - 创建调度器
        - 初始化LLM客户端
        - 初始化成本跟踪器
        - 创建并注册所有Agent
        """
        if self.initialized:
            logger.info("🤖 Agent管理器已经初始化")
            return

        logger.info("🤖 开始初始化Agent系统...")

        # 创建通信管理器
        self.communicator = AgentCommunicator()

        # 创建调度器
        self.scheduler = AgentScheduler(self.communicator)

        # 初始化LLM客户端
        self.client = QwenClient()

        # 初始化成本跟踪器
        self.cost_tracker = CostTracker()

        # 创建并注册所有Agent
        await self._create_and_register_agents()

        self.initialized = True
        logger.info("🤖 Agent系统初始化完成！")

    async def _create_and_register_agents(self):
        """创建并注册所有Agent."""
        # 创建各种Agent
        market_agent = MarketAnalysisAgent(
            name="market_analysis_agent",
            communicator=self.communicator,
            qwen_client=self.client,
            cost_tracker=self.cost_tracker,
        )

        content_agent = ContentPlanningAgent(
            name="content_planning_agent",
            communicator=self.communicator,
            qwen_client=self.client,
            cost_tracker=self.cost_tracker,
        )

        writing_agent = WritingAgent(
            name="writing_agent",
            communicator=self.communicator,
            qwen_client=self.client,
            cost_tracker=self.cost_tracker,
        )

        editing_agent = EditingAgent(
            name="editing_agent",
            communicator=self.communicator,
            qwen_client=self.client,
            cost_tracker=self.cost_tracker,
        )

        publishing_agent = PublishingAgent(
            name="publishing_agent",
            communicator=self.communicator,
            qwen_client=self.client,
            cost_tracker=self.cost_tracker,
        )

        # 注册Agent到调度器
        agents_to_register = [
            market_agent,
            content_agent,
            writing_agent,
            editing_agent,
            publishing_agent,
        ]

        for agent in agents_to_register:
            await self.scheduler.register_agent(agent)
            self.agents[agent.name] = agent
            logger.info(f"🤖 注册Agent: {agent.name}")

    async def start(self):
        """启动所有Agent."""
        if not self.initialized:
            await self.initialize()

        logger.info("🤖 启动所有Agent...")

        # Agent在注册时已经启动，这里主要是确保所有Agent都处于运行状态
        for agent_name, agent in self.agents.items():
            if hasattr(agent, "status"):
                logger.info(f"🤖 Agent {agent_name} 状态: {agent.status}")

        logger.info("🤖 所有Agent启动完成！")

    async def stop(self):
        """停止所有Agent."""
        if not self.initialized:
            logger.info("🤖 Agent系统未初始化")
            return

        logger.info("🤖 停止所有Agent...")

        for agent_name, agent in self.agents.items():
            if hasattr(agent, "stop"):
                await agent.stop()
                logger.info(f"🤖 停止Agent: {agent_name}")

        self.initialized = False
        logger.info("🤖 所有Agent停止完成！")

    def get_scheduler(self) -> Optional[AgentScheduler]:
        """获取调度器。

        Returns:
            AgentScheduler: 调度器实例
        """
        return self.scheduler

    def get_agent(self, agent_name: str) -> Optional[object]:
        """获取指定Agent。

        Args:
            agent_name: Agent名称

        Returns:
            object: Agent实例
        """
        return self.agents.get(agent_name)

    def get_all_agents(self) -> Dict[str, object]:
        """获取所有Agent。

        Returns:
            Dict[str, object]: Agent名称到实例的映射
        """
        return self.agents

    async def get_agent_status(self, agent_name: str) -> Optional[str]:
        """获取Agent状态。

        Args:
            agent_name: Agent名称

        Returns:
            str: Agent状态
        """
        if not self.initialized:
            return None

        return await self.scheduler.get_agent_status(agent_name)

    async def get_all_agent_statuses(self) -> Dict[str, str]:
        """获取所有Agent状态。

        Returns:
            Dict[str, str]: Agent名称到状态的映射
        """
        if not self.initialized:
            return {}

        statuses = {}
        for agent_name in self.agents:
            status = await self.get_agent_status(agent_name)
            if status:
                statuses[agent_name] = status

        return statuses


# 全局Agent管理器实例
global_agent_manager = AgentManager()


def get_agent_manager() -> AgentManager:
    """获取全局Agent管理器实例。

    Returns:
        AgentManager: 全局Agent管理器实例
    """
    return global_agent_manager
