#!/usr/bin/env python3
"""数据去重服务 - 负责处理爬虫数据的去重和增量爬取"""
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.config import settings
from core.models.crawl_result import CrawlResult

logger = logging.getLogger(__name__)


class DataDeduplicationService:
    """数据去重服务"""
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.deduplication_prefix = "crawler:deduplication"
        self.logger = logger.getChild("data_deduplication")
    
    async def initialize(self):
        """初始化数据去重服务"""
        try:
            # 测试Redis连接
            await self.redis_client.ping()
            self.logger.info("Redis连接成功")
            self.logger.info("数据去重服务初始化成功")
        except Exception as e:
            self.logger.error(f"数据去重服务初始化失败: {e}")
            raise
    
    def calculate_item_hash(self, item: Dict[str, Any]) -> str:
        """计算数据项的哈希值
        
        Args:
            item: 数据项
            
        Returns:
            哈希值
        """
        try:
            # 对数据项进行排序，确保相同内容生成相同哈希
            sorted_item = json.dumps(item, sort_keys=True, ensure_ascii=False)
            item_hash = hashlib.md5(sorted_item.encode()).hexdigest()
            return item_hash
        except Exception as e:
            self.logger.error(f"计算数据项哈希失败: {e}")
            raise
    
    async def is_duplicate(self, platform: str, data_type: str, item: Dict[str, Any]) -> bool:
        """检查数据项是否重复
        
        Args:
            platform: 平台
            data_type: 数据类型
            item: 数据项
            
        Returns:
            是否重复
        """
        try:
            item_hash = self.calculate_item_hash(item)
            key = f"{self.deduplication_prefix}:{platform}:{data_type}:{item_hash}"
            
            # 检查Redis中是否存在
            exists = await self.redis_client.exists(key)
            return bool(exists)
        except Exception as e:
            self.logger.error(f"检查数据重复失败: {e}")
            # 出错时默认返回False，避免误判
            return False
    
    async def mark_processed(self, platform: str, data_type: str, item: Dict[str, Any], expiration: int = 86400):
        """标记数据项为已处理
        
        Args:
            platform: 平台
            data_type: 数据类型
            item: 数据项
            expiration: 过期时间（秒），默认24小时
        """
        try:
            item_hash = self.calculate_item_hash(item)
            key = f"{self.deduplication_prefix}:{platform}:{data_type}:{item_hash}"
            
            # 存储到Redis，并设置过期时间
            await self.redis_client.setex(key, expiration, str(datetime.now()))
            self.logger.debug(f"数据项标记为已处理: {key}")
        except Exception as e:
            self.logger.error(f"标记数据项失败: {e}")
    
    async def batch_check_duplicates(self, platform: str, data_type: str, items: List[Dict[str, Any]]) -> List[bool]:
        """批量检查数据项是否重复
        
        Args:
            platform: 平台
            data_type: 数据类型
            items: 数据项列表
            
        Returns:
            重复标记列表
        """
        try:
            results = []
            for item in items:
                is_dup = await self.is_duplicate(platform, data_type, item)
                results.append(is_dup)
            return results
        except Exception as e:
            self.logger.error(f"批量检查数据重复失败: {e}")
            # 出错时默认返回全False
            return [False] * len(items)
    
    async def batch_mark_processed(self, platform: str, data_type: str, items: List[Dict[str, Any]], expiration: int = 86400):
        """批量标记数据项为已处理
        
        Args:
            platform: 平台
            data_type: 数据类型
            items: 数据项列表
            expiration: 过期时间（秒），默认24小时
        """
        try:
            pipeline = self.redis_client.pipeline()
            
            for item in items:
                item_hash = self.calculate_item_hash(item)
                key = f"{self.deduplication_prefix}:{platform}:{data_type}:{item_hash}"
                pipeline.setex(key, expiration, str(datetime.now()))
            
            await pipeline.execute()
            self.logger.debug(f"批量标记 {len(items)} 个数据项为已处理")
        except Exception as e:
            self.logger.error(f"批量标记数据项失败: {e}")
    
    async def get_last_crawl_time(self, platform: str, data_type: str) -> Optional[datetime]:
        """获取上次爬取时间
        
        Args:
            platform: 平台
            data_type: 数据类型
            
        Returns:
            上次爬取时间
        """
        try:
            key = f"{self.deduplication_prefix}:{platform}:{data_type}:last_crawl"
            last_crawl_str = await self.redis_client.get(key)
            
            if last_crawl_str:
                return datetime.fromisoformat(last_crawl_str)
            return None
        except Exception as e:
            self.logger.error(f"获取上次爬取时间失败: {e}")
            return None
    
    async def update_last_crawl_time(self, platform: str, data_type: str):
        """更新上次爬取时间
        
        Args:
            platform: 平台
            data_type: 数据类型
        """
        try:
            key = f"{self.deduplication_prefix}:{platform}:{data_type}:last_crawl"
            await self.redis_client.set(key, datetime.now().isoformat())
            self.logger.debug(f"更新 {platform}:{data_type} 上次爬取时间")
        except Exception as e:
            self.logger.error(f"更新上次爬取时间失败: {e}")
    
    async def cleanup_old_records(self, days: int = 7):
        """清理旧记录
        
        Args:
            days: 保留天数
        """
        try:
            # 注意：Redis不支持直接按模式删除过期键
            # 这里使用SCAN命令遍历所有键，然后检查过期时间
            # 实际应用中可能需要优化
            cursor = 0
            keys_to_delete = []
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match=f"{self.deduplication_prefix}:*",
                    count=1000
                )
                
                for key in keys:
                    # 检查键是否为数据项键（排除last_crawl键）
                    if "last_crawl" not in key.decode():
                        ttl = await self.redis_client.ttl(key)
                        # TTL为-1表示永不过期，-2表示不存在
                        if ttl == -1:
                            # 对于永不过期的键，手动检查创建时间
                            create_time_str = await self.redis_client.get(key)
                            if create_time_str:
                                try:
                                    create_time = datetime.fromisoformat(create_time_str)
                                    if (datetime.now() - create_time).days > days:
                                        keys_to_delete.append(key)
                                except:
                                    pass
                
                if cursor == 0:
                    break
            
            # 批量删除
            if keys_to_delete:
                await self.redis_client.delete(*keys_to_delete)
                self.logger.info(f"清理了 {len(keys_to_delete)} 条旧记录")
        except Exception as e:
            self.logger.error(f"清理旧记录失败: {e}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """获取去重统计信息
        
        Returns:
            统计信息
        """
        try:
            cursor = 0
            total_records = 0
            platform_stats = {}
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match=f"{self.deduplication_prefix}:*",
                    count=1000
                )
                
                for key in keys:
                    key_str = key.decode()
                    # 跳过last_crawl键
                    if "last_crawl" in key_str:
                        continue
                    
                    total_records += 1
                    
                    # 解析平台和数据类型
                    parts = key_str.split(":")
                    if len(parts) >= 4:
                        platform = parts[2]
                        data_type = parts[3]
                        
                        if platform not in platform_stats:
                            platform_stats[platform] = {}
                        if data_type not in platform_stats[platform]:
                            platform_stats[platform][data_type] = 0
                        platform_stats[platform][data_type] += 1
                
                if cursor == 0:
                    break
            
            return {
                "total_records": total_records,
                "platform_stats": platform_stats
            }
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"total_records": 0, "platform_stats": {}}


# 全局数据去重服务实例
data_deduplication_service = DataDeduplicationService()
