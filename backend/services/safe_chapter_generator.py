"""
章节生成失败处理增强模块

提供章节生成失败时的安全处理机制，确保：
1. 立即终止后续章节生成
2. 保护已生成章节数据完整性
3. 使用独立事务隔离每个章节
4. 准确的错误日志和状态追踪
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import logger
from core.models.novel import Novel
from core.models.chapter import Chapter, ChapterStatus
from core.models.generation_task import GenerationTask, TaskType, TaskStatus


class ChapterGenerationFailure(Exception):
    """章节生成失败异常"""
    def __init__(self, chapter_number: int, reason: str, original_error: Optional[Exception] = None):
        self.chapter_number = chapter_number
        self.reason = reason
        self.original_error = original_error
        super().__init__(f"第{chapter_number}章生成失败：{reason}")


class BatchGenerationInterrupted(Exception):
    """批量生成中断异常"""
    def __init__(self, continuous_failures: int, last_failed_chapter: int):
        self.continuous_failures = continuous_failures
        self.last_failed_chapter = last_failed_chapter
        super().__init__(
            f"连续{continuous_failures}章失败，批量生成已中断（最后失败：第{last_failed_chapter}章）"
        )


class SafeChapterGenerator:
    """安全的章节生成器

    实现章节生成失败的安全处理机制
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.max_continuous_failures = 2  # 连续失败阈值

    async def generate_chapter_safely(
        self,
        novel_id: UUID,
        chapter_number: int,
        generation_func,
        **kwargs
    ) -> Dict[str, Any]:
        """
        安全生成单个章节

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            generation_func: 实际的章节生成函数
            **kwargs: 传递给生成函数的参数

        Returns:
            生成结果字典

        Raises:
            ChapterGenerationFailure: 章节生成失败
        """
        logger.info(f"📝 开始生成第{chapter_number}章")

        try:
            # 1. 前置条件检查
            await self._validate_generation_prerequisites(novel_id, chapter_number)

            # 2. 执行章节生成
            generation_result = await generation_func(novel_id, chapter_number, **kwargs)

            # 3. 验证生成结果
            self._validate_generation_result(generation_result, chapter_number)

            # 4. 保存章节到数据库（独立事务）
            await self._save_chapter_independently(novel_id, chapter_number, generation_result)

            # 5. 记录成功日志
            word_count = len(generation_result.get("final_content", ""))
            logger.info(
                f"✅ 第{chapter_number}章生成成功 "
                f"(字数：{word_count}, 质量：{generation_result.get('quality_score', 0):.1f})"
            )

            return {
                "status": "success",
                "chapter_number": chapter_number,
                "result": generation_result,
            }

        except ChapterGenerationFailure:
            # 已经是章节生成失败异常，直接抛出
            raise

        except Exception as e:
            # 其他异常转换为章节生成失败异常
            logger.error(f"❌ 第{chapter_number}章生成异常：{e}")
            raise ChapterGenerationFailure(
                chapter_number=chapter_number,
                reason=str(e),
                original_error=e
            )

    async def generate_batch_safely(
        self,
        novel_id: UUID,
        from_chapter: int,
        to_chapter: int,
        generation_func,
        task_id: Optional[UUID] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        安全批量生成章节

        Args:
            novel_id: 小说 ID
            from_chapter: 起始章节
            to_chapter: 结束章节
            generation_func: 章节生成函数
            task_id: 任务 ID（可选）
            **kwargs: 传递给生成函数的参数

        Returns:
            批量生成结果

        Raises:
            BatchGenerationInterrupted: 批量生成被中断
        """
        total_chapters = to_chapter - from_chapter + 1
        logger.info(
            f"🚀 开始批量生成章节：第{from_chapter}-{to_chapter}章，共 {total_chapters} 章"
        )

        results = []
        continuous_failures = 0
        successful_chapters = []
        failed_chapters = []

        try:
            for chapter_num in range(from_chapter, to_chapter + 1):
                try:
                    # 生成单章
                    result = await self.generate_chapter_safely(
                        novel_id=novel_id,
                        chapter_number=chapter_num,
                        generation_func=generation_func,
                        **kwargs
                    )

                    results.append(result)
                    successful_chapters.append(chapter_num)
                    continuous_failures = 0  # 重置连续失败计数

                except ChapterGenerationFailure as e:
                    # 章节生成失败
                    logger.error(f"❌ 第{chapter_num}章生成失败：{e.reason}")

                    results.append({
                        "status": "failed",
                        "chapter_number": chapter_num,
                        "error": e.reason,
                    })
                    failed_chapters.append(chapter_num)
                    continuous_failures += 1

                    # 检查是否需要中断
                    if continuous_failures >= self.max_continuous_failures:
                        logger.error(
                            f"⚠️ 连续{self.max_continuous_failures}章生成失败，"
                            f"批量生成已中断（最后失败：第{chapter_num}章）"
                        )

                        # 记录剩余未生成的章节
                        remaining_chapters = list(range(chapter_num + 1, to_chapter + 1))
                        if remaining_chapters:
                            logger.warning(f"剩余未生成章节：{remaining_chapters}")

                        # 抛出中断异常
                        raise BatchGenerationInterrupted(
                            continuous_failures=continuous_failures,
                            last_failed_chapter=chapter_num
                        )

            # 批量生成完成
            logger.info(
                f"🎉 批量生成完成：成功 {len(successful_chapters)} 章，"
                f"失败 {len(failed_chapters)} 章"
            )

            return {
                "status": "completed",
                "total_chapters": total_chapters,
                "successful_chapters": successful_chapters,
                "failed_chapters": failed_chapters,
                "results": results,
                "interrupted": False,
            }

        except BatchGenerationInterrupted:
            # 批量生成被中断
            logger.warning("批量生成已中断")

            return {
                "status": "interrupted",
                "total_chapters": total_chapters,
                "successful_chapters": successful_chapters,
                "failed_chapters": failed_chapters,
                "results": results,
                "interrupted": True,
            }

    async def _validate_generation_prerequisites(
        self,
        novel_id: UUID,
        chapter_number: int
    ):
        """验证生成前置条件"""
        # 检查小说是否存在
        novel_result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        if not novel:
            raise ValueError(f"小说 {novel_id} 不存在")

        # 检查章节是否已存在
        existing_chapter = await self.db.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number
            )
        )
        if existing_chapter.scalar_one_or_none():
            raise ValueError(f"第{chapter_number}章已存在")

        # 检查小说是否有大纲
        if not novel.plot_outline:
            logger.warning(f"小说 {novel_id} 缺少大纲，但仍然继续生成")

    def _validate_generation_result(
        self,
        result: Dict[str, Any],
        chapter_number: int
    ):
        """验证生成结果"""
        if not result:
            raise ValueError("生成结果为空")

        final_content = result.get("final_content", "")
        if not final_content:
            raise ValueError(f"第{chapter_number}章内容为空")

        if len(final_content) < 100:
            logger.warning(f"第{chapter_number}章字数过少：{len(final_content)}")

    async def _save_chapter_independently(
        self,
        novel_id: UUID,
        chapter_number: int,
        generation_result: Dict[str, Any]
    ):
        """
        独立保存章节到数据库

        使用独立事务，确保提交后不受后续操作影响
        """
        final_content = generation_result.get("final_content", "")
        chapter_plan = generation_result.get("chapter_plan", {})

        # 创建章节对象
        chapter = Chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            volume_number=generation_result.get("volume_number", 1),
            title=chapter_plan.get("title", f"第{chapter_number}章"),
            content=final_content,
            word_count=len(final_content),
            status=ChapterStatus.draft,
            outline=chapter_plan,
            plot_points=chapter_plan.get("plot_points", []),
            foreshadowing=chapter_plan.get("foreshadowing", []),
            quality_score=generation_result.get("quality_score", 0),
            continuity_issues=generation_result.get("continuity_report", {}).get("issues", []),
            detailed_outline=generation_result.get("detailed_outline", {}),
        )

        self.db.add(chapter)

        # 更新小说统计
        novel = await self._get_novel(novel_id)
        if novel:
            novel.chapter_count = (novel.chapter_count or 0) + 1
            novel.word_count = (novel.word_count or 0) + len(final_content)

            # 更新 token 成本
            cost = generation_result.get("cost", 0)
            if cost:
                novel.token_cost = (novel.token_cost or Decimal("0")) + Decimal(str(cost))

        # 立即提交事务
        await self.db.commit()

        # 刷新对象获取 ID
        await self.db.refresh(chapter)

        logger.debug(f"第{chapter_number}章已保存到数据库 (ID: {chapter.id})")

    async def _get_novel(self, novel_id: UUID) -> Optional[Novel]:
        """获取小说对象"""
        result = await self.db.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        return result.scalar_one_or_none()


async def safe_generate_single_chapter(
    db: AsyncSession,
    novel_id: UUID,
    chapter_number: int,
    generation_func,
    **kwargs
) -> Dict[str, Any]:
    """
    安全生成单个章节的便捷函数

    Args:
        db: 数据库会话
        novel_id: 小说 ID
        chapter_number: 章节号
        generation_func: 生成函数
        **kwargs: 其他参数

    Returns:
        生成结果
    """
    generator = SafeChapterGenerator(db)
    return await generator.generate_chapter_safely(
        novel_id=novel_id,
        chapter_number=chapter_number,
        generation_func=generation_func,
        **kwargs
    )


async def safe_generate_batch_chapters(
    db: AsyncSession,
    novel_id: UUID,
    from_chapter: int,
    to_chapter: int,
    generation_func,
    task_id: Optional[UUID] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    安全批量生成章节的便捷函数

    Args:
        db: 数据库会话
        novel_id: 小说 ID
        from_chapter: 起始章节
        to_chapter: 结束章节
        generation_func: 生成函数
        task_id: 任务 ID
        **kwargs: 其他参数

    Returns:
        批量生成结果
    """
    generator = SafeChapterGenerator(db)
    return await generator.generate_batch_safely(
        novel_id=novel_id,
        from_chapter=from_chapter,
        to_chapter=to_chapter,
        generation_func=generation_func,
        task_id=task_id,
        **kwargs
    )
