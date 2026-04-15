"""统一上下文管理器 - 解决三层存储碎片化问题 (Issue #34).

问题：
1. 三层上下文存储：GenerationService._team_contexts (内存字典)、MemoryService (内存缓存)、PersistentMemory (SQLite)
2. 数据同步依赖手动调用，容易遗漏
3. 内存泄漏风险 (_team_contexts 无清理机制)
4. 上下文构建逻辑重复 (_build_previous_context 和 _build_previous_context_enhanced)

解决方案：
1. 创建 UnifiedContextManager 统一管理三层存储
2. 实现自动同步机制
3. 添加内存清理策略 (LRU + TTL)
4. 统一上下文构建逻辑
"""

import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.chapter import Chapter
from core.models.novel import Novel
from core.models.plot_outline import PlotOutline

logger = logging.getLogger(__name__)


class LRUCache:
    """LRU 缓存实现，带 TTL 过期."""

    def __init__(self, max_size: int = 100, ttl_minutes: int = 30):
        """
        初始化 LRU 缓存.
        
        Args:
            max_size: 最大缓存数量
            ttl_minutes: 过期时间 (分钟)
        """
        self.max_size = max_size
        self.ttl_minutes = ttl_minutes
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.timestamps: Dict[str, datetime] = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存，更新访问时间."""
        if key not in self.cache:
            return None
        
        # 检查是否过期
        if datetime.now() > self.timestamps[key]:
            self.delete(key)
            return None
        
        # 移动到末尾 (最近使用)
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: Any) -> None:
        """设置缓存，如果已满则删除最旧的."""
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                # 删除最旧的
                oldest_key = next(iter(self.cache))
                self.delete(oldest_key)
        
        self.cache[key] = value
        self.timestamps[key] = datetime.now() + timedelta(minutes=self.ttl_minutes)

    def delete(self, key: str) -> None:
        """删除缓存."""
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]

    def clear(self) -> None:
        """清空缓存."""
        self.cache.clear()
        self.timestamps.clear()

    def cleanup_expired(self) -> int:
        """清理过期项，返回清理数量."""
        now = datetime.now()
        expired_keys = [
            key for key, ts in self.timestamps.items()
            if now > ts
        ]
        for key in expired_keys:
            self.delete(key)
        return len(expired_keys)


class UnifiedContextManager:
    """
    统一上下文管理器.
    
    核心功能：
    1. 统一管理三层存储（内存缓存、MemoryService、SQLite 持久化）
    2. 自动同步机制
    3. LRU + TTL 清理策略
    4. 统一的上下文构建接口
    """

    def __init__(
        self,
        db: AsyncSession,
        novel_id: UUID,
        cache_max_size: int = 100,
        cache_ttl_minutes: int = 30,
    ):
        """
        初始化上下文管理器.
        
        Args:
            db: 数据库会话
            novel_id: 小说 ID
            cache_max_size: 缓存最大大小
            cache_ttl_minutes: 缓存过期时间
        """
        self.db = db
        self.novel_id = novel_id
        self.novel_id_str = str(novel_id)
        
        # 三层存储
        self.memory_cache = LRUCache(max_size=cache_max_size, ttl_minutes=cache_ttl_minutes)
        self._memory_service_cache = None  # 延迟加载
        self._persistent_memory = None  # 延迟加载
        
        # 上下文数据
        self._current_context: Dict[str, Any] = {}
        self._context_version = 0

    @property
    def memory_service_cache(self):
        """延迟加载 MemoryService 缓存."""
        if self._memory_service_cache is None:
            from backend.services.memory_service import NovelMemoryService
            self._memory_service_cache = NovelMemoryService()
        return self._memory_service_cache

    @property
    def persistent_memory(self):
        """延迟加载持久化记忆."""
        if self._persistent_memory is None:
            from backend.services.agentmesh_memory_adapter import NovelMemoryStorage
            # 使用正确的数据库路径，而不是 novel_id 作为文件名
            db_path = "./novel_memory/novel_memory.db"
            self._persistent_memory = NovelMemoryStorage(db_path)
        return self._persistent_memory

    async def get_chapter_context(
        self,
        chapter_number: int,
        include_previous: bool = True,
        previous_count: int = 3,
    ) -> Dict[str, Any]:
        """
        获取章节上下文.
        
        Args:
            chapter_number: 章节号
            include_previous: 是否包含前文章节
            previous_count: 前文章节数量
        
        Returns:
            上下文数据
        """
        cache_key = f"chapter_{chapter_number}_context"
        
        # 1. 先查内存缓存
        cached = self.memory_cache.get(cache_key)
        if cached:
            logger.debug(f"Cache hit for {cache_key}")
            return cached
        
        # 2. 查 MemoryService 缓存
        memory_service_context = self.memory_service_cache.get_chapter_summary(self.novel_id_str, chapter_number)
        if memory_service_context:
            self.memory_cache.set(cache_key, memory_service_context)
            return memory_service_context
        
        # 3. 查 SQLite 持久化
        persistent_context = self.persistent_memory.get_chapter_summary(self.novel_id_str, chapter_number)
        if persistent_context:
            # 同步到上层缓存
            self.memory_cache.set(cache_key, persistent_context)
            self.memory_service_cache.set_chapter_summary(self.novel_id_str, chapter_number, persistent_context)
            return persistent_context
        
        # 4. 从数据库加载章节
        chapter_context = await self._load_chapter_from_db(chapter_number)
        if chapter_context:
            # 同步到所有层
            await self._sync_to_all_layers(chapter_number, chapter_context)
            return chapter_context
        
        return {}

    async def _load_chapter_from_db(self, chapter_number: int) -> Optional[Dict[str, Any]]:
        """从数据库加载章节."""
        query = select(Chapter).where(
            Chapter.novel_id == self.novel_id,
            Chapter.chapter_number == chapter_number,
        ).order_by(Chapter.created_at.desc()).limit(1)
        result = await self.db.execute(query)
        chapter = result.scalars().first()
        
        if not chapter:
            return None
        
        return {
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "content": chapter.content,
            "word_count": chapter.word_count,
            "outline": chapter.outline,
            "characters_appeared": chapter.characters_appeared,
            "plot_points": chapter.plot_points,
            "foreshadowing": chapter.foreshadowing,
        }

    async def _sync_to_all_layers(
        self,
        chapter_number: int,
        context: Dict[str, Any],
    ) -> None:
        """同步上下文到所有存储层."""
        cache_key = f"chapter_{chapter_number}_context"
        
        # 1. 内存缓存
        self.memory_cache.set(cache_key, context)
        
        # 2. MemoryService
        self.memory_service_cache.set_chapter_summary(self.novel_id_str, chapter_number, context)
        
        # 3. SQLite 持久化
        self.persistent_memory.save_chapter_summary(
            novel_id=self.novel_id_str,
            chapter_number=chapter_number,
            summary=context,
        )
        
        logger.debug(f"Synced chapter {chapter_number} context to all layers")

    async def update_chapter_context(
        self,
        chapter_number: int,
        context: Dict[str, Any],
        sync_immediately: bool = True,
    ) -> None:
        """
        更新章节上下文.
        
        Args:
            chapter_number: 章节号
            context: 上下文数据
            sync_immediately: 是否立即同步到所有层
        """
        cache_key = f"chapter_{chapter_number}_context"
        
        # 1. 更新内存缓存
        self.memory_cache.set(cache_key, context)
        
        # 2. 更新 MemoryService
        self.memory_service_cache.set_chapter_summary(self.novel_id_str, chapter_number, context)
        
        # 3. 同步到持久化
        if sync_immediately:
            self.persistent_memory.save_chapter_summary(
                novel_id=self.novel_id_str,
                chapter_number=chapter_number,
                summary=context,
            )
        
        self._context_version += 1
        logger.info(f"Updated chapter {chapter_number} context (version {self._context_version})")

    async def build_previous_context(
        self,
        current_chapter: int,
        count: int = 3,
    ) -> str:
        """
        构建前文章节上下文.
        
        保留完整内容，由调用方统一压缩处理。
        
        Args:
            current_chapter: 当前章节号
            count: 需要的前文章节数量
        
        Returns:
            格式化的前文文本
        """
        previous_contexts = []
        
        for ch_num in range(max(1, current_chapter - count), current_chapter):
            context = await self.get_chapter_context(ch_num, include_previous=False)
            if context:
                # 保留完整内容，由统一压缩处理
                previous_contexts.append(
                    f"第{ch_num}章 {context.get('title', '')}:\n"
                    f"{context.get('content', '')}"
                )
        
        return "\n\n".join(previous_contexts)

    async def get_novel_memory(self) -> Dict[str, Any]:
        """获取小说基础记忆."""
        cache_key = f"novel_{self.novel_id_str}_memory"
        
        # 先查缓存
        cached = self.memory_cache.get(cache_key)
        if cached:
            return cached
        
        # 从数据库加载
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == self.novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        
        if not novel:
            return {}
        
        memory = {
            "title": novel.title,
            "genre": novel.genre,
            "synopsis": novel.synopsis,
            "word_count": novel.word_count,
            "chapter_count": novel.chapter_count,
            "created_at": novel.created_at.isoformat() if novel.created_at else None,
        }
        
        # 加载大纲
        outline_result = await self.db.execute(
            select(PlotOutline).where(PlotOutline.novel_id == self.novel_id)
        )
        outline = outline_result.scalar_one_or_none()
        
        if outline:
            memory["outline"] = {
                "structure_type": outline.structure_type,
                "volumes": outline.volumes,
                "main_plot": outline.main_plot,
            }
        
        # 缓存
        self.memory_cache.set(cache_key, memory)
        self.memory_service_cache.set_novel_memory(self.novel_id_str, memory)
        
        return memory

    async def cleanup(self) -> Dict[str, int]:
        """
        清理过期缓存.
        
        Returns:
            清理统计
        """
        stats = {
            "memory_cache_expired": self.memory_cache.cleanup_expired(),
            "memory_service_cleaned": 0,
        }
        
        # MemoryService 也有清理逻辑
        if self._memory_service_cache:
            stats["memory_service_cleaned"] = self._memory_service_cache.cleanup()
        
        logger.info(f"Context cleanup completed: {stats}")
        return stats

    async def refresh_all(self) -> None:
        """刷新所有缓存."""
        logger.info("Refreshing all context caches...")
        
        # 清空内存缓存
        self.memory_cache.clear()
        
        # 重新加载小说记忆
        await self.get_novel_memory()
        
        logger.info("All context caches refreshed")
