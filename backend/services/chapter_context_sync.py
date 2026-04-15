"""章节上下文统一同步服务.

确保章节摘要同步到所有存储层（内存缓存 + 持久化存储），
避免三层存储不一致导致的上下文断裂问题。
"""

from typing import Any, Dict

from core.logging_config import logger


class ChapterContextSync:
    """统一的章节上下文同步服务，确保三层存储一致性."""

    def __init__(self, memory_service, persistent_memory):
        """初始化方法.

        Args:
            memory_service: NovelMemoryService 实例
            persistent_memory: NovelMemoryAdapter 实例
        """
        self.memory_service = memory_service
        self.persistent_memory = persistent_memory

    async def sync_chapter_summary(
        self,
        novel_id: str,
        chapter_number: int,
        summary: Dict[str, Any],
    ) -> Dict[str, bool]:
        """同步章节摘要到所有存储层.

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            summary: 章节摘要内容

        Returns:
            {存储层名称: 是否成功}
        """
        results = {
            "memory_service": False,
            "persistent_memory": False,
        }

        # 1. 同步到内存缓存
        try:
            self.memory_service.update_chapter_summary(novel_id, chapter_number, summary)
            results["memory_service"] = True
            logger.debug(
                f"[ContextSync] 内存缓存写入成功 (novel={novel_id[:8]}, ch{chapter_number})"
            )
        except Exception as e:
            logger.error(f"[ContextSync] 内存缓存写入失败 (ch{chapter_number}): {e}")

        # 2. 同步到持久化存储
        try:
            await self.persistent_memory.save_chapter_memory(
                novel_id=novel_id,
                chapter_number=chapter_number,
                content="",  # 内容已在 generation_service 中保存到数据库
                summary=summary,
            )
            results["persistent_memory"] = True
            logger.debug(
                f"[ContextSync] 持久化存储写入成功 (novel={novel_id[:8]}, ch{chapter_number})"
            )
        except Exception as e:
            logger.error(f"[ContextSync] 持久化存储写入失败 (ch{chapter_number}): {e}")

        # 3. 记录整体状态
        all_success = all(results.values())
        if not all_success:
            failed = [k for k, v in results.items() if not v]
            logger.warning(
                f"[ContextSync] 部分存储层写入失败 (ch{chapter_number}): {failed}，"
                f"后续章节可能获取到不一致的上下文"
            )
        else:
            logger.info(
                f"[ContextSync] 第{chapter_number}章摘要已同步到所有存储层"
            )

        return results

    async def verify_consistency(
        self,
        novel_id: str,
        chapter_number: int,
    ) -> bool:
        """验证两层存储的一致性.

        如果不一致，将以持久化存储为准进行修复。

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号

        Returns:
            是否一致
        """
        try:
            mem_summary = self.memory_service.get_chapter_summary(novel_id, chapter_number)
            persist_summary = self.persistent_memory.storage.get_chapter_summary(
                novel_id, chapter_number
            )

            if mem_summary and persist_summary:
                # 比较关键字段
                key_fields = ["key_events", "plot_progress", "ending_state"]
                consistent = all(
                    mem_summary.get(f) == persist_summary.get(f)
                    for f in key_fields
                )
                if not consistent:
                    logger.warning(
                        f"[ContextSync] 检测到存储不一致 (ch{chapter_number})，"
                        f"将以持久化存储为准修复"
                    )
                    # 修复：用持久化存储覆盖内存缓存
                    self.memory_service.update_chapter_summary(
                        novel_id, chapter_number, persist_summary
                    )
                return consistent

            return True  # 都为空也算一致
        except Exception as e:
            logger.error(f"[ContextSync] 一致性验证失败: {e}")
            return False
