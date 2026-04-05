"""章节助手上下文构建服务.

为章节编辑助手构建丰富的上下文信息，包括前序章节摘要、角色信息、情节上下文等。
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.logging_config import logger
from core.models.chapter import Chapter
from core.models.novel import Novel
from core.models.plot_outline import PlotOutline


@dataclass
class ChapterAssistantContext:
    """章节助手上下文数据结构."""

    # 当前章节信息
    chapter_number: int
    chapter_title: str
    chapter_content: str
    word_count: int

    # 小说基本信息
    novel_title: str
    novel_genre: str

    # 前序章节摘要（最多3章）
    previous_chapters_summary: str = ""

    # 本章涉及角色
    chapter_characters: list[dict] = field(default_factory=list)

    # 情节上下文
    plot_context: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式."""
        return {
            "chapter_number": self.chapter_number,
            "chapter_title": self.chapter_title,
            "chapter_content": self.chapter_content,
            "word_count": self.word_count,
            "novel_title": self.novel_title,
            "novel_genre": self.novel_genre,
            "previous_chapters_summary": self.previous_chapters_summary,
            "chapter_characters": self.chapter_characters,
            "plot_context": self.plot_context,
        }


class ChapterContextBuilder:
    """章节助手上下文构建器.

    构建章节编辑所需的完整上下文，包括：
    - 小说基本信息
    - 前序章节摘要
    - 本章涉及的角色信息
    - 情节上下文（大纲）
    """

    def __init__(self, db: AsyncSession, memory_service: Any = None):
        """初始化构建器.

        Args:
            db: 数据库会话
            memory_service: 持久化记忆服务（可选）
        """
        self.db = db
        self.memory_service = memory_service

    async def build_context(
        self,
        novel_id: str,
        chapter_number: int,
        chapter_info: dict[str, Any],
    ) -> ChapterAssistantContext:
        """构建章节编辑所需的完整上下文.

        Args:
            novel_id: 小说ID
            chapter_number: 当前章节号
            chapter_info: 当前章节信息（包含content, title等）

        Returns:
            完整的章节助手上下文
        """
        # 获取小说基本信息
        novel_data = await self._get_novel_data(novel_id)
        novel_title = novel_data.get("title", "未知小说") if novel_data else "未知小说"
        novel_genre = novel_data.get("genre", "") if novel_data else ""

        # 获取前序章节摘要
        previous_summary = await self._get_previous_chapters_summary(novel_id, chapter_number)

        # 识别本章涉及的角色
        all_characters = novel_data.get("characters", []) if novel_data else []
        chapter_characters = self._identify_chapter_characters(
            chapter_info.get("content", ""), all_characters
        )

        # 获取情节上下文
        plot_context = await self._get_plot_context(novel_id)

        return ChapterAssistantContext(
            chapter_number=chapter_number,
            chapter_title=chapter_info.get("title", f"第{chapter_number}章"),
            chapter_content=chapter_info.get("content", ""),
            word_count=chapter_info.get("word_count", 0),
            novel_title=novel_title,
            novel_genre=novel_genre,
            previous_chapters_summary=previous_summary,
            chapter_characters=chapter_characters,
            plot_context=plot_context,
        )

    async def _get_novel_data(self, novel_id: str) -> dict[str, Any] | None:
        """从数据库获取小说数据.

        Args:
            novel_id: 小说ID

        Returns:
            小说数据字典
        """
        try:
            novel_uuid = UUID(novel_id)
        except ValueError:
            logger.error(f"无效的小说ID格式: {novel_id}")
            return None

        try:
            query = (
                select(Novel)
                .where(Novel.id == novel_uuid)
                .options(
                    selectinload(Novel.characters),
                    selectinload(Novel.plot_outline),
                )
            )
            result = await self.db.execute(query)
            novel = result.scalar_one_or_none()

            if not novel:
                return None

            return {
                "id": str(novel.id),
                "title": novel.title,
                "genre": novel.genre,
                "characters": [
                    {
                        "id": str(char.id),
                        "name": char.name,
                        "role_type": char.role_type,
                        "personality": char.personality,
                        "background": char.background,
                        "appearance": char.appearance,
                    }
                    for char in novel.characters
                ],
                "plot_outline": novel.plot_outline,
            }
        except Exception as e:
            logger.error(f"获取小说数据失败: {e}")
            return None

    async def _get_previous_chapters_summary(
        self,
        novel_id: str,
        current_chapter: int,
        count: int = 3,
    ) -> str:
        """获取前序章节摘要.

        优先从持久化记忆中获取章节摘要，如果没有则从数据库加载简要信息。

        Args:
            novel_id: 小说ID
            current_chapter: 当前章节号
            count: 要获取的前序章节数量

        Returns:
            前序章节摘要文本
        """
        # 尝试从记忆服务获取
        if self.memory_service:
            memory = self.memory_service.get_novel_memory(novel_id)
            if memory:
                chapter_summaries = memory.get("chapter_summaries", {})
                summaries = []
                for ch_num in range(current_chapter - 1, max(0, current_chapter - count - 1), -1):
                    if str(ch_num) in chapter_summaries:
                        summaries.append(f"第{ch_num}章: {chapter_summaries[str(ch_num)]}")

                if summaries:
                    return "\n".join(summaries)

        # 从数据库获取简要信息
        try:
            novel_uuid = UUID(novel_id)
        except ValueError:
            return "暂无前序章节信息"

        try:
            start_chapter = max(1, current_chapter - count)
            query = (
                select(Chapter)
                .where(
                    Chapter.novel_id == novel_uuid,
                    Chapter.chapter_number >= start_chapter,
                    Chapter.chapter_number < current_chapter,
                )
                .order_by(Chapter.chapter_number.desc())
            )

            result = await self.db.execute(query)
            chapters = result.scalars().all()

            if not chapters:
                return "暂无前序章节信息"

            summaries = []
            for ch in chapters:
                # 生成简要摘要（取前200字）
                content = ch.content or ""
                summary = content[:200] + "..." if len(content) > 200 else content
                summaries.append(f"第{ch.chapter_number}章《{ch.title or '无标题'}》: {summary}")

            return "\n".join(summaries)

        except Exception as e:
            logger.error(f"获取前序章节摘要失败: {e}")
            return "暂无前序章节信息"

    def _identify_chapter_characters(
        self,
        chapter_content: str,
        all_characters: list[dict],
    ) -> list[dict]:
        """识别章节涉及的角色.

        通过角色名称在章节内容中进行匹配来识别。

        Args:
            chapter_content: 章节内容
            all_characters: 所有角色列表

        Returns:
            本章涉及的角色列表
        """
        if not chapter_content or not all_characters:
            return []

        involved_characters = []
        for char in all_characters:
            char_name = char.get("name", "")
            if char_name and char_name in chapter_content:
                involved_characters.append(
                    {
                        "name": char_name,
                        "role_type": char.get("role_type", ""),
                        "personality": char.get("personality", ""),
                    }
                )

        return involved_characters

    async def _get_plot_context(self, novel_id: str) -> str | None:
        """获取情节上下文.

        从大纲中提取当前章节相关的情节信息。

        Args:
            novel_id: 小说ID

        Returns:
            情节上下文文本
        """
        try:
            novel_uuid = UUID(novel_id)
        except ValueError:
            return None

        try:
            query = select(PlotOutline).where(PlotOutline.novel_id == novel_uuid)
            result = await self.db.execute(query)
            plot_outline = result.scalar_one_or_none()

            if not plot_outline:
                return None

            # 返回大纲原文
            raw_content = plot_outline.raw_content
            if raw_content:
                # 截取前1000字作为上下文
                if len(raw_content) > 1000:
                    return raw_content[:1000] + "..."
                return raw_content

            return None

        except Exception as e:
            logger.error(f"获取情节上下文失败: {e}")
            return None


def format_characters_for_prompt(characters: list[dict]) -> str:
    """格式化角色信息用于 System Prompt.

    Args:
        characters: 角色信息列表

    Returns:
        格式化后的角色描述文本
    """
    if not characters:
        return "暂无角色信息"

    lines = []
    for char in characters:
        name = char.get("name", "未知角色")
        role_type = char.get("role_type", "")
        personality = char.get("personality", "")

        role_text = f"【{role_type}】" if role_type else ""
        personality_text = f" - {personality[:50]}" if personality else ""
        lines.append(f"- {name}{role_text}{personality_text}")

    return "\n".join(lines)
