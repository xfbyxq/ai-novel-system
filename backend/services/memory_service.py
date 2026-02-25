"""小说记忆模块服务 - 高效存储和管理小说相关信息"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any, List
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
    
    def _compute_content_hash(self, data: Any) -> str:
        """计算内容哈希用于变化检测"""
        if data is None:
            return ""
        try:
            content = json.dumps(data, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(content.encode()).hexdigest()
        except (TypeError, ValueError):
            # 如果数据无法序列化，返回空字符串
            return ""
    
    def _detect_changes(self, novel_data: Dict, current_memory: Dict) -> bool:
        """深度变化检测 - 检测所有关键字段的变化"""
        # 基础字段比较
        basic_fields = ['title', 'genre', 'synopsis']
        for field in basic_fields:
            if novel_data.get(field) != current_memory['base'].get(field):
                return True
        
        # 复杂字段哈希比较
        current_details = current_memory.get('details') or {}
        
        # 世界观变化检测
        new_world_hash = self._compute_content_hash(novel_data.get('world_setting'))
        old_world_hash = self._compute_content_hash(current_details.get('world_setting'))
        if new_world_hash != old_world_hash:
            return True
        
        # 情节大纲变化检测
        new_outline_hash = self._compute_content_hash(novel_data.get('plot_outline'))
        old_outline_hash = self._compute_content_hash(current_details.get('plot_outline'))
        if new_outline_hash != old_outline_hash:
            return True
        
        # 角色变化检测（数量和内容）
        new_chars = novel_data.get('characters') or []
        old_chars = current_details.get('characters') or []
        if len(new_chars) != len(old_chars):
            return True
        new_chars_hash = self._compute_content_hash(new_chars)
        old_chars_hash = self._compute_content_hash(old_chars)
        if new_chars_hash != old_chars_hash:
            return True
        
        # 章节变化检测
        new_chapters = novel_data.get('chapters') or []
        old_chapters = current_memory.get('chapters') or []
        if len(new_chapters) != len(old_chapters):
            return True
        
        return False
    
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
        
        # 检查内容是否有变化（使用深度变化检测）
        if current_memory:
            has_changes = self._detect_changes(novel_data, current_memory)
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
                'characters': novel_data.get('characters') or [],  # 确保不为 None
                'plot_outline': novel_data.get('plot_outline'),
            },
            'chapters': novel_data.get('chapters', []),
            'chapter_summaries': novel_data.get('chapter_summaries', {}),  # 结构化章节摘要
            'character_states': novel_data.get('character_states', {}),    # 角色状态追踪
            'analysis': novel_data.get('analysis', {}),
            'metadata': {
                'version': novel_data.get('version', 1),
                'last_updated': novel_data.get('last_updated'),
                'content_hashes': {  # 内容哈希用于增量检测
                    'world_setting': self._compute_content_hash(novel_data.get('world_setting')),
                    'characters': self._compute_content_hash(novel_data.get('characters')),
                    'plot_outline': self._compute_content_hash(novel_data.get('plot_outline')),
                },
                'character_count': len(novel_data.get('characters') or []),
                'chapter_count': len(novel_data.get('chapters') or []),
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
        
        # 合并章节摘要
        if 'chapter_summaries' in updated:
            if 'chapter_summaries' not in current:
                current['chapter_summaries'] = {}
            current['chapter_summaries'].update(updated['chapter_summaries'])
        
        # 合并角色状态
        if 'character_states' in updated:
            if 'character_states' not in current:
                current['character_states'] = {}
            current['character_states'].update(updated['character_states'])
        
        # 合并分析结果
        if 'analysis' in updated:
            current['analysis'].update(updated['analysis'])
        
        return current
    
    # ==================== 章节摘要管理方法 ====================
    
    def update_chapter_summary(self, novel_id: str, chapter_number: int, summary: Dict[str, Any]) -> None:
        """更新单个章节的结构化摘要
        
        Args:
            novel_id: 小说ID
            chapter_number: 章节号
            summary: 章节摘要，包含 key_events, character_changes, plot_progress, foreshadowing, ending_state
        """
        cache_key = f"novel:{novel_id}"
        memory = self.get_novel_memory(novel_id)
        if memory:
            if 'chapter_summaries' not in memory:
                memory['chapter_summaries'] = {}
            memory['chapter_summaries'][str(chapter_number)] = summary
            # 直接更新缓存，不触发版本号递增
            self.cache.set(cache_key, memory)
            logger.info(f"Updated chapter {chapter_number} summary for novel {novel_id}")
        else:
            logger.warning(f"Cannot update chapter summary: novel {novel_id} not in memory")
    
    def get_chapter_summaries(self, novel_id: str, max_chapters: int = 20) -> Dict[str, Dict]:
        """获取章节摘要
        
        Args:
            novel_id: 小说ID
            max_chapters: 最大返回章节数（默认20）
            
        Returns:
            章节摘要字典，键为章节号字符串
        """
        memory = self.get_novel_memory(novel_id)
        if memory and 'chapter_summaries' in memory:
            summaries = memory['chapter_summaries']
            if not summaries:
                return {}
            # 按章节号排序，返回最近的章节摘要
            try:
                sorted_keys = sorted(summaries.keys(), key=lambda x: int(x))[-max_chapters:]
                return {k: summaries[k] for k in sorted_keys}
            except (ValueError, TypeError):
                return summaries
        return {}
    
    def get_chapter_summary(self, novel_id: str, chapter_number: int) -> Optional[Dict[str, Any]]:
        """获取单个章节的摘要
        
        Args:
            novel_id: 小说ID
            chapter_number: 章节号
            
        Returns:
            章节摘要或None
        """
        summaries = self.get_chapter_summaries(novel_id)
        return summaries.get(str(chapter_number))
    
    # ==================== 角色状态管理方法 ====================
    
    def update_character_state(self, novel_id: str, character_name: str, state: Dict[str, Any]) -> None:
        """更新角色状态
        
        Args:
            novel_id: 小说ID
            character_name: 角色名称
            state: 角色状态，包含 last_appearance_chapter, current_location, cultivation_level, 
                   emotional_state, relationships, status, pending_events 等
        """
        cache_key = f"novel:{novel_id}"
        memory = self.get_novel_memory(novel_id)
        if memory:
            if 'character_states' not in memory:
                memory['character_states'] = {}
            # 合并状态而非完全覆盖
            if character_name in memory['character_states']:
                memory['character_states'][character_name].update(state)
            else:
                memory['character_states'][character_name] = state
            # 直接更新缓存
            self.cache.set(cache_key, memory)
            logger.info(f"Updated character '{character_name}' state for novel {novel_id}")
        else:
            logger.warning(f"Cannot update character state: novel {novel_id} not in memory")
    
    def get_character_states(self, novel_id: str) -> Dict[str, Dict]:
        """获取所有角色状态
        
        Args:
            novel_id: 小说ID
            
        Returns:
            角色状态字典，键为角色名称
        """
        memory = self.get_novel_memory(novel_id)
        if memory:
            return memory.get('character_states', {})
        return {}
    
    def get_character_state(self, novel_id: str, character_name: str) -> Optional[Dict[str, Any]]:
        """获取单个角色的状态
        
        Args:
            novel_id: 小说ID
            character_name: 角色名称
            
        Returns:
            角色状态或None
        """
        states = self.get_character_states(novel_id)
        return states.get(character_name)


# 全局记忆服务实例
_novel_memory_service: Optional[NovelMemoryService] = None

def get_novel_memory_service() -> NovelMemoryService:
    """获取小说记忆服务实例"""
    global _novel_memory_service
    if _novel_memory_service is None:
        _novel_memory_service = NovelMemoryService()
    return _novel_memory_service