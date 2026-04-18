"""小说信息查询工具执行器.

为AI聊天服务提供按需查询小说数据的工具，支持LLM通过Function Calling自主获取所需信息。
"""

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models.chapter import Chapter
from core.models.character import Character
from core.models.novel import Novel
from core.models.plot_outline import PlotOutline
from core.models.world_setting import WorldSetting

# 内容长度限制常量
MAX_CONTENT_LENGTH = 1000000  # 100万字

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


# 修改工具定义：供LLM调用的小说修改工具
NOVEL_MODIFICATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "modify_chapter_content",
            "description": "修改小说章节内容。当用户要求修改、编辑、重写章节内容时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "chapter_number": {
                        "type": "integer",
                        "description": "要修改的章节号（必填）",
                    },
                    "title": {
                        "type": "string",
                        "description": "新的章节标题（可选）",
                    },
                    "content": {
                        "type": "string",
                        "description": "新的章节内容（可选，与content_append二选一）",
                    },
                    "content_append": {
                        "type": "string",
                        "description": "追加到章节末尾的内容（可选，用于扩写）",
                    },
                    "content_prepend": {
                        "type": "string",
                        "description": "插入到章节开头的内容（可选，用于前插）",
                    },
                    "content_replace": {
                        "type": "object",
                        "description": "替换章节中的特定文本",
                        "properties": {
                            "old_text": {"type": "string", "description": "要替换的原文"},
                            "new_text": {"type": "string", "description": "替换后的新文本"},
                        },
                        "required": ["old_text", "new_text"],
                    },
                },
                "required": ["chapter_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_outline",
            "description": "修改剧情大纲。当用户要求修改大纲、调整剧情走向、更新主线支线时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "要修改的字段名",
                        "enum": [
                            "volumes",
                            "main_plot",
                            "main_plot_detailed",
                            "sub_plots",
                            "key_turning_points",
                            "raw_content",
                        ],
                    },
                    "value": {
                        "type": "string",
                        "description": "新的字段值（JSON字符串或纯文本）",
                    },
                    "append_to_raw": {
                        "type": "string",
                        "description": "追加到大纲原文的内容（可选）",
                    },
                },
                "required": ["field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_world_setting",
            "description": "修改世界观设定。当用户要求修改世界观、调整设定、更新修炼体系时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {
                        "type": "string",
                        "description": "要修改的字段名",
                        "enum": [
                            "world_name",
                            "world_type",
                            "power_system",
                            "geography",
                            "factions",
                            "rules",
                            "timeline",
                            "special_elements",
                            "raw_content",
                        ],
                    },
                    "value": {
                        "type": "string",
                        "description": "新的字段值（JSON字符串或纯文本）",
                    },
                    "append_to_raw": {
                        "type": "string",
                        "description": "追加到世界观原文的内容（可选）",
                    },
                },
                "required": ["field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_character",
            "description": "修改角色信息。当用户要求修改角色属性、调整人物设定时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "character_name": {
                        "type": "string",
                        "description": "角色名称（必填）",
                    },
                    "field": {
                        "type": "string",
                        "description": "要修改的字段名",
                        "enum": [
                            "name",
                            "role_type",
                            "gender",
                            "age",
                            "appearance",
                            "personality",
                            "background",
                            "goals",
                            "abilities",
                            "relationships",
                            "growth_arc",
                            "status",
                        ],
                    },
                    "value": {
                        "type": "string",
                        "description": "新的字段值（JSON字符串或纯文本）",
                    },
                },
                "required": ["character_name", "field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_character",
            "description": "新增角色。当用户要求添加新角色、创建新人物时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "角色名称（必填）",
                    },
                    "role_type": {
                        "type": "string",
                        "description": "角色类型",
                        "enum": ["protagonist", "supporting", "antagonist", "minor"],
                    },
                    "gender": {"type": "string", "description": "性别"},
                    "age": {"type": "integer", "description": "年龄"},
                    "personality": {"type": "string", "description": "性格描述"},
                    "background": {"type": "string", "description": "背景故事"},
                    "appearance": {"type": "string", "description": "外貌描述"},
                },
                "required": ["name"],
            },
        },
    },
]


# 合并所有工具（查询+修改）
NOVEL_ALL_TOOLS = NOVEL_QUERY_TOOLS + NOVEL_MODIFICATION_TOOLS


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

    def _validate_novel_id(self) -> UUID | None:
        """验证并返回有效的小说ID.

        Returns:
            UUID对象，无效时返回None
        """
        try:
            return UUID(self.novel_id)
        except ValueError:
            return None

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
            # 查询工具
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
            # 修改工具
            elif tool_name == "modify_chapter_content":
                return await self._modify_chapter_content(**arguments)
            elif tool_name == "modify_outline":
                return await self._modify_outline(**arguments)
            elif tool_name == "modify_world_setting":
                return await self._modify_world_setting(**arguments)
            elif tool_name == "modify_character":
                return await self._modify_character(**arguments)
            elif tool_name == "add_character":
                return await self._add_character(**arguments)
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

    # ==================== 修改工具实现 ====================

    async def _modify_chapter_content(
        self,
        chapter_number: int,
        title: str | None = None,
        content: str | None = None,
        content_append: str | None = None,
        content_prepend: str | None = None,
        content_replace: dict | None = None,
    ) -> dict:
        """修改章节内容.

        Args:
            chapter_number: 章节号
            title: 新标题（可选）
            content: 完全替换的新内容（可选）
            content_append: 追加到末尾的内容（可选）
            content_prepend: 插入到开头的内容（可选）
            content_replace: 替换特定文本 {old_text, new_text}（可选）

        Returns:
            修改结果
        """
        # 输入验证：检查是否有修改内容
        if not any([content, content_append, content_prepend, content_replace, title]):
            return {"success": False, "error": "未提供任何修改内容"}

        # 内容长度限制检查
        if content and len(content) > MAX_CONTENT_LENGTH:
            return {
                "success": False,
                "error": f"内容过长（{len(content)}字），超过限制{MAX_CONTENT_LENGTH}字",
            }

        # 验证小说ID
        novel_id = self._validate_novel_id()
        if not novel_id:
            return {"success": False, "error": "无效的小说ID格式"}

        try:
            # 查找章节
            query = select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number,
            )
            result = await self.db.execute(query)
            chapter = result.scalar_one_or_none()

            if not chapter:
                return {
                    "success": False,
                    "error": f"未找到第{chapter_number}章",
                }

            old_content = chapter.content or ""
            new_content = old_content
            changes = []

            # 处理不同修改方式
            if content is not None:
                # 完全替换内容
                new_content = content
                changes.append("替换全部内容")
            else:
                # 增量修改
                if content_prepend:
                    new_content = content_prepend + "\n" + new_content
                    changes.append(f"开头插入{len(content_prepend)}字")
                if content_append:
                    new_content = new_content + "\n" + content_append
                    changes.append(f"末尾追加{len(content_append)}字")
                if content_replace:
                    old_text = content_replace.get("old_text", "")
                    new_text = content_replace.get("new_text", "")
                    # 验证替换参数
                    if not old_text:
                        return {
                            "success": False,
                            "error": "替换操作缺少要替换的原文",
                        }
                    if old_text not in new_content:
                        return {
                            "success": False,
                            "error": f"未找到要替换的文本: '{old_text[:50]}...'",
                        }
                    # 记录匹配次数警告
                    match_count = new_content.count(old_text)
                    if match_count > 1:
                        logger.warning(
                            f"文本在章节中出现{match_count}次，仅替换第一个匹配"
                        )
                    new_content = new_content.replace(old_text, new_text, 1)
                    changes.append(f"替换文本: '{old_text[:20]}...' -> '{new_text[:20]}...'")

            # 更新章节
            update_values = {"content": new_content, "word_count": len(new_content)}
            if title:
                update_values["title"] = title
                changes.append(f"标题改为: {title}")

            stmt = update(Chapter).where(Chapter.id == chapter.id).values(**update_values)
            await self.db.execute(stmt)
            await self.db.commit()

            return {
                "success": True,
                "message": f"✅ 已修改第{chapter_number}章",
                "changes": changes,
                "old_word_count": len(old_content),
                "new_word_count": len(new_content),
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"修改章节内容失败: {e}")
            return {"success": False, "error": f"修改失败: {str(e)}"}
        finally:
            # 清除缓存以刷新数据
            self._novel_cache = None

    async def _modify_outline(
        self,
        field: str,
        value: str | None = None,
        append_to_raw: str | None = None,
    ) -> dict:
        """修改剧情大纲.

        Args:
            field: 要修改的字段
            value: 新值（JSON字符串或纯文本）
            append_to_raw: 追加到原文的内容

        Returns:
            修改结果
        """
        # 验证小说ID
        novel_id = self._validate_novel_id()
        if not novel_id:
            return {"success": False, "error": "无效的小说ID格式"}

        try:
            # 查找大纲
            query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
            result = await self.db.execute(query)
            outline = result.scalar_one_or_none()

            if not outline:
                return {"success": False, "error": "该小说暂无剧情大纲"}

            update_values = {}
            changes = []

            # 处理追加到原文
            if append_to_raw:
                old_raw = outline.raw_content or ""
                update_values["raw_content"] = old_raw + "\n" + append_to_raw
                changes.append("追加到大纲原文")

            # 处理字段更新
            if value:
                # 尝试解析JSON
                json_fields = [
                    "volumes",
                    "main_plot",
                    "main_plot_detailed",
                    "sub_plots",
                    "key_turning_points",
                ]

                if field == "raw_content":
                    update_values["raw_content"] = value
                    changes.append("更新大纲原文")
                elif field in json_fields:
                    try:
                        parsed_value = json.loads(value)
                        update_values[field] = parsed_value
                        changes.append(f"更新{field}（结构化数据）")
                    except json.JSONDecodeError as e:
                        # 不是有效JSON，作为纯文本存储并记录警告
                        logger.warning(f"字段 {field} JSON解析失败，将作为纯文本存储: {e}")
                        update_values[field] = value
                        changes.append(f"更新{field}（文本格式）")
                else:
                    return {"success": False, "error": f"不支持的字段: {field}"}

            if not update_values:
                return {"success": False, "error": "未提供修改内容"}

            # 执行更新
            stmt = (
                update(PlotOutline)
                .where(PlotOutline.id == outline.id)
                .values(**update_values)
            )
            await self.db.execute(stmt)
            await self.db.commit()

            return {
                "success": True,
                "message": "✅ 已更新剧情大纲",
                "changes": changes,
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"修改剧情大纲失败: {e}")
            return {"success": False, "error": f"修改失败: {str(e)}"}
        finally:
            # 清除缓存
            self._novel_cache = None

    async def _modify_world_setting(
        self,
        field: str,
        value: str | None = None,
        append_to_raw: str | None = None,
    ) -> dict:
        """修改世界观设定.

        Args:
            field: 要修改的字段
            value: 新值（JSON字符串或纯文本）
            append_to_raw: 追加到原文的内容

        Returns:
            修改结果
        """
        # 验证小说ID
        novel_id = self._validate_novel_id()
        if not novel_id:
            return {"success": False, "error": "无效的小说ID格式"}

        try:
            # 查找世界观
            query = select(WorldSetting).where(WorldSetting.novel_id == novel_id)
            result = await self.db.execute(query)
            world_setting = result.scalar_one_or_none()

            if not world_setting:
                return {"success": False, "error": "该小说暂无世界观设定"}

            update_values = {}
            changes = []

            # 处理追加到原文
            if append_to_raw:
                old_raw = world_setting.raw_content or ""
                update_values["raw_content"] = old_raw + "\n" + append_to_raw
                changes.append("追加到世界观原文")

            # 处理字段更新
            if value:
                json_fields = [
                    "power_system",
                    "geography",
                    "factions",
                    "rules",
                    "timeline",
                    "special_elements",
                ]

                if field == "raw_content":
                    update_values["raw_content"] = value
                    changes.append("更新世界观原文")
                elif field == "world_name":
                    update_values["world_name"] = value
                    changes.append(f"更新世界名称为: {value}")
                elif field == "world_type":
                    update_values["world_type"] = value
                    changes.append(f"更新世界类型为: {value}")
                elif field in json_fields:
                    try:
                        parsed_value = json.loads(value)
                        update_values[field] = parsed_value
                        changes.append(f"更新{field}（结构化数据）")
                    except json.JSONDecodeError as e:
                        # 不是有效JSON，作为纯文本存储并记录警告
                        logger.warning(f"字段 {field} JSON解析失败，将作为纯文本存储: {e}")
                        update_values[field] = {"content": value}
                        changes.append(f"更新{field}（文本格式）")
                else:
                    return {"success": False, "error": f"不支持的字段: {field}"}

            if not update_values:
                return {"success": False, "error": "未提供修改内容"}

            # 执行更新
            stmt = (
                update(WorldSetting)
                .where(WorldSetting.id == world_setting.id)
                .values(**update_values)
            )
            await self.db.execute(stmt)
            await self.db.commit()

            return {
                "success": True,
                "message": "✅ 已更新世界观设定",
                "changes": changes,
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"修改世界观设定失败: {e}")
            return {"success": False, "error": f"修改失败: {str(e)}"}
        finally:
            # 清除缓存
            self._novel_cache = None

    async def _modify_character(
        self,
        character_name: str,
        field: str,
        value: str | None = None,
    ) -> dict:
        """修改角色信息.

        Args:
            character_name: 角色名称
            field: 要修改的字段
            value: 新值

        Returns:
            修改结果
        """
        # 验证小说ID
        novel_id = self._validate_novel_id()
        if not novel_id:
            return {"success": False, "error": "无效的小说ID格式"}

        if not value:
            return {"success": False, "error": "未提供新值"}

        try:
            # 查找角色
            query = select(Character).where(
                Character.novel_id == novel_id,
                Character.name == character_name,
            )
            result = await self.db.execute(query)
            character = result.scalar_one_or_none()

            if not character:
                return {
                    "success": False,
                    "error": f"未找到角色: {character_name}",
                }

            # 处理不同字段类型
            json_fields = ["abilities", "relationships", "growth_arc"]
            int_fields = ["age"]

            update_values = {}

            if field in json_fields:
                try:
                    parsed_value = json.loads(value)
                    update_values[field] = parsed_value
                except json.JSONDecodeError as e:
                    logger.warning(f"字段 {field} JSON解析失败，将作为纯文本存储: {e}")
                    update_values[field] = {"content": value}
            elif field in int_fields:
                try:
                    update_values[field] = int(value)
                except ValueError:
                    return {"success": False, "error": f"{field}必须是整数"}
            else:
                update_values[field] = value

            # 执行更新
            stmt = (
                update(Character)
                .where(Character.id == character.id)
                .values(**update_values)
            )
            await self.db.execute(stmt)
            await self.db.commit()

            return {
                "success": True,
                "message": f"✅ 已更新角色「{character_name}」的{field}",
                "field": field,
                "new_value": value,
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"修改角色信息失败: {e}")
            return {"success": False, "error": f"修改失败: {str(e)}"}
        finally:
            # 清除缓存
            self._novel_cache = None

    async def _add_character(
        self,
        name: str,
        role_type: str = "minor",
        gender: str | None = None,
        age: int | None = None,
        personality: str | None = None,
        background: str | None = None,
        appearance: str | None = None,
    ) -> dict:
        """新增角色.

        Args:
            name: 角色名称
            role_type: 角色类型
            gender: 性别
            age: 年龄
            personality: 性格
            background: 背景
            appearance: 外貌

        Returns:
            创建结果
        """
        import uuid

        # 验证小说ID
        novel_id = self._validate_novel_id()
        if not novel_id:
            return {"success": False, "error": "无效的小说ID格式"}

        try:
            # 检查角色是否已存在
            query = select(Character).where(
                Character.novel_id == novel_id,
                Character.name == name,
            )
            result = await self.db.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                return {
                    "success": False,
                    "error": f"角色「{name}」已存在",
                    "existing_character": {
                        "id": str(existing.id),
                        "role_type": existing.role_type,
                    },
                }

            # 创建新角色
            new_character = Character(
                id=uuid.uuid4(),
                novel_id=novel_id,
                name=name,
                role_type=role_type,
                gender=gender,
                age=age,
                personality=personality,
                background=background,
                appearance=appearance,
            )

            self.db.add(new_character)
            await self.db.commit()

            return {
                "success": True,
                "message": f"✅ 已创建角色「{name}」",
                "character": {
                    "id": str(new_character.id),
                    "name": name,
                    "role_type": role_type,
                },
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建角色失败: {e}")
            return {"success": False, "error": f"创建失败: {str(e)}"}
        finally:
            # 清除缓存
            self._novel_cache = None
