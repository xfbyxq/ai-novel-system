"""具体的Agent实现."""

import asyncio
from typing import Dict, Any

from agents.agent_communicator import AgentCommunicator
from agents.agent_scheduler import BaseAgent
from llm.qwen_client import QwenClient
from llm.prompt_manager import PromptManager
from llm.cost_tracker import CostTracker

# Use the project-wide logger
from core.logging_config import logger


class MarketAnalysisAgent(BaseAgent):
    """市场分析Agent."""

    def __init__(
        self,
        name: str,
        communicator: AgentCommunicator,
        qwen_client: QwenClient,
        cost_tracker: CostTracker,
    ):
        """初始化市场分析Agent.

        Args:
            name: Agent名称
            communicator: 通信管理器
            qwen_client: 通义千问客户端
            cost_tracker: 成本跟踪器
        """
        super().__init__(name, communicator)
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

    async def _process_task(self, task_data: Dict[str, Any]):
        """处理任务.

        Args:
            task_data: 任务数据
        """
        self.status = "busy"

        try:
            # 提取任务信息
            task_id = task_data.get("task_id")
            task_name = task_data.get("task_name")
            input_data = task_data.get("input_data", {})

            logger.info(f"📊 开始市场分析任务: {task_name}")

            # 获取市场数据
            market_data = input_data.get("market_data", [])
            platform = input_data.get("platform", "all")

            # 构建分析提示词
            analysis_task = self.pm.format(
                self.pm.MARKET_ANALYST_TASK,
                market_data=str(market_data),
                platform=platform,
            )

            # 调用LLM进行分析
            response = await self.client.chat(
                prompt=analysis_task,
                system=self.pm.MARKET_ANALYST_SYSTEM,
                temperature=0.7,
                max_tokens=2048,
            )

            # 记录成本
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self.name,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            # 处理分析结果
            analysis_result = {
                "platform": platform,
                "trending_topics": [],
                "popular_genres": [],
                "recommended_tags": [],
                "market_insights": response["content"],
            }

            logger.info(f"📊 市场分析任务完成: {task_name}")

            # 发送任务完成消息
            from agents.agent_communicator import Message

            completion_message = Message(
                sender=self.name,
                receiver="scheduler",
                message_type="task_completion",
                content={
                    "task_id": task_id,
                    "status": "completed",
                    "result": analysis_result,
                },
            )

            # 发送消息给调度器
            await self.communicator.send_message(completion_message)
            logger.debug(f"📊 市场分析结果: {analysis_result}")

        except Exception as e:
            logger.error(f"❌ 市场分析任务失败: {e}")
            self.status = "error"
        finally:
            self.status = "idle"


class ContentPlanningAgent(BaseAgent):
    """内容策划Agent."""

    def __init__(
        self,
        name: str,
        communicator: AgentCommunicator,
        qwen_client: QwenClient,
        cost_tracker: CostTracker,
    ):
        """初始化内容策划Agent.

        Args:
            name: Agent名称
            communicator: 通信管理器
            qwen_client: 通义千问客户端
            cost_tracker: 成本跟踪器
        """
        super().__init__(name, communicator)
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

    async def _process_task(self, task_data: Dict[str, Any]):
        """处理任务.

        Args:
            task_data: 任务数据
        """
        self.status = "busy"

        try:
            # 提取任务信息
            task_id = task_data.get("task_id")
            task_name = task_data.get("task_name")
            input_data = task_data.get("input_data", {})

            logger.info(f"🎯 开始内容策划任务: {task_name}")

            # 获取市场分析结果
            market_analysis = input_data.get("market_analysis", {})
            user_preferences = input_data.get("user_preferences", {})

            # 构建策划提示词
            planning_task = self.pm.format(
                self.pm.CONTENT_PLANNER_TASK,
                market_analysis=str(market_analysis),
                user_preferences=str(user_preferences),
            )

            # 调用LLM进行策划
            response = await self.client.chat(
                prompt=planning_task,
                system=self.pm.CONTENT_PLANNER_SYSTEM,
                temperature=0.8,
                max_tokens=3072,
            )

            # 记录成本
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self.name,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            # 处理策划结果
            planning_result = {
                "novel_title": "",
                "genre": "",
                "tags": [],
                "synopsis": "",
                "target_audience": "",
                "content_plan": response["content"],
            }

            logger.info(f"🎯 内容策划任务完成: {task_name}")

            # 发送任务完成消息
            from agents.agent_communicator import Message

            completion_message = Message(
                sender=self.name,
                receiver="scheduler",
                message_type="task_completion",
                content={
                    "task_id": task_id,
                    "status": "completed",
                    "result": planning_result,
                },
            )

            # 发送消息给调度器
            await self.communicator.send_message(completion_message)
            logger.debug(f"🎯 内容策划结果: {planning_result}")

        except Exception as e:
            logger.error(f"❌ 内容策划任务失败: {e}")
            self.status = "error"
        finally:
            self.status = "idle"


class WritingAgent(BaseAgent):
    """创作Agent."""

    def __init__(
        self,
        name: str,
        communicator: AgentCommunicator,
        qwen_client: QwenClient,
        cost_tracker: CostTracker,
    ):
        """初始化创作Agent.

        Args:
            name: Agent名称
            communicator: 通信管理器
            qwen_client: 通义千问客户端
            cost_tracker: 成本跟踪器
        """
        super().__init__(name, communicator)
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

    async def _process_task(self, task_data: Dict[str, Any]):
        """处理任务.

        Args:
            task_data: 任务数据
        """
        self.status = "busy"

        try:
            # 提取任务信息
            task_id = task_data.get("task_id")
            task_name = task_data.get("task_name")
            input_data = task_data.get("input_data", {})

            logger.info(f"✍️  开始创作任务: {task_name}")

            # 获取创作所需信息
            content_plan = input_data.get("content_plan", {})
            chapter_number = input_data.get("chapter_number", 1)
            world_setting = input_data.get("world_setting", {})
            characters = input_data.get("characters", [])
            input_data.get("plot_outline", {})

            # 构建创作提示词
            writing_task = self.pm.format(
                self.pm.WRITER_TASK,
                chapter_number=chapter_number,
                chapter_plan=str(content_plan),
                world_setting_brief=str(world_setting),
                character_info=str(characters),
                previous_ending="",
                chapter_title=content_plan.get("title", f"第{chapter_number}章"),
            )

            # 调用LLM进行创作
            response = await self.client.chat(
                prompt=writing_task,
                system=self.pm.WRITER_SYSTEM,
                temperature=0.85,
                max_tokens=4096,
            )

            # 记录成本
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self.name,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            # 处理创作结果
            writing_result = {
                "chapter_number": chapter_number,
                "chapter_title": content_plan.get("title", f"第{chapter_number}章"),
                "content": response["content"],
                "word_count": len(response["content"]),
            }

            logger.info(f"✍️  创作任务完成: {task_name}")

            # 发送任务完成消息
            from agents.agent_communicator import Message

            completion_message = Message(
                sender=self.name,
                receiver="scheduler",
                message_type="task_completion",
                content={
                    "task_id": task_id,
                    "status": "completed",
                    "result": writing_result,
                },
            )

            # 发送消息给调度器
            await self.communicator.send_message(completion_message)
            logger.debug(
                f"✍️  创作结果: 第{chapter_number}章，{len(response['content'])}字"
            )

        except Exception as e:
            logger.error(f"❌ 创作任务失败: {e}")
            self.status = "error"
        finally:
            self.status = "idle"


class EditingAgent(BaseAgent):
    """编辑Agent."""

    def __init__(
        self,
        name: str,
        communicator: AgentCommunicator,
        qwen_client: QwenClient,
        cost_tracker: CostTracker,
    ):
        """初始化编辑Agent.

        Args:
            name: Agent名称
            communicator: 通信管理器
            qwen_client: 通义千问客户端
            cost_tracker: 成本跟踪器
        """
        super().__init__(name, communicator)
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

    async def _process_task(self, task_data: Dict[str, Any]):
        """处理任务.

        Args:
            task_data: 任务数据
        """
        self.status = "busy"

        try:
            # 提取任务信息
            task_id = task_data.get("task_id")
            task_name = task_data.get("task_name")
            input_data = task_data.get("input_data", {})

            logger.info(f"📝 开始编辑任务: {task_name}")

            # 获取待编辑内容
            draft_content = input_data.get("draft_content", "")
            chapter_number = input_data.get("chapter_number", 1)
            chapter_title = input_data.get("chapter_title", f"第{chapter_number}章")
            chapter_summary = input_data.get("chapter_summary", "")

            # 构建编辑提示词
            editing_task = self.pm.format(
                self.pm.EDITOR_TASK,
                draft_content=draft_content,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                chapter_summary=chapter_summary,
            )

            # 调用LLM进行编辑
            response = await self.client.chat(
                prompt=editing_task,
                system=self.pm.EDITOR_SYSTEM,
                temperature=0.6,
                max_tokens=4096,
            )

            # 记录成本
            usage = response["usage"]
            self.cost_tracker.record(
                agent_name=self.name,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            )

            # 处理编辑结果
            editing_result = {
                "chapter_number": chapter_number,
                "original_content": draft_content,
                "edited_content": response["content"],
                "word_count": len(response["content"]),
            }

            logger.info(f"📝 编辑任务完成: {task_name}")

            # 发送任务完成消息
            from agents.agent_communicator import Message

            completion_message = Message(
                sender=self.name,
                receiver="scheduler",
                message_type="task_completion",
                content={
                    "task_id": task_id,
                    "status": "completed",
                    "result": editing_result,
                },
            )

            # 发送消息给调度器
            await self.communicator.send_message(completion_message)
            logger.debug(f"📝 编辑结果: {len(response['content'])}字")

        except Exception as e:
            logger.error(f"❌ 编辑任务失败: {e}")
            self.status = "error"
        finally:
            self.status = "idle"


class PublishingAgent(BaseAgent):
    """发布Agent."""

    def __init__(
        self,
        name: str,
        communicator: AgentCommunicator,
        qwen_client: QwenClient,
        cost_tracker: CostTracker,
    ):
        """初始化发布Agent.

        Args:
            name: Agent名称
            communicator: 通信管理器
            qwen_client: 通义千问客户端
            cost_tracker: 成本跟踪器
        """
        super().__init__(name, communicator)
        self.client = qwen_client
        self.cost_tracker = cost_tracker
        self.pm = PromptManager

    async def _process_task(self, task_data: Dict[str, Any]):
        """处理任务.

        Args:
            task_data: 任务数据
        """
        self.status = "busy"

        try:
            # 提取任务信息
            task_id = task_data.get("task_id")
            task_name = task_data.get("task_name")
            input_data = task_data.get("input_data", {})

            logger.info(f"🚀 开始发布任务: {task_name}")

            # 获取发布所需信息
            novel_data = input_data.get("novel_data", {})
            chapter_data = input_data.get("chapter_data", {})
            platform = input_data.get("platform", "qidian")
            input_data.get("account_id")

            # 模拟发布过程
            # 实际实现中，这里应该调用发布服务
            publish_result = {
                "platform": platform,
                "novel_title": novel_data.get("title", "未命名小说"),
                "chapter_number": chapter_data.get("chapter_number", 1),
                "publish_status": "success",
                "publish_time": asyncio.get_event_loop().time(),
                "platform_book_id": f"book_{platform}_{novel_data.get('id', '0')}",
                "platform_chapter_id": f"chapter_{platform}_{chapter_data.get('chapter_number', '1')}",
            }

            logger.info(f"🚀 发布任务完成: {task_name}")

            # 发送任务完成消息
            from agents.agent_communicator import Message

            completion_message = Message(
                sender=self.name,
                receiver="scheduler",
                message_type="task_completion",
                content={
                    "task_id": task_id,
                    "status": "completed",
                    "result": publish_result,
                },
            )

            # 发送消息给调度器
            await self.communicator.send_message(completion_message)
            logger.debug(f"🚀 发布结果: {platform} 平台发布成功")

        except Exception as e:
            logger.error(f"❌ 发布任务失败: {e}")
            self.status = "error"
        finally:
            self.status = "idle"
