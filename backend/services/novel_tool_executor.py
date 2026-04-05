"""小说信息查询工具执行器.

为AI聊天服务提供按需查询小说数据的工具，支持LLM通过Function Calling自主获取所需信息。
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.novel import Novel

logger = logging.getLogger(__name__)

# 工具定义：供LLM调用的小说查询工具
NOVEL_QUERY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_chapter_content",
            "description": "获取指定范围章节内容。用于分析具体章节时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_start": {
                        "type": "integer",
                        "description": "开始章节号（必填）",
                    },
                    "chapter_end": {
                        "type": "integer",
                        "description": "结束章节号（可选，不填则只获取chapter_start对应的一章）",
                    },
                },
                "required": ["chapter_start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_character_info",
            "description": "获取指定角色的详细信息。当用户询问角色、人物相关问题时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_name": {
                        "type": "string",
                        "description": "角色名称（可选，不填则返回所有角色列表）",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_world_setting",
            "description": "获取世界观设定。当用户询问世界观、背景设定、修炼体系等问题时调用。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_outline",
            "description": "获取剧情大纲。当用户询问大纲、剧情走向、主线支线等问题时调用。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_chapters",
            "description": "获取章节列表（标题、字数，不含内容）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_novel_info",
            "description": "获取小说基本信息（标题、类型、简介等）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class NovelToolExecutor:
    """小说信息查询工具执行器.

    为LLM提供按需查询小说数据的能力，避免一次性加载所有内容导致上下文膨胀。
    """

    def __init__(self, db: AsyncSession, novel_id: str):
        """初始化工具执行器.

        Args:
            db: 数据库会话
            novel_id: 小说ID
        """
        self.db = db
        self.novel_id = novel_id
        self._novel_cache: dict[str, Any] | None = None

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """执行工具调用.

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        logger.info(f"执行工具调用: {tool_name}, 参数: {arguments}")

        try:
            if tool_name == "get_chapter_content":
                return await self._get_chapter_content(**arguments)
            elif tool_name == "get_character_info":
                return await self._get_character_info(**arguments)
            elif tool_name == "get_world_setting":
                return await self._get_world_setting()
            elif tool_name == "get_outline":
                return await self._get_outline()
            elif tool_name == "list_chapters":
                return await self._list_chapters()
            elif tool_name == "get_novel_info":
                return await self._get_novel_info()
            else:
                return {"error": f"未知工具: {tool_name}"}
        except Exception as e:
            logger.error(f"工具执行失败 {tool_name}: {e}")
            return {"error": f"工具执行失败: {str(e)}"}

    async def _ensure_novel_loaded(self) -> dict:
        """确保小说数据已加载."""
        if self._novel_cache is not None:
            return self._novel_cache

        try:
            novel_id = UUID(self.novel_id)
        except ValueError:
            return {"error": "无效的小说ID格式"}

        query = (
            select(Novel)
            .where(Novel.id == novel_id)
            .options(
                selectinload(Novel.world_setting),
                selectinload(Novel.characters),
                selectinload(Novel.plot_outline),
                selectinload(Novel.chapters),
            )
        )
        result = await self.db.execute(query)
        novel = result.scalar_one_or_none()

        if not novel:
            self._novel_cache = {"error": "小说不存在"}
        else:
            self._novel_cache = {"novel": novel}

        return self._novel_cache

    async def _get_chapter_content(
        self, chapter_start: int, chapter_end: int | None = None
    ) -> dict:
        """获取章节内容.

        Args:
            chapter_start: 开始章节号
            chapter_end: 结束章节号（可选）

        Returns:
            章节内容字典
        """
        data = await self._ensure_novel_loaded()
        if "error" in data:
            return data

        novel = data["novel"]
        if chapter_end is None:
            chapter_end = chapter_start

        chapters_data = []
        for chapter in novel.chapters:
            if chapter_start <= chapter.chapter_number <= chapter_end:
                chapters_data.append({
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title or f"第{chapter.chapter_number}章",
                    "content": chapter.content or "",
                    "word_count": len(chapter.content) if chapter.content else 0,
                })

        if not chapters_data:
            return {
                "error": f"未找到第{chapter_start}-{chapter_end}章的内容",
                "available_chapters": [ch.chapter_number for ch in novel.chapters],
            }

        return {
            "chapters": chapters_data,
            "requested_range": f"{chapter_start}-{chapter_end}",
            "found_count": len(chapters_data),
        }

    async def _get_character_info(self, character_name: str | None = None) -> dict:
        """获取角色信息.

        Args:
            character_name: 角色名称（可选）

        Returns:
            角色信息字典
        """
        data = await self._ensure_novel_loaded()
        if "error" in data:
            return data

        novel = data["novel"]
        characters = list(novel.characters)

        if character_name:
            # 查找指定角色
            for char in characters:
                if char.name == character_name:
                    return {
                        "character": {
                            "id": str(char.id),
                            "name": char.name,
                            "role_type": char.role_type,
                            "personality": char.personality,
                            "background": char.background,
                            "appearance": char.appearance,
                        }
                    }
            return {
                "error": f"未找到角色: {character_name}",
                "available_characters": [c.name for c in characters],
            }
        else:
            # 返回所有角色列表
            return {
                "characters": [
                    {
                        "id": str(char.id),
                        "name": char.name,
                        "role_type": char.role_type,
                        "personality": (char.personality[:200] if char.personality else None),
                    }
                    for char in characters
                ],
                "total_count": len(characters),
            }

    async def _get_world_setting(self) -> dict:
        """获取世界观设定."""
        data = await self._ensure_novel_loaded()
        if "error" in data:
            return data

        novel = data["novel"]
        if not novel.world_setting:
            return {"error": "该小说暂无世界观设定"}

        ws = novel.world_setting
        return {
            "world_setting": {
                "id": str(ws.id),
                "world_type": ws.world_type,
                "raw_content": ws.raw_content or "",
            }
        }

    async def _get_outline(self) -> dict:
        """获取剧情大纲."""
        data = await self._ensure_novel_loaded()
        if "error" in data:
            return data

        novel = data["novel"]
        if not novel.plot_outline:
            return {"error": "该小说暂无剧情大纲"}

        po = novel.plot_outline
        return {
            "plot_outline": {
                "id": str(po.id),
                "raw_content": po.raw_content or "",
            }
        }

    async def _list_chapters(self) -> dict:
        """获取章节列表（不含内容）."""
        data = await self._ensure_novel_loaded()
        if "error" in data:
            return data

        novel = data["novel"]
        chapters = sorted(novel.chapters, key=lambda ch: ch.chapter_number)

        return {
            "chapters": [
                {
                    "chapter_number": ch.chapter_number,
                    "title": ch.title or f"第{ch.chapter_number}章",
                    "word_count": len(ch.content) if ch.content else 0,
                    "status": ch.status,
                }
                for ch in chapters
            ],
            "total_count": len(chapters),
            "total_words": sum(
                len(ch.content) if ch.content else 0 for ch in chapters
            ),
        }

    async def _get_novel_info(self) -> dict:
        """获取小说基本信息."""
        data = await self._ensure_novel_loaded()
        if "error" in data:
            return data

        novel = data["novel"]
        return {
            "novel": {
                "id": str(novel.id),
                "title": novel.title,
                "author": novel.author,
                "genre": novel.genre,
                "tags": novel.tags or [],
                "status": (novel.status.value if hasattr(novel.status, "value") else novel.status),
                "length_type": (
                    novel.length_type.value
                    if hasattr(novel.length_type, "value")
                    else novel.length_type
                ),
                "word_count": novel.word_count,
                "chapter_count": novel.chapter_count,
                "synopsis": novel.synopsis,
                "target_platform": novel.target_platform,
            }
        }
