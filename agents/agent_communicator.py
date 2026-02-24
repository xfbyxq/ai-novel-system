"""Agent间通信机制"""
import asyncio
import json
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

# Use the project-wide logger
from core.logging_config import logger


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
        self.timestamp = timestamp or asyncio.get_event_loop().time()
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
            logger.debug(f"📨 消息已发送: {message.sender} -> {message.receiver} ({message.message_type})")

    async def receive_message(self, agent_name: str, timeout: Optional[float] = None) -> Optional[Message]:
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
                self.message_queues[agent_name].get(),
                timeout=timeout
            )
            message.status = "processed"
            logger.debug(f"📥 消息已接收: {message.sender} -> {message.receiver} ({message.message_type})")
            return message
        except asyncio.TimeoutError:
            return None

    async def broadcast_message(self, sender: str, message_type: str, content: Dict[str, Any]) -> None:
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

    def get_message_history(self, agent_name: Optional[str] = None) -> List[Message]:
        """获取消息历史
        
        Args:
            agent_name: Agent名称（可选，None表示所有消息）
            
        Returns:
            消息历史列表
        """
        if agent_name:
            return [msg for msg in self.message_history 
                    if msg.sender == agent_name or msg.receiver == agent_name]
        return self.message_history

    def clear_message_history(self) -> None:
        """清除消息历史"""
        self.message_history.clear()
        logger.info("🧹 消息历史已清除")


# 全局通信管理器实例
agent_communicator = AgentCommunicator()
