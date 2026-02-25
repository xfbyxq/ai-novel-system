"""小说记忆模块服务 - 高效存储和管理小说相关信息"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MemoryCache:
    """内存缓存实现"""
    
    def __init__(self, max_size: int = 100, expiration_minutes: int = 30):
        self.max_size = max_size
        self.expiration_minutes = expiration_minutes
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存数据"""
        if key not in self.cache:
            return None
        
        item = self.cache[key]
        # 检查是否过期
        if datetime.now() > item['expires_at']:
            del self.cache[key]
            return None
        
        # 更新访问时间和访问次数
        item['last_accessed'] = datetime.now()
        item['access_count'] += 1
        
        return item['data']
    
    def set(self, key: str, data: Any) -> None:
        """设置缓存数据"""
        # 如果缓存已满，删除最不常用的项目
        if len(self.cache) >= self.max_size:
            self._evict_least_used()
        
        self.cache[key] = {
            'data': data,
            'created_at': datetime.now(),
            'last_accessed': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=self.expiration_minutes),
            'access_count': 1
        }
    
    def delete(self, key: str) -> None:
        """删除缓存数据"""
        if key in self.cache:
            del self.cache[key]
    
    def _evict_least_used(self) -> None:
        """删除最不常用的缓存项"""
        if not self.cache:
            return
        
        # 按访问次数和最后访问时间排序
        least_used = sorted(
            self.cache.items(),
            key=lambda x: (x[1]['access_count'], x[1]['last_accessed'])
        )[0]
        
        del self.cache[least_used[0]]
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()


class NovelMemoryService:
    """小说记忆服务"""
    
    def __init__(self):
        self.cache = MemoryCache()
        self.version_map: Dict[str, int] = {}  # 小说ID -> 版本号
    
    def get_novel_memory(self, novel_id: str) -> Optional[Dict[str, Any]]:
        """获取小说记忆"""
        cache_key = f"novel:{novel_id}"
        return self.cache.get(cache_key)
    
    def set_novel_memory(self, novel_id: str, novel_data: Dict[str, Any]) -> bool:
        """设置小说记忆，返回是否有内容变化"""
        cache_key = f"novel:{novel_id}"
        
        # 获取当前记忆
        current_memory = self.get_novel_memory(novel_id)
        has_changes = False
        
        # 检查内容是否有变化
        if current_memory:
            # 比较关键字段
            if novel_data.get('title') != current_memory['base'].get('title'):
                has_changes = True
            if novel_data.get('genre') != current_memory['base'].get('genre'):
                has_changes = True
            if novel_data.get('synopsis') != current_memory['base'].get('synopsis'):
                has_changes = True
            
            # 比较章节数量
            current_chapter_count = len(current_memory.get('chapters', []))
            new_chapter_count = len(novel_data.get('chapters', []))
            if current_chapter_count != new_chapter_count:
                has_changes = True
            
            # 比较角色数量
            current_character_count = len(current_memory['details'].get('characters', []))
            new_character_count = len(novel_data.get('characters', []))
            if current_character_count != new_character_count:
                has_changes = True
        else:
            # 新的记忆，视为有变化
            has_changes = True
        
        # 只有在有变化时才更新
        if has_changes:
            # 更新版本号
            current_version = self.version_map.get(novel_id, 0)
            new_version = current_version + 1
            self.version_map[novel_id] = new_version
            
            # 添加版本信息和时间戳
            novel_data['version'] = new_version
            novel_data['last_updated'] = datetime.now().isoformat()
            novel_data['last_change_detected'] = datetime.now().isoformat()
            
            # 分层存储数据
            memory_data = self._structure_novel_data(novel_data)
            
            self.cache.set(cache_key, memory_data)
            logger.info(f"Set novel memory for {novel_id}, version: {new_version}, changes detected: {has_changes}")
        
        return has_changes
    
    def update_novel_memory(self, novel_id: str, updated_data: Dict[str, Any]) -> bool:
        """更新小说记忆（增量更新），返回是否有内容变化"""
        current_memory = self.get_novel_memory(novel_id)
        
        if current_memory:
            # 合并数据
            updated_memory = self._merge_memory(current_memory, updated_data)
        else:
            updated_memory = updated_data
        
        # 调用set_novel_memory检测变化
        return self.set_novel_memory(novel_id, updated_memory)
    
    def invalidate_novel_memory(self, novel_id: str) -> None:
        """使小说记忆失效"""
        cache_key = f"novel:{novel_id}"
        self.cache.delete(cache_key)
        if novel_id in self.version_map:
            del self.version_map[novel_id]
        logger.info(f"Invalidated novel memory for {novel_id}")
    
    def get_novel_version(self, novel_id: str) -> int:
        """获取小说版本号"""
        return self.version_map.get(novel_id, 0)
    
    def _structure_novel_data(self, novel_data: Dict[str, Any]) -> Dict[str, Any]:
        """结构化小说数据"""
        return {
            'base': {
                'id': novel_data.get('id'),
                'title': novel_data.get('title'),
                'author': novel_data.get('author'),
                'genre': novel_data.get('genre'),
                'tags': novel_data.get('tags', []),
                'status': novel_data.get('status'),
                'length_type': novel_data.get('length_type'),
                'word_count': novel_data.get('word_count'),
                'chapter_count': novel_data.get('chapter_count'),
                'cover_url': novel_data.get('cover_url'),
                'synopsis': novel_data.get('synopsis'),
                'target_platform': novel_data.get('target_platform'),
                'metadata': novel_data.get('metadata', {}),
                'created_at': novel_data.get('created_at'),
                'updated_at': novel_data.get('updated_at'),
            },
            'details': {
                'world_setting': novel_data.get('world_setting'),
                'characters': novel_data.get('characters'),
                'plot_outline': novel_data.get('plot_outline'),
            },
            'chapters': novel_data.get('chapters', []),
            'analysis': novel_data.get('analysis', {}),
            'metadata': {
                'version': novel_data.get('version', 1),
                'last_updated': novel_data.get('last_updated'),
                'character_count': len(novel_data.get('characters', [])),
                'chapter_count': len(novel_data.get('chapters', [])),
                'chapter_range': novel_data.get('chapter_range', {'start': 1, 'end': 10}),
            }
        }
    
    def _merge_memory(self, current: Dict[str, Any], updated: Dict[str, Any]) -> Dict[str, Any]:
        """合并内存数据"""
        # 合并基本信息
        if 'base' in updated:
            current['base'].update(updated['base'])
        
        # 合并详细信息
        if 'details' in updated:
            for key, value in updated['details'].items():
                if value is not None:
                    current['details'][key] = value
        
        # 合并章节
        if 'chapters' in updated:
            current['chapters'] = updated['chapters']
        
        # 合并分析结果
        if 'analysis' in updated:
            current['analysis'].update(updated['analysis'])
        
        return current


# 全局记忆服务实例
_novel_memory_service: Optional[NovelMemoryService] = None

def get_novel_memory_service() -> NovelMemoryService:
    """获取小说记忆服务实例"""
    global _novel_memory_service
    if _novel_memory_service is None:
        _novel_memory_service = NovelMemoryService()
    return _novel_memory_service