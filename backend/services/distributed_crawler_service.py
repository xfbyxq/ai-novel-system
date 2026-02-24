#!/usr/bin/env python3
"""分布式爬虫服务 - 负责协调多个爬虫节点"""
import asyncio
import logging
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from core.models.crawler_task import CrawlerTask, CrawlTaskStatus
from backend.services.crawler_service import CrawlerService

logger = logging.getLogger(__name__)


@dataclass
class CrawlerNode:
    """爬虫节点"""
    node_id: str
    status: str  # online, busy, offline
    last_heartbeat: datetime
    performance: Dict[str, float]  # 性能指标
    capabilities: List[str]  # 支持的爬取类型


class DistributedCrawlerService:
    """分布式爬虫服务"""
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.nodes: Dict[str, CrawlerNode] = {}
        self.task_queue = "crawler:task:queue"
        self.node_registry = "crawler:nodes"
        self.logger = logger.getChild("distributed_crawler")
    
    async def initialize(self):
        """初始化分布式爬虫服务"""
        try:
            # 测试Redis连接
            await asyncio.to_thread(self.redis_client.ping)
            self.logger.info("Redis连接成功")
            
            # 清理旧的任务队列
            await asyncio.to_thread(self.redis_client.delete, self.task_queue)
            self.logger.info("分布式爬虫服务初始化成功")
        except Exception as e:
            self.logger.error(f"分布式爬虫服务初始化失败: {e}")
            raise
    
    async def register_node(self, node_id: str, capabilities: List[str] = None):
        """注册爬虫节点
        
        Args:
            node_id: 节点ID
            capabilities: 节点支持的爬取类型
        """
        try:
            capabilities = capabilities or ["qidian", "fanqie", "zongheng", "douyin"]
            
            node = CrawlerNode(
                node_id=node_id,
                status="online",
                last_heartbeat=datetime.now(),
                performance={"success_rate": 1.0, "avg_time": 0.0},
                capabilities=capabilities
            )
            
            self.nodes[node_id] = node
            
            # 保存到Redis
            node_data = {
                "node_id": node_id,
                "status": "online",
                "last_heartbeat": node.last_heartbeat.isoformat(),
                "performance": node.performance,
                "capabilities": capabilities
            }
            
            await asyncio.to_thread(
                self.redis_client.hset,
                self.node_registry,
                node_id,
                json.dumps(node_data)
            )
            
            self.logger.info(f"节点注册成功: {node_id}")
        except Exception as e:
            self.logger.error(f"节点注册失败: {e}")
    
    async def heartbeat(self, node_id: str):
        """节点心跳
        
        Args:
            node_id: 节点ID
        """
        try:
            if node_id in self.nodes:
                self.nodes[node_id].last_heartbeat = datetime.now()
                self.nodes[node_id].status = "online"
            
            # 更新Redis中的心跳时间
            node_data_str = await asyncio.to_thread(
                self.redis_client.hget,
                self.node_registry,
                node_id
            )
            
            if node_data_str:
                node_data = json.loads(node_data_str)
                node_data["last_heartbeat"] = datetime.now().isoformat()
                node_data["status"] = "online"
                
                await asyncio.to_thread(
                    self.redis_client.hset,
                    self.node_registry,
                    node_id,
                    json.dumps(node_data)
                )
        except Exception as e:
            self.logger.error(f"心跳更新失败: {e}")
    
    async def get_available_nodes(self, crawl_type: str = None) -> List[str]:
        """获取可用节点
        
        Args:
            crawl_type: 爬取类型
            
        Returns:
            可用节点ID列表
        """
        try:
            # 从Redis获取所有节点
            nodes_data = await asyncio.to_thread(
                self.redis_client.hgetall,
                self.node_registry
            )
            
            available_nodes = []
            now = datetime.now()
            
            for node_id, data_str in nodes_data.items():
                try:
                    node_data = json.loads(data_str)
                    last_heartbeat = datetime.fromisoformat(node_data["last_heartbeat"])
                    
                    # 检查节点是否在线（心跳时间不超过60秒）
                    if (now - last_heartbeat).total_seconds() < 60:
                        # 检查节点状态
                        if node_data["status"] == "online":
                            # 检查是否支持指定的爬取类型
                            if not crawl_type or crawl_type in node_data.get("capabilities", []):
                                available_nodes.append(node_id)
                except Exception as e:
                    self.logger.error(f"解析节点数据失败: {e}")
            
            return available_nodes
        except Exception as e:
            self.logger.error(f"获取可用节点失败: {e}")
            return []
    
    async def submit_task(self, task: CrawlerTask):
        """提交爬虫任务
        
        Args:
            task: 爬虫任务
        """
        try:
            task_data = {
                "task_id": str(task.id),
                "crawl_type": task.crawl_type,
                "config": task.config,
                "created_at": task.created_at.isoformat() if task.created_at else datetime.now().isoformat()
            }
            
            # 计算任务哈希值，用于去重
            task_hash = hashlib.md5(json.dumps(task_data, sort_keys=True).encode()).hexdigest()
            task_data["task_hash"] = task_hash
            
            # 检查任务是否已存在
            if not await asyncio.to_thread(
                self.redis_client.exists,
                f"task:{task_hash}"
            ):
                # 提交到任务队列
                await asyncio.to_thread(
                    self.redis_client.lpush,
                    self.task_queue,
                    json.dumps(task_data)
                )
                
                # 标记任务为已提交
                await asyncio.to_thread(
                    self.redis_client.set,
                    f"task:{task_hash}",
                    "submitted",
                    ex=3600  # 1小时过期
                )
                
                self.logger.info(f"任务提交成功: {task.id}")
            else:
                self.logger.info(f"任务已存在，跳过提交: {task.id}")
        except Exception as e:
            self.logger.error(f"任务提交失败: {e}")
    
    async def get_task(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取一个任务
        
        Args:
            node_id: 节点ID
            
        Returns:
            任务数据
        """
        try:
            # 从队列中获取任务
            task_data_str = await asyncio.to_thread(
                self.redis_client.rpop,
                self.task_queue
            )
            
            if task_data_str:
                task_data = json.loads(task_data_str)
                
                # 标记任务为正在处理
                await asyncio.to_thread(
                    self.redis_client.set,
                    f"task:{task_data['task_hash']}",
                    "processing",
                    ex=3600
                )
                
                # 更新节点状态为忙碌
                node_data_str = await asyncio.to_thread(
                    self.redis_client.hget,
                    self.node_registry,
                    node_id
                )
                
                if node_data_str:
                    node_data = json.loads(node_data_str)
                    node_data["status"] = "busy"
                    
                    await asyncio.to_thread(
                        self.redis_client.hset,
                        self.node_registry,
                        node_id,
                        json.dumps(node_data)
                    )
                
                self.logger.info(f"节点 {node_id} 获取任务成功: {task_data['task_id']}")
                return task_data
            
            return None
        except Exception as e:
            self.logger.error(f"获取任务失败: {e}")
            return None
    
    async def complete_task(self, node_id: str, task_id: str, success: bool, result: Dict[str, Any] = None):
        """完成任务
        
        Args:
            node_id: 节点ID
            task_id: 任务ID
            success: 是否成功
            result: 任务结果
        """
        try:
            # 更新节点状态为在线
            node_data_str = await asyncio.to_thread(
                self.redis_client.hget,
                self.node_registry,
                node_id
            )
            
            if node_data_str:
                node_data = json.loads(node_data_str)
                node_data["status"] = "online"
                
                # 更新节点性能指标
                if "performance" not in node_data:
                    node_data["performance"] = {"success_rate": 1.0, "avg_time": 0.0}
                
                # 简单的性能指标更新
                if success:
                    node_data["performance"]["success_rate"] = (
                        node_data["performance"]["success_rate"] * 0.9 + 1.0 * 0.1
                    )
                else:
                    node_data["performance"]["success_rate"] = (
                        node_data["performance"]["success_rate"] * 0.9 + 0.0 * 0.1
                    )
                
                await asyncio.to_thread(
                    self.redis_client.hset,
                    self.node_registry,
                    node_id,
                    json.dumps(node_data)
                )
            
            self.logger.info(f"任务完成: {task_id}, 成功: {success}")
        except Exception as e:
            self.logger.error(f"任务完成处理失败: {e}")
    
    async def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态
        """
        try:
            # 遍历所有任务，查找指定的任务ID
            # 注意：这只是一个简单的实现，实际应用中可能需要更高效的方式
            keys = await asyncio.to_thread(
                self.redis_client.keys,
                "task:*"
            )
            
            for key in keys:
                task_hash = key.decode().split(":")[1]
                status = await asyncio.to_thread(self.redis_client.get, key)
                
                if status:
                    # 这里需要根据实际情况关联任务ID和哈希值
                    # 简化实现，直接返回状态
                    return status.decode()
            
            return None
        except Exception as e:
            self.logger.error(f"获取任务状态失败: {e}")
            return None
    
    async def cleanup_offline_nodes(self):
        """清理离线节点"""
        try:
            now = datetime.now()
            offline_nodes = []
            
            # 检查内存中的节点
            for node_id, node in self.nodes.items():
                if (now - node.last_heartbeat).total_seconds() > 60:
                    offline_nodes.append(node_id)
            
            # 检查Redis中的节点
            nodes_data = await asyncio.to_thread(
                self.redis_client.hgetall,
                self.node_registry
            )
            
            for node_id, data_str in nodes_data.items():
                try:
                    node_data = json.loads(data_str)
                    last_heartbeat = datetime.fromisoformat(node_data["last_heartbeat"])
                    
                    if (now - last_heartbeat).total_seconds() > 60:
                        # 标记为离线
                        node_data["status"] = "offline"
                        await asyncio.to_thread(
                            self.redis_client.hset,
                            self.node_registry,
                            node_id,
                            json.dumps(node_data)
                        )
                        
                        self.logger.info(f"节点标记为离线: {node_id}")
                except Exception as e:
                    self.logger.error(f"清理离线节点失败: {e}")
            
            # 从内存中移除离线节点
            for node_id in offline_nodes:
                if node_id in self.nodes:
                    del self.nodes[node_id]
        except Exception as e:
            self.logger.error(f"清理离线节点失败: {e}")


# 全局分布式爬虫服务实例
distributed_crawler_service = DistributedCrawlerService()
