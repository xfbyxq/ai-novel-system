"""上下文构建器 - 构建章节生成的上下文."""

from typing import TYPE_CHECKING, Callable
from uuid import UUID

from core.logging_config import logger
from core.models.novel import Novel

if TYPE_CHECKING:
    from backend.services.agentmesh_memory_adapter import NovelMemoryAdapter
    from backend.services.context_manager import UnifiedContextManager
    from backend.services.memory_service import NovelMemoryService


class ContextBuilder:
    """上下文构建器，负责构建章节生成的上下文."""

    def __init__(
        self,
        memory_service: "NovelMemoryService",
        persistent_memory: "NovelMemoryAdapter",
        get_context_manager: Callable[[UUID], "UnifiedContextManager"],
    ):
        """初始化上下文构建器.

        Args:
            memory_service: 内存记忆服务
            persistent_memory: 持久化记忆适配器
            get_context_manager: 获取上下文管理器的回调函数
        """
        self.memory_service = memory_service
        self.persistent_memory = persistent_memory
        self._get_context_manager = get_context_manager

    def build_previous_context(
        self, novel_id: UUID, novel: Novel, chapter_number: int
    ) -> str:
        """构建结构化的前置章节上下文.

        使用记忆系统中的结构化摘要，保留完整内容，由调用方统一压缩。

        Args:
            novel_id: 小说ID
            novel: Novel对象（包含已加载的chapters）
            chapter_number: 当前章节号

        Returns:
            前置章节上下文字符串
        """
        # 首先尝试从记忆系统获取结构化摘要
        summaries = self.memory_service.get_chapter_summaries(str(novel_id))

        previous_context = ""
        for ch in sorted(novel.chapters, key=lambda c: c.chapter_number):
            if ch.chapter_number < chapter_number and ch.content:
                ch_num_str = str(ch.chapter_number)
                if ch_num_str in summaries:
                    # 使用结构化摘要（完整内容）
                    summary = summaries[ch_num_str]
                    previous_context += f"\n## 第{ch.chapter_number}章 {ch.title or ''}\n"

                    key_events = summary.get("key_events", [])
                    if key_events:
                        if isinstance(key_events, list):
                            # 保留完整事件列表
                            previous_context += (
                                f"**主要事件**: {', '.join(str(e) for e in key_events)}\n"
                            )
                        else:
                            previous_context += f"**主要事件**: {key_events}\n"

                    char_changes = summary.get("character_changes", "")
                    if char_changes:
                        # 保留完整角色变化描述
                        previous_context += f"**角色变化**: {char_changes}\n"

                    plot_progress = summary.get("plot_progress", "")
                    if plot_progress:
                        # 保留完整情节摘要
                        previous_context += f"**情节推进**: {plot_progress}\n"

                    foreshadowing = summary.get("foreshadowing", [])
                    if foreshadowing:
                        if isinstance(foreshadowing, list) and foreshadowing:
                            # 保留完整伏笔列表
                            previous_context += (
                                f"**伏笔**: {', '.join(str(f) for f in foreshadowing)}\n"
                            )
                else:
                    # 无结构化摘要时，保留完整章节内容（由统一压缩处理）
                    previous_context += (
                        f"\n## 第{ch.chapter_number}章 {ch.title or ''}\n{ch.content}\n"
                    )

        return previous_context

    async def build_previous_context_enhanced(
        self, novel_id: UUID, novel: Novel, chapter_number: int
    ) -> str:
        """构建增强的前置章节上下文.

        优先使用持久化记忆系统，回退到内存缓存和数据库。

        Args:
            novel_id: 小说ID
            novel: Novel对象
            chapter_number: 当前章节号

        Returns:
            前置章节上下文字符串
        """
        novel_id_str = str(novel_id)

        # 1. 首先尝试从持久化记忆获取上下文
        try:
            persistent_context = await self.persistent_memory.get_chapter_context(
                novel_id=novel_id_str, chapter_number=chapter_number, context_chapters=5
            )
            if persistent_context:
                logger.debug(f"Using persistent memory context for chapter {chapter_number}")
                return persistent_context
        except Exception as e:
            logger.warning(f"Failed to get persistent memory context: {e}")

        # 2. 回退到统一上下文管理器
        context_manager = self._get_context_manager(novel_id)
        return await context_manager.build_previous_context(
            chapter_number=chapter_number,
            count=3,
        )
