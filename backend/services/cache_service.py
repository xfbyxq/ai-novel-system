"""
Redis缓存服务

提供通用的缓存功能,用于减少数据库查询压力,提高系统性能。
支持分布式环境检测,自动使用正确的Redis地址。
"""

import json
import redis
from typing import Optional, Any
from backend.config import settings


class CacheService:
    """
    Redis缓存服务
    
    提供通用的缓存功能:
    - 通用键值操作
    - 生成结果缓存
    - Agent输出缓存
    - 热点数据缓存
    """
    
    _instance = None
    _client = None
    
    def __new__(cls):
        """单例模式：确保全局只有一个 Redis 客户端实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化 Redis 客户端（仅在首次创建时）"""
        if not hasattr(self, '_initialized'):
            self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self._initialized = True

    @property
    def client(self):
        """获取 Redis 客户端"""
        return self._client
    
    def close(self):
        """关闭 Redis 连接（在应用关闭时调用）"""
        if self._client:
            self._client.close()
            self._initialized = False
    
    async def get(self, key: str) -> Optional[str]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值,如果不存在返回None
        """
        try:
            value = self.client.get(key)
            return value.decode('utf-8') if value else None
        except Exception as e:
            # 缓存读取失败不影响主流程
            return None
            
    async def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间(秒),默认1小时
            
        Returns:
            成功返回True,失败返回False
        """
        try:
            self.client.setex(key, ttl, value)
            return True
        except Exception as e:
            # 缓存写入失败不影响主流程
            return False
            
    async def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            成功返回True,失败返回False
        """
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            return False
            
    async def exists(self, key: str) -> bool:
        """
        检查缓存是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            存在返回True,否则返回False
        """
        try:
            return self.client.exists(key) > 0
        except Exception:
            return False
            
    # ========== 生成结果缓存 ========== #
    
    async def get_generation_result(self, task_id: str) -> Optional[dict]:
        """
        获取生成结果缓存
        
        Args:
            task_id: 任务ID
            
        Returns:
            生成结果字典,如果不存在返回None
        """
        data = await self.get(f"generation:{task_id}")
        return json.loads(data) if data else None
        
    async def set_generation_result(self, task_id: str, result: dict, ttl: int = 300) -> bool:
        """
        设置生成结果缓存(默认5分钟)
        
        Args:
            task_id: 任务ID
            result: 生成结果字典
            ttl: 过期时间(秒),默认5分钟
            
        Returns:
            成功返回True,失败返回False
        """
        return await self.set(f"generation:{task_id}", json.dumps(result), ttl)
        
    async def delete_generation_result(self, task_id: str) -> bool:
        """
        删除生成结果缓存
        
        Args:
            task_id: 任务ID
            
        Returns:
            成功返回True,失败返回False
        """
        return await self.delete(f"generation:{task_id}")
        
    # ========== Agent输出缓存 ========== #
    
    async def get_agent_output(self, agent_name: str, novel_id: int, version: int = 1) -> Optional[dict]:
        """
        获取Agent输出缓存
        
        Args:
            agent_name: Agent名称
            novel_id: 小说ID
            version: 版本号
            
        Returns:
            Agent输出字典,如果不存在返回None
        """
        key = f"agent:{agent_name}:novel:{novel_id}:v{version}"
        data = await self.get(key)
        return json.loads(data) if data else None
        
    async def set_agent_output(self, agent_name: str, novel_id: int, version: int, output: dict, ttl: int = 3600) -> bool:
        """
        设置Agent输出缓存(默认1小时)
        
        Args:
            agent_name: Agent名称
            novel_id: 小说ID
            version: 版本号
            output: Agent输出字典
            ttl: 过期时间(秒),默认1小时
            
        Returns:
            成功返回True,失败返回False
        """
        key = f"agent:{agent_name}:novel:{novel_id}:v{version}"
        return await self.set(key, json.dumps(output), ttl)
        
    async def delete_agent_output(self, agent_name: str, novel_id: int, version: int = 1) -> bool:
        """
        删除Agent输出缓存
        
        Args:
            agent_name: Agent名称
            novel_id: 小说ID
            version: 版本号
            
        Returns:
            成功返回True,失败返回False
        """
        key = f"agent:{agent_name}:novel:{novel_id}:v{version}"
        return await self.delete(key)
        
    # ========== 章节内容缓存 ========== #
    
    async def get_chapter_content(self, novel_id: int, chapter_number: int) -> Optional[str]:
        """
        获取章节内容缓存
        
        Args:
            novel_id: 小说ID
            chapter_number: 章节编号
            
        Returns:
            章节内容,如果不存在返回None
        """
        key = f"chapter:{novel_id}:{chapter_number}:content"
        return await self.get(key)
        
    async def set_chapter_content(self, novel_id: int, chapter_number: int, content: str, ttl: int = 7200) -> bool:
        """
        设置章节内容缓存(默认2小时)
        
        Args:
            novel_id: 小说ID
            chapter_number: 章节编号
            content: 章节内容
            ttl: 过期时间(秒),默认2小时
            
        Returns:
            成功返回True,失败返回False
        """
        key = f"chapter:{novel_id}:{chapter_number}:content"
        return await self.set(key, content, ttl)
        
    async def delete_chapter_content(self, novel_id: int, chapter_number: int) -> bool:
        """
        删除章节内容缓存
        
        Args:
            novel_id: 小说ID
            chapter_number: 章节编号
            
        Returns:
            成功返回True,失败返回False
        """
        key = f"chapter:{novel_id}:{chapter_number}:content"
        return await self.delete(key)
        
    # ========== 概览数据缓存 ========== #
    
    async def get_dashboard_stats(self, user_id: int) -> Optional[dict]:
        """
        获取仪表盘统计数据缓存(默认5分钟)
        
        Args:
            user_id: 用户ID
            
        Returns:
            统计数据字典,如果不存在返回None
        """
        key = f"dashboard:{user_id}:stats"
        data = await self.get(key)
        return json.loads(data) if data else None
        
    async def set_dashboard_stats(self, user_id: int, stats: dict, ttl: int = 300) -> bool:
        """
        设置仪表盘统计数据缓存(默认5分钟)
        
        Args:
            user_id: 用户ID
            stats: 统计数据字典
            ttl: 过期时间(秒),默认5分钟
            
        Returns:
            成功返回True,失败返回False
        """
        key = f"dashboard:{user_id}:stats"
        return await self.set(key, json.dumps(stats), ttl)
        
    async def delete_dashboard_stats(self, user_id: int) -> bool:
        """
        删除仪表盘统计数据缓存
        
        Args:
            user_id: 用户ID
            
        Returns:
            成功返回True,失败返回False
        """
        key = f"dashboard:{user_id}:stats"
        return await self.delete(key)


# 全局实例
cache_service = CacheService()
