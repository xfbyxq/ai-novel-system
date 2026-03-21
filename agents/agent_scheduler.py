"""Agent调度系统"""

import asyncio
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from uuid import UUID, uuid4

from agents.agent_communicator import AgentCommunicator, Message

# Use the project-wide logger
from core.logging_config import logger


class AgentStatus(str, Enum):
    """Agent状态"""

    IDLE = "idle"  # 空闲
    BUSY = "busy"  # 忙碌
    ERROR = "error"  # 错误
    OFFLINE = "offline"  # 离线


class TaskPriority(int, Enum):
    """任务优先级"""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    URGENT = 3


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"  # 待处理
    ASSIGNED = "assigned"  # 已分配
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class AgentTask:
    """Agent任务"""

    def __init__(
        self,
        task_id: Optional[UUID] = None,
        task_name: str = "",
        task_type: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: List[UUID] = None,
        input_data: Dict[str, Any] = None,
        expected_output: Dict[str, Any] = None,
        timeout: Optional[float] = None,
        callback: Optional[Callable] = None,
    ):
        """初始化任务

        Args:
            task_id: 任务ID
            task_name: 任务名称
            task_type: 任务类型
            priority: 优先级
            dependencies: 依赖的任务ID列表
            input_data: 输入数据
            expected_output: 期望输出格式
            timeout: 超时时间
            callback: 任务完成后的回调函数
        """
        self.task_id = task_id or uuid4()
        self.task_name = task_name
        self.task_type = task_type
        self.priority = priority
        self.dependencies = dependencies or []
        self.input_data = input_data or {}
        self.expected_output = expected_output or {}
        self.timeout = timeout
        self.callback = callback

        self.status = TaskStatus.PENDING
        self.assigned_agent = None
        self.start_time = None
        self.complete_time = None
        self.result = None
        self.error_message = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": str(self.task_id),
            "task_name": self.task_name,
            "task_type": self.task_type,
            "priority": (
                self.priority.value
                if hasattr(self.priority, "value")
                else int(self.priority)
            ),
            "dependencies": [str(dep) for dep in self.dependencies],
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "timeout": self.timeout,
            "status": (
                self.status.value if hasattr(self.status, "value") else str(self.status)
            ),
            "assigned_agent": self.assigned_agent,
            "start_time": self.start_time,
            "complete_time": self.complete_time,
            "result": self.result,
            "error_message": self.error_message,
        }


class BaseAgent:
    """基础Agent类"""

    def __init__(self, name: str, communicator: AgentCommunicator):
        """初始化Agent

        Args:
            name: Agent名称
            communicator: 通信管理器
        """
        self.name = name
        self.communicator = communicator
        self.status = AgentStatus.IDLE
        self.current_task = None
        self._running = True
        self._task_queue = asyncio.Queue()

    async def start(self):
        """启动Agent"""
        await self.communicator.register_agent(self.name)
        self.status = AgentStatus.IDLE
        logger.info(f"🤖 Agent '{self.name}' 已启动")

        # 启动消息处理循环
        asyncio.create_task(self._message_loop())
        # 启动任务处理循环
        asyncio.create_task(self._task_loop())

    async def stop(self):
        """停止Agent"""
        self._running = False
        self.status = AgentStatus.OFFLINE
        logger.info(f"🤖 Agent '{self.name}' 已停止")

    async def _message_loop(self):
        """消息处理循环"""
        while self._running:
            try:
                message = await self.communicator.receive_message(
                    self.name, timeout=1.0
                )
                if message:
                    await self._handle_message(message)
            except Exception as e:
                logger.error(f"❌ Agent '{self.name}' 消息处理错误: {e}")

    async def _handle_message(self, message: Message):
        """处理消息

        Args:
            message: 消息对象
        """
        logger.debug(f"🤖 Agent '{self.name}' 处理消息: {message.message_type}")

        # 处理不同类型的消息
        if message.message_type == "task_assignment":
            # 任务分配消息
            task_data = message.content.get("task")
            if task_data:
                await self._task_queue.put(task_data)
        elif message.message_type == "task_cancellation":
            # 任务取消消息
            task_id = message.content.get("task_id")
            if (
                task_id
                and self.current_task
                and str(self.current_task.task_id) == task_id
            ):
                logger.info(f"🤖 Agent '{self.name}' 取消任务: {task_id}")
                self.current_task.status = TaskStatus.CANCELLED
        elif message.message_type == "status_request":
            # 状态请求消息
            response = Message(
                sender=self.name,
                receiver=message.sender,
                message_type="status_response",
                content={
                    "status": (
                        self.status.value
                        if hasattr(self.status, "value")
                        else str(self.status)
                    ),
                    "current_task": (
                        str(self.current_task.task_id) if self.current_task else None
                    ),
                },
            )
            await self.communicator.send_message(response)

    async def _task_loop(self):
        """任务处理循环"""
        while self._running:
            try:
                task_data = await asyncio.wait_for(self._task_queue.get(), timeout=1.0)
                await self._process_task(task_data)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ Agent '{self.name}' 任务处理错误: {e}")
                self.status = AgentStatus.ERROR

    async def _process_task(self, task_data: Dict[str, Any]):
        """处理任务

        Args:
            task_data: 任务数据
        """
        # 这里应该由具体的Agent子类实现
        logger.warning(f"⚠️  Agent '{self.name}' 未实现任务处理方法")

        # 模拟任务完成，避免任务一直处于运行状态
        task_id = task_data.get("task_id")
        if task_id:
            try:
                from uuid import UUID

                task_id_uuid = UUID(task_id)
                await self.communicator.send_message(
                    Message(
                        sender=self.name,
                        receiver="scheduler",
                        message_type="task_completion",
                        content={
                            "task_id": task_id,
                            "status": "completed",
                            "result": {},
                        },
                    )
                )
            except Exception as e:
                logger.error(f"❌ Agent '{self.name}' 发送任务完成消息失败: {e}")


class AgentScheduler:
    """Agent调度器"""

    def __init__(self, communicator: AgentCommunicator):
        """初始化调度器

        Args:
            communicator: 通信管理器
        """
        self.communicator = communicator
        self.agents: Dict[str, BaseAgent] = {}
        self.tasks: Dict[UUID, AgentTask] = {}
        self.pending_tasks: List[AgentTask] = []
        self.running_tasks: List[AgentTask] = []
        self._lock = asyncio.Lock()
        self._running = True

        # 启动消息处理循环
        asyncio.create_task(self._message_loop())

    async def register_agent(self, agent: BaseAgent):
        """注册Agent

        Args:
            agent: Agent实例
        """
        async with self._lock:
            if agent.name not in self.agents:
                self.agents[agent.name] = agent
                await agent.start()
                logger.info(f"🎮 调度器已注册Agent: '{agent.name}'")

    async def submit_task(self, task: AgentTask) -> UUID:
        """提交任务

        Args:
            task: 任务对象

        Returns:
            任务ID
        """
        async with self._lock:
            self.tasks[task.task_id] = task
            self.pending_tasks.append(task)
            logger.info(f"📋 任务已提交: {task.task_name} (ID: {task.task_id})")

        # 尝试立即分配任务
        await self._schedule_tasks()
        return task.task_id

    async def _message_loop(self):
        """消息处理循环"""
        # 注册调度器自身到通信系统
        await self.communicator.register_agent("scheduler")

        while self._running:
            try:
                message = await self.communicator.receive_message(
                    "scheduler", timeout=1.0
                )
                if message:
                    await self._handle_message(message)
            except Exception as e:
                logger.error(f"❌ 调度器消息处理错误: {e}")

    async def _handle_message(self, message: Message):
        """处理消息

        Args:
            message: 消息对象
        """
        logger.debug(f"🎮 调度器处理消息: {message.message_type} from {message.sender}")

        # 处理不同类型的消息
        if message.message_type == "task_completion":
            # 任务完成消息
            await self._handle_task_completion(message)
        elif message.message_type == "agent_status":
            # Agent状态消息
            logger.debug(f"🎮 收到Agent状态消息: {message.content}")

    async def _handle_task_completion(self, message: Message):
        """处理任务完成消息

        Args:
            message: 任务完成消息
        """
        task_id = message.content.get("task_id")
        status = message.content.get("status")
        result = message.content.get("result")

        if not task_id:
            logger.error("❌ 任务完成消息缺少task_id")
            return

        try:
            task_id_uuid = UUID(task_id)
            await self.update_task_status(
                task_id_uuid,
                TaskStatus.COMPLETED if status == "completed" else TaskStatus.FAILED,
                result=result,
            )
        except Exception as e:
            logger.error(f"❌ 处理任务完成消息失败: {e}")

    async def _schedule_tasks(self):
        """调度任务

        1. 检查待处理任务的依赖关系
        2. 筛选出可执行的任务
        3. 按优先级排序
        4. 分配给空闲的Agent
        """
        async with self._lock:
            # 筛选出可执行的任务（依赖已完成）
            executable_tasks = []
            for task in self.pending_tasks:
                # 检查所有依赖是否已完成
                all_deps_completed = True
                for dep in task.dependencies:
                    dep_id = dep if isinstance(dep, UUID) else UUID(dep)
                    dep_task = self.tasks.get(dep_id)
                    # 如果依赖任务不存在或未完成，则当前任务不可执行
                    if dep_task is None:
                        logger.warning(
                            f"⚠️ 任务 {task.task_name} 的依赖 {dep_id} 不存在"
                        )
                        all_deps_completed = False
                        break
                    if dep_task.status != TaskStatus.COMPLETED:
                        all_deps_completed = False
                        break
                if all_deps_completed:
                    executable_tasks.append(task)

            # 按优先级排序
            executable_tasks.sort(
                key=lambda t: (
                    t.priority.value
                    if hasattr(t.priority, "value")
                    else int(t.priority)
                ),
                reverse=True,
            )

            # 获取空闲的Agent
            idle_agents = [
                agent
                for agent in self.agents.values()
                if agent.status == AgentStatus.IDLE
            ]

            # 分配任务
            for task in executable_tasks:
                if not idle_agents:
                    break

                # 选择一个空闲的Agent
                agent = idle_agents.pop(0)

                # 分配任务
                task.assigned_agent = agent.name
                task.status = TaskStatus.ASSIGNED

                # 从待处理队列中移除
                self.pending_tasks.remove(task)
                self.running_tasks.append(task)

                # 发送任务分配消息
                task_message = Message(
                    sender="scheduler",
                    receiver=agent.name,
                    message_type="task_assignment",
                    content={"task": task.to_dict()},
                )
                await self.communicator.send_message(task_message)

                logger.info(f"🎮 任务已分配: {task.task_name} -> {agent.name}")

    async def get_task_status(self, task_id: UUID) -> Optional[TaskStatus]:
        """获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            return task.status if task else None

    async def get_agent_status(self, agent_name: str) -> Optional[AgentStatus]:
        """获取Agent状态

        Args:
            agent_name: Agent名称

        Returns:
            Agent状态
        """
        async with self._lock:
            agent = self.agents.get(agent_name)
            return agent.status if agent else None

    async def cancel_task(self, task_id: UUID) -> bool:
        """取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否取消成功
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED]:
                # 待处理或已分配的任务
                task.status = TaskStatus.CANCELLED
                if task in self.pending_tasks:
                    self.pending_tasks.remove(task)
                elif task in self.running_tasks:
                    self.running_tasks.remove(task)
                logger.info(f"🎮 任务已取消: {task_id}")
                return True
            elif task.status == TaskStatus.RUNNING and task.assigned_agent:
                # 运行中的任务，发送取消消息
                cancel_message = Message(
                    sender="scheduler",
                    receiver=task.assigned_agent,
                    message_type="task_cancellation",
                    content={"task_id": str(task_id)},
                )
                await self.communicator.send_message(cancel_message)
                logger.info(f"🎮 发送任务取消消息: {task_id} -> {task.assigned_agent}")
                return True

            return False

    async def update_task_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        result: Optional[Any] = None,
        error_message: Optional[str] = None,
    ):
        """更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            result: 任务结果
            error_message: 错误信息
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return

            # 更新任务状态
            task.status = status
            if result:
                task.result = result
            if error_message:
                task.error_message = error_message

            # 处理任务完成
            if status == TaskStatus.COMPLETED or status == TaskStatus.FAILED:
                task.complete_time = asyncio.get_event_loop().time()
                if task in self.running_tasks:
                    self.running_tasks.remove(task)

                # 释放Agent
                if task.assigned_agent and task.assigned_agent in self.agents:
                    agent = self.agents[task.assigned_agent]
                    agent.status = AgentStatus.IDLE
                    agent.current_task = None

                # 执行回调函数
                if task.callback and status == TaskStatus.COMPLETED:
                    try:
                        await task.callback(task)
                    except Exception as e:
                        logger.error(f"❌ 任务回调执行错误: {e}")

                # 重新调度任务
                # 在锁外调用，避免死锁
                asyncio.create_task(self._schedule_tasks())

            logger.info(
                f"🎮 任务状态更新: {task_id} -> {status.value if hasattr(status, 'value') else status}"
            )
