"""Agent间通信机制"""

import asyncio
import json
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

# Use the project-wide logger
from core.logging_config import logger


class MessageType(str, Enum):
    """Agent间通信的消息类型"""

    # 基础通信
    TASK_ASSIGNMENT = "task_assignment"
    TASK_COMPLETION = "task_completion"
    TASK_CANCELLATION = "task_cancellation"
    STATUS_REQUEST = "status_request"
    STATUS_RESPONSE = "status_response"

    # 请求-应答
    REQUEST = "request"
    RESPONSE = "response"

    # 审查反馈
    REVIEW_FEEDBACK = "review_feedback"
    REVISION_REQUEST = "revision_request"

    # 投票共识
    VOTE_CALL = "vote_call"
    VOTE_CAST = "vote_cast"
    VOTE_RESULT = "vote_result"

    # 质量检查
    QUALITY_CHECK = "quality_check"


class Message:
    """Agent间通信的消息类"""

    def __init__(
        self,
        sender: str,
        receiver: str,
        message_type: str,
        content: Dict[str, Any],
        message_id: Optional[UUID] = None,
        timestamp: Optional[float] = None,
        priority: int = 0,
    ):
        """初始化消息

        Args:
            sender: 发送者Agent名称
            receiver: 接收者Agent名称
            message_type: 消息类型
            content: 消息内容
            message_id: 消息ID（自动生成）
            timestamp: 时间戳（自动生成）
            priority: 优先级（0-10，默认为0）
        """
        self.message_id = message_id or uuid4()
        self.sender = sender
        self.receiver = receiver
        self.message_type = message_type
        self.content = content
        self.timestamp = timestamp or time.time()
        self.priority = priority
        self.status = "pending"  # pending, delivered, processed

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": str(self.message_id),
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息"""
        message = cls(
            sender=data["sender"],
            receiver=data["receiver"],
            message_type=data["message_type"],
            content=data["content"],
            message_id=UUID(data["message_id"]),
            timestamp=data["timestamp"],
            priority=data["priority"],
        )
        message.status = data["status"]
        return message


class AgentCommunicator:
    """Agent间通信管理器"""

    def __init__(self):
        """初始化通信管理器"""
        self.message_queues: Dict[str, asyncio.Queue] = {}  # Agent名称 -> 消息队列
        self.message_history: List[Message] = []
        self._lock = asyncio.Lock()
        # 请求-响应配对：request_message_id -> Future
        self.pending_requests: Dict[UUID, asyncio.Future] = {}

    async def register_agent(self, agent_name: str) -> None:
        """注册Agent

        Args:
            agent_name: Agent名称
        """
        async with self._lock:
            if agent_name not in self.message_queues:
                self.message_queues[agent_name] = asyncio.Queue()
                logger.info(f"🤖 Agent '{agent_name}' 已注册到通信系统")

    async def send_message(self, message: Message) -> None:
        """发送消息

        Args:
            message: 消息对象
        """
        async with self._lock:
            # 检查接收者是否已注册
            if message.receiver not in self.message_queues:
                logger.warning(f"⚠️  接收者 '{message.receiver}' 未注册，消息将被丢弃")
                return

            # 将消息加入接收者的队列
            await self.message_queues[message.receiver].put(message)
            message.status = "delivered"

            # 记录消息历史
            self.message_history.append(message)
            logger.debug(
                f"📨 消息已发送: {message.sender} -> {message.receiver} ({message.message_type})"
            )

    async def receive_message(
        self, agent_name: str, timeout: Optional[float] = None
    ) -> Optional[Message]:
        """接收消息

        Args:
            agent_name: Agent名称
            timeout: 超时时间

        Returns:
            消息对象，或None（如果超时）
        """
        async with self._lock:
            if agent_name not in self.message_queues:
                logger.warning(f"⚠️  Agent '{agent_name}' 未注册，无法接收消息")
                return None

        try:
            message = await asyncio.wait_for(
                self.message_queues[agent_name].get(), timeout=timeout
            )
            message.status = "processed"
            logger.debug(
                f"📥 消息已接收: {message.sender} -> {message.receiver} ({message.message_type})"
            )
            return message
        except asyncio.TimeoutError:
            return None

    async def broadcast_message(
        self, sender: str, message_type: str, content: Dict[str, Any]
    ) -> None:
        """广播消息给所有注册的Agent

        Args:
            sender: 发送者Agent名称
            message_type: 消息类型
            content: 消息内容
        """
        async with self._lock:
            receivers = list(self.message_queues.keys())

        for receiver in receivers:
            if receiver != sender:
                message = Message(
                    sender=sender,
                    receiver=receiver,
                    message_type=message_type,
                    content=content,
                )
                await self.send_message(message)

    async def send_and_wait_reply(
        self, message: Message, timeout: float = 60.0
    ) -> Optional[Message]:
        """发送请求消息并等待对方回复

        通过 Future 实现请求-响应配对。发送方阻塞等待，直到接收方调用
        send_reply() 回复对应的 message_id。

        Args:
            message: 请求消息（message_type 应为 REQUEST 等需要回复的类型）
            timeout: 等待超时（秒）

        Returns:
            响应消息，或 None（如果超时）
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self.pending_requests[message.message_id] = future

        await self.send_message(message)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(
                f"⏰ 请求超时: {message.sender} -> {message.receiver} "
                f"({message.message_type}), timeout={timeout}s"
            )
            return None
        finally:
            self.pending_requests.pop(message.message_id, None)

    async def send_reply(
        self, original_message_id: UUID, response_message: Message
    ) -> None:
        """回复一个请求消息

        将响应消息投递到发送方队列，并唤醒 send_and_wait_reply 中的等待方。

        Args:
            original_message_id: 原始请求消息的 ID
            response_message: 响应消息
        """
        # 记录到历史
        await self.send_message(response_message)

        # 唤醒等待方
        future = self.pending_requests.get(original_message_id)
        if future and not future.done():
            future.set_result(response_message)
            logger.debug(
                f"↩️  回复已送达: {response_message.sender} -> {response_message.receiver} "
                f"(reply to {original_message_id})"
            )

    def get_message_history(self, agent_name: Optional[str] = None) -> List[Message]:
        """获取消息历史

        Args:
            agent_name: Agent名称（可选，None表示所有消息）

        Returns:
            消息历史列表
        """
        if agent_name:
            return [
                msg
                for msg in self.message_history
                if msg.sender == agent_name or msg.receiver == agent_name
            ]
        return self.message_history

    def clear_message_history(self) -> None:
        """清除消息历史"""
        self.message_history.clear()
        logger.info("🧹 消息历史已清除")


# 全局通信管理器实例
agent_communicator = AgentCommunicator()
