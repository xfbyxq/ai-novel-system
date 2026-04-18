"""AI 对话服务 - 提供智能辅助能力."""

import json
import logging
import re
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.graph.neo4j_client import Neo4jClient
from llm.qwen_client import QwenClient

from .agentmesh_memory_adapter import NovelMemoryAdapter
from .graph_query_service import GraphQueryService
from .graph_sync_service import GraphSyncService
from .memory_service import get_novel_memory_service
from .novel_tool_executor import NOVEL_ALL_TOOLS, NovelToolExecutor
from .revision_understanding_service import RevisionUnderstandingService

logger = logging.getLogger(__name__)


# 结构化修订建议类型
class RevisionSuggestion:
    """结构化的修订建议."""

    def __init__(
        self,
        suggestion_type: str,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        field: Optional[str] = None,
        original_value: Optional[str] = None,
        suggested_value: Optional[str] = None,
        description: str = "",
        confidence: float = 0.8,
    ):
        """初始化方法."""
        self.suggestion_type = suggestion_type  # world_setting, character, outline, chapter
        self.target_id = target_id  # 目标对象ID（如角色ID、章节ID）
        self.target_name = target_name  # 目标对象名称（如角色名、章节标题）
        self.field = field  # 要修改的字段
        self.original_value = original_value  # 原始值
        self.suggested_value = suggested_value  # 建议的新值
        self.description = description  # 建议描述
        self.confidence = confidence  # 置信度

    def to_dict(self) -> dict:
        return {
            "type": self.suggestion_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "field": self.field,
            "original_value": self.original_value,
            "suggested_value": self.suggested_value,
            "description": self.description,
            "confidence": self.confidence,
        }


SCENE_NOVEL_CREATION = "novel_creation"
SCENE_CRAWLER_TASK = "crawler_task"
SCENE_NOVEL_REVISION = "novel_revision"
SCENE_NOVEL_ANALYSIS = "novel_analysis"
SCENE_CHAPTER_ASSISTANT = "chapter_assistant"

NOVEL_GENRES = [
    "玄幻",
    "都市",
    "仙侠",
    "历史",
    "军事",
    "游戏",
    "科幻",
    "悬疑",
    "都市",
    "轻小说",
]
CRAWLER_TYPES = ["ranking", "trending_tags", "book_metadata", "genre_list"]
RANKING_TYPES = ["yuepiao", "hotsales", "readIndex", "recom", "collect"]

# Intent classification tools for OpenAI Function Calling
INTENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "classify_intent",
            "description": "Classifies the user's intent from a novel-related message and extracts relevant entities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "primary_intent": {
                        "type": "string",
                        "enum": [
                            "world_creation",
                            "world_revision",
                            "character_creation",
                            "character_revision",
                            "plot_creation",
                            "plot_revision",
                            "chapter_revision",
                            "analysis",
                            "general",
                        ],
                        "description": "The primary intent of the user's message",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score for the classification (0-1)",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of why this intent was selected",
                    },
                    "entities": {
                        "type": "object",
                        "properties": {
                            "mentioned_characters": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of character names mentioned in the message",
                            },
                            "mentioned_chapters": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "Chapter numbers mentioned in the message",
                            },
                            "genre": {
                                "type": "string",
                                "description": "Genre mentioned or inferred from the message",
                            },
                        },
                        "description": "Entities extracted from the message",
                    },
                },
                "required": ["primary_intent", "confidence", "reasoning", "entities"],
            },
        },
    }
]

# System prompt for intent classification
INTENT_CLASSIFICATION_PROMPT = """You are an expert at classifying user intentions in a novel writing and editing assistant.

Your task is to analyze the user's message and classify their primary intent.

Intent Types:
- world_creation: Creating new world settings, magic systems, geography, factions
- world_revision: Modifying existing world settings
- character_creation: Creating new characters
- character_revision: Modifying existing characters
- plot_creation: Creating new plot outlines or storylines
- plot_revision: Modifying existing plot/structure
- chapter_revision: Revising specific chapter content
- analysis: Analyzing novel structure, market, strengths/weaknesses
- general: General questions, greetings, or unclear intents

When analyzing:
1. Consider the context (scene) provided
2. Look for keywords and semantic meaning
3. Extract any mentioned characters, chapters, or genre preferences
4. Provide a confidence score based on how certain you are

Be precise and conservative with confidence - only give high scores when intent is clearly expressed."""

SYSTEM_PROMPTS = {
    SCENE_NOVEL_CREATION: """你是一位专业的小说创作顾问，专门帮助作者规划小说世界。你需要根据用户的需求提供创意建议，包括但不限于：.

1. **世界观设定**：修炼体系、地理环境、势力划分、规则设定
2. **角色设定**：主角/配角的性格、背景、能力、成长路线
3. **情节大纲**：主线剧情、支线故事、关键转折点、高潮设计
4. **类型特色**：根据用户选择的类型（玄幻、都市、仙侠等）提供该类型的经典元素

请用中文回复，语气专业但亲切幽默。可以主动询问用户更多细节以便给出更好的建议。""",
    SCENE_CRAWLER_TASK: """你是一位网络文学数据分析师，专门帮助用户分析市场趋势和制定爬虫策略。你需要根据用户的需求提供专业建议，包括但不限于：.

1. **平台分析**：起点、纵横、番茄等主流平台的特点
2. **数据维度**：排行榜类型（月票榜、畅销榜等）、分类筛选、标签分析
3. **URL爬取策略**：规律、请求频率、数据字段选择
4. **市场洞察**：热门类型分析、读者偏好趋势、竞用中文回复，专业品分析

请且务实。可以主动询问用户想了解哪方面的数据。""",
    SCENE_NOVEL_REVISION: """你是一位专业的小说编辑助手，专门帮助作者修订和完善小说内容。

**重要**：你可以使用以下工具获取小说信息（按需调用，不要一次性获取所有数据）：
- get_novel_info: 获取小说基本信息
- list_chapters: 获取章节列表（不含内容）
- get_chapter_content: 获取指定章节内容
- get_character_info: 获取角色信息
- get_world_setting: 获取世界观设定
- get_outline: 获取剧情大纲

**工作原则**：
1. 根据用户问题，调用必要的工具获取所需信息
2. 基于获取的信息，直接生成具体的修订内容
3. 生成的内容应该可以直接使用

请用中文回复。""",
    SCENE_NOVEL_ANALYSIS: """你是一位专业的小说分析师，专门帮助作者分析小说的整体情况和潜力。

**重要**：你可以使用以下工具获取小说信息：
- get_novel_info: 获取小说基本信息
- list_chapters: 获取章节列表
- get_chapter_content: 获取指定章节内容
- get_character_info: 获取角色信息
- get_world_setting: 获取世界观设定
- get_outline: 获取剧情大纲

**工作原则**：
1. 根据分析需要，调用工具获取相关信息
2. 提供客观、全面的分析
3. 给出有针对性的改进建议

请用中文回复。""",
    SCENE_CHAPTER_ASSISTANT: """你是一位专业的章节编辑助手，专门帮助作者编辑和改进章节内容。

**重要**：你可以使用以下工具获取小说信息并执行修改操作：
- get_character_info: 获取角色详细信息，确保角色描写一致性
- get_world_setting: 获取世界观设定，保持设定一致
- get_outline: 获取剧情大纲，了解情节走向
- modify_chapter_content: 修改章节内容（替换/追加/插入）

## 你的能力

### 1. 章节分析维度
- 情节逻辑连贯性：检查事件发展是否合理
- 角色行为一致性：验证角色行为是否符合人物设定
- 描写生动性：评估环境、动作、心理描写的效果
- 节奏控制：分析情节推进速度是否恰当
- 对话自然度：检查对话是否符合角色性格

### 2. 修改操作指南
当用户要求修改章节时，使用 `modify_chapter_content` 工具：
- **替换内容**：使用 `content_replace` 参数，指定 `old_text` 和 `new_text`
- **追加内容**：使用 `content_append` 参数，在章节末尾添加内容
- **插入开头**：使用 `content_prepend` 参数，在章节开头插入内容
- **完全替换**：使用 `content` 参数，替换整个章节内容

### 3. 工作流程
1. 首先阅读并理解当前章节内容（已包含在上下文中）
2. 如需了解角色或设定，调用相应工具获取信息
3. 分析问题并提供修改建议
4. 如用户确认修改，调用 `modify_chapter_content` 执行修改

## 工作原则
1. 保持与小说整体风格一致
2. 尊重角色性格设定，确保行为合理
3. 注意与前后章节的情节连贯
4. 执行修改前向用户确认（重大修改）
5. 提供具体、可操作的修改建议

请用中文回复。""",
}

WELCOME_MESSAGES = {
    SCENE_NOVEL_CREATION: "你好！我是小说创作AI助手。你可以告诉我你想写什么类型的小说，或者有什么创意想法，我来帮你完善世界观、角色和情节设定。",
    SCENE_CRAWLER_TASK: "你好！我是爬虫策略AI助手。你可以告诉我你想爬取什么数据，或者想了解哪些市场趋势，我来帮你分析并制定合适的爬取方案。",
    SCENE_NOVEL_REVISION: "你好！我是小说修订AI助手。告诉我你想修订什么内容，比如「优化下小说简介」、「丰富世界观设定」、「完善主角背景」等，我会直接生成优化后的内容。",
    SCENE_NOVEL_ANALYSIS: "你好！我是小说分析AI助手。我可以帮你全面分析小说的整体情况，包括结构、元素、市场定位等方面，并提供有针对性的改进建议。请选择你想分析的小说。",
    # SCENE_CHAPTER_ASSISTANT 的欢迎消息在 create_session 中动态生成
}


class ChatMessage:
    """对话消息."""

    def __init__(self, role: str, content: str):
        """初始化方法."""
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class ChatSession:
    """对话会话."""

    def __init__(
        self,
        session_id: str,
        scene: str,
        context: Optional[dict] = None,
        novel_id: Optional[str] = None,
        title: Optional[str] = None,
    ):
        """初始化方法."""
        self.session_id = session_id
        self.scene = scene
        self.context = context or {}
        self.novel_id = novel_id  # 关联的小说ID
        self.title = title  # 会话标题
        self.messages: list[ChatMessage] = []
        self.dialogue_state = "active"  # active, waiting_for_clarification, completed
        self.pending_questions = []
        self.conversation_history = []
        self.last_user_intent = None
        self.follow_up_questions = []

        welcome = WELCOME_MESSAGES.get(scene, "你好！有什么我可以帮助你的？")
        self.messages.append(ChatMessage("assistant", welcome))

    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage("user", content))
        self.conversation_history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(ChatMessage("assistant", content))
        self.conversation_history.append({"role": "assistant", "content": content})

    def get_messages_for_api(self) -> list[dict]:
        result = []
        for msg in self.messages:
            result.append(msg.to_dict())
        return result

    def get_conversation_history(self, limit: int = 10) -> list[dict]:
        """获取最近的对话历史."""
        return self.conversation_history[-limit:]

    def set_dialogue_state(self, state: str) -> None:
        """设置对话状态."""
        self.dialogue_state = state

    def add_pending_question(self, question: str) -> None:
        """添加待处理的问题."""
        self.pending_questions.append(question)

    def get_pending_question(self) -> Optional[str]:
        """获取待处理的问题."""
        if self.pending_questions:
            return self.pending_questions.pop(0)
        return None

    def set_last_user_intent(self, intent: str) -> None:
        """设置用户的最后意图."""
        self.last_user_intent = intent

    def add_follow_up_question(self, question: str) -> None:
        """添加后续问题."""
        self.follow_up_questions.append(question)

    def get_follow_up_questions(self) -> list[str]:
        """获取后续问题."""
        return self.follow_up_questions


class AiChatService:
    """AI 对话服务."""

    def __init__(self, db: AsyncSession):
        """初始化方法."""
        self.db = db
        self.client = QwenClient()
        self.sessions: dict[str, ChatSession] = {}
        self.memory_service = get_novel_memory_service()
        # 初始化持久化记忆适配器
        self.persistent_memory = NovelMemoryAdapter()
        # 初始化修订理解服务
        self.revision_service = RevisionUnderstandingService(db=db, llm=self.client)
        # 初始化图库服务（延迟初始化，避免 Neo4j 未配置时报错）
        try:
            from backend.config import settings

            self.neo4j_client = Neo4jClient(
                uri=settings.NEO4J_URI, user=settings.NEO4J_USER, password=settings.NEO4J_PASSWORD
            )
            self.graph_query = GraphQueryService(self.neo4j_client)
            self.graph_sync = GraphSyncService(self.neo4j_client, db)
            self.gallery_enabled = True
        except Exception as e:
            logger.warning(f"Neo4j 未配置，图库功能不可用：{e}")
            self.neo4j_client = None
            self.graph_query = None
            self.graph_sync = None
            self.gallery_enabled = False

    def _get_system_prompt(self, scene: str) -> str:
        return SYSTEM_PROMPTS.get(scene, "你是一位AI助手，请帮助用户解决问题。")

    def _get_welcome_message(self, scene: str) -> str:
        return WELCOME_MESSAGES.get(scene, "你好！有什么我可以帮助你的？")

    # ===== 图库查询方法 =====

    async def query_character_network(self, novel_id: UUID) -> Dict:
        """查询角色关系网络.

        Args:
            novel_id: 小说 ID

        Returns:
            角色关系网络数据
        """
        if not self.gallery_enabled:
            return {"error": "图库功能未启用，请先配置 Neo4j"}

        try:
            return await self.graph_query.get_character_network(novel_id)
        except Exception as e:
            logger.error(f"查询角色关系网络失败：{e}")
            return {"error": f"查询失败：{str(e)}"}

    async def query_world_setting_map(self, novel_id: UUID) -> Dict:
        """查询世界观设定地图.

        Args:
            novel_id: 小说 ID

        Returns:
            世界观设定地图数据
        """
        if not self.gallery_enabled:
            return {"error": "图库功能未启用，请先配置 Neo4j"}

        try:
            return await self.graph_query.get_world_setting_map(novel_id)
        except Exception as e:
            logger.error(f"查询世界观设定地图失败：{e}")
            return {"error": f"查询失败：{str(e)}"}

    async def query_plot_timeline(self, novel_id: UUID) -> Dict:
        """查询情节时间线.

        Args:
            novel_id: 小说 ID

        Returns:
            情节时间线数据
        """
        if not self.gallery_enabled:
            return {"error": "图库功能未启用，请先配置 Neo4j"}

        try:
            return await self.graph_query.get_plot_timeline(novel_id)
        except Exception as e:
            logger.error(f"查询情节时间线失败：{e}")
            return {"error": f"查询失败：{str(e)}"}

    async def query_gallery(self, novel_id: UUID, query_type: str) -> Dict:
        """查询图库数据.

        Args:
            novel_id: 小说 ID
            query_type: 查询类型 (character_network, world_map, plot_timeline)

        Returns:
            图库数据
        """
        if not self.gallery_enabled:
            return {"error": "图库功能未启用，请先配置 Neo4j"}

        if query_type == "character_network":
            return await self.query_character_network(novel_id)
        elif query_type == "world_map":
            return await self.query_world_setting_map(novel_id)
        elif query_type == "plot_timeline":
            return await self.query_plot_timeline(novel_id)
        else:
            return {"error": f"未知的查询类型：{query_type}"}

    # ===== 图库同步方法 =====

    async def sync_chapter_to_gallery(
        self,
        novel_id: UUID,
        chapter_number: int,
        chapter_content: str,
    ) -> Dict:
        """同步章节到图库.

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            chapter_content: 章节内容

        Returns:
            同步结果
        """
        if not self.gallery_enabled:
            return {"success": False, "error": "图库功能未启用，请先配置 Neo4j"}

        try:
            await self.graph_sync.sync_chapter_incremental(
                novel_id=novel_id, chapter_number=chapter_number, chapter_content=chapter_content
            )
            return {"success": True, "message": "同步成功"}
        except Exception as e:
            logger.error(f"同步章节到图库失败：{e}")
            return {"success": False, "error": f"同步失败：{str(e)}"}

    async def sync_novel_full_to_gallery(self, novel_id: UUID) -> Dict:
        """全量同步小说到图库.

        Args:
            novel_id: 小说 ID

        Returns:
            同步结果
        """
        if not self.gallery_enabled:
            return {"success": False, "error": "图库功能未启用，请先配置 Neo4j"}

        try:
            await self.graph_sync.sync_novel_full(novel_id)
            return {"success": True, "message": "全量同步成功"}
        except Exception as e:
            logger.error(f"全量同步小说到图库失败：{e}")
            return {"success": False, "error": f"同步失败：{str(e)}"}

    async def get_novel_info(
        self,
        novel_id: str,
        chapter_start: int = 1,
        chapter_end: int = 10,
        force_db: bool = True,  # 默认强制从数据库获取，确保内容是最新的完整内容
    ) -> dict:
        """获取小说的完整信息，包括世界观、角色、大纲和章节.

        Args:
            novel_id: 小说ID
            chapter_start: 开始章节（默认1）
            chapter_end: 结束章节（默认10）
            force_db: 强制从数据库加载，忽略记忆缓存（默认True）

        Returns:
            小说信息字典，包含一个额外的'has_changes'字段表示内容是否有变化
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from core.models.novel import Novel

        try:
            # 验证 novel_id 是否为有效的 UUID
            UUID(novel_id)
        except ValueError:
            logger.error(f"无效的小说 ID 格式: {novel_id}")
            return {"error": "无效的小说 ID 格式"}

        # 首先尝试从记忆服务获取（除非强制使用数据库）
        # 注意：默认强制使用数据库，因为记忆服务可能缓存了旧的截断数据
        memory_data = None if force_db else self.memory_service.get_novel_memory(novel_id)
        if memory_data:
            logger.info(f"从记忆服务获取小说信息: {novel_id}")
            # 转换为预期的格式
            novel_info = {
                "id": memory_data["base"]["id"],
                "title": memory_data["base"]["title"],
                "author": memory_data["base"].get("author"),
                "genre": memory_data["base"]["genre"],
                "tags": memory_data["base"].get("tags", []),
                "status": memory_data["base"]["status"],
                "length_type": memory_data["base"].get("length_type"),
                "word_count": memory_data["base"].get("word_count"),
                "chapter_count": memory_data["base"].get("chapter_count"),
                "cover_url": memory_data["base"].get("cover_url"),
                "synopsis": memory_data["base"]["synopsis"],
                "target_platform": memory_data["base"].get("target_platform"),
                "world_setting": memory_data["details"]["world_setting"],
                "characters": memory_data["details"]["characters"],
                "plot_outline": memory_data["details"]["plot_outline"],
                "chapters": memory_data["chapters"],
                "metadata": memory_data["base"].get("metadata", {}),
                "created_at": memory_data["base"].get("created_at"),
                "updated_at": memory_data["base"].get("updated_at"),
                "has_changes": False,  # 从记忆服务获取，视为无变化
            }
            return novel_info

        logger.info(f"从数据库获取小说信息: {novel_id}")

        try:
            # 使用类实例的数据库会话
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
                logger.warning(f"小说不存在: {novel_id}")
                return {"error": "小说不存在"}

            # 构建小说信息字典
            novel_info = {
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
                "cover_url": novel.cover_url,
                "synopsis": novel.synopsis,
                "target_platform": novel.target_platform,
                "world_setting": None,
                "characters": [],
                "plot_outline": None,
                "chapters": [],
                "metadata": novel.metadata_ or {},
                "created_at": (novel.created_at.isoformat() if novel.created_at else None),
                "updated_at": (novel.updated_at.isoformat() if novel.updated_at else None),
            }

            # 添加世界观信息
            if novel.world_setting:
                # 保持raw_content为字符串，以便在提示词中正确使用
                novel_info["world_setting"] = {
                    "id": str(novel.world_setting.id),
                    "setting_type": novel.world_setting.world_type,
                    "content": novel.world_setting.raw_content or "",
                }

            # 添加角色信息（限制最多20个角色）
            for character in novel.characters[:20]:
                novel_info["characters"].append(
                    {
                        "id": str(character.id),
                        "name": character.name,
                        "role_type": character.role_type,
                        "description": character.appearance or character.personality or "",
                        "personality": character.personality,
                        "background": character.background,
                    }
                )

            # 添加大纲信息
            if novel.plot_outline:
                novel_info["plot_outline"] = {
                    "id": str(novel.plot_outline.id),
                    "content": novel.plot_outline.raw_content or "",
                }

            # 添加章节信息（按需加载）
            # end=0 表示只加载元信息，不加载内容
            # end>0 时加载指定范围内的章节内容
            load_content = chapter_end >= chapter_start
            for chapter in novel.chapters:
                if load_content and (chapter_start <= chapter.chapter_number <= chapter_end):
                    # 加载完整章节内容
                    chapter_data = {
                        "id": str(chapter.id),
                        "chapter_number": chapter.chapter_number,
                        "title": chapter.title,
                        "word_count": len(chapter.content) if chapter.content else 0,
                        "content": chapter.content or "",
                    }
                    novel_info["chapters"].append(chapter_data)
                elif not load_content:
                    # 只加载元信息，不加载内容
                    chapter_data = {
                        "id": str(chapter.id),
                        "chapter_number": chapter.chapter_number,
                        "title": chapter.title,
                        "word_count": len(chapter.content) if chapter.content else 0,
                        # 不包含 content 字段
                    }
                    novel_info["chapters"].append(chapter_data)

            # 存储到记忆服务并检测变化
            has_changes = self.memory_service.set_novel_memory(novel_id, novel_info)

            # 添加变化状态到返回结果
            novel_info["has_changes"] = has_changes

            if has_changes:
                logger.info(f"成功获取小说信息并检测到变化: {novel.title}, 版本已更新")
            else:
                logger.info(f"成功获取小说信息: {novel.title}, 内容无变化")

            return novel_info
        except Exception as e:
            logger.error(f"获取小说信息失败: {e}")
            return {"error": "获取小说信息失败，请稍后重试"}

    async def _get_chapter_by_number(self, novel_id: str, chapter_number: int) -> dict:
        """获取指定章节的内容.

        Args:
            novel_id: 小说ID
            chapter_number: 章节号

        Returns:
            章节信息字典
        """
        from sqlalchemy import select

        from core.models.chapter import Chapter

        try:
            novel_uuid = UUID(novel_id)
        except ValueError:
            return {"error": "无效的小说 ID 格式"}

        try:
            query = select(Chapter).where(
                Chapter.novel_id == novel_uuid,
                Chapter.chapter_number == chapter_number,
            )
            result = await self.db.execute(query)
            chapter = result.scalar_one_or_none()

            if not chapter:
                return {"error": f"章节不存在: 第{chapter_number}章"}

            return {
                "chapter_number": chapter.chapter_number,
                "title": chapter.title or f"第{chapter.chapter_number}章",
                "content": chapter.content or "",
                "word_count": len(chapter.content) if chapter.content else 0,
                "status": chapter.status.value
                if hasattr(chapter.status, "value")
                else chapter.status,
            }
        except Exception as e:
            logger.error(f"获取章节内容失败: {e}")
            return {"error": f"获取章节内容失败: {str(e)}"}

    async def generate_smart_chapter_summary(
        self,
        novel_id: str,
        chapter_numbers: List[int],
        force_regenerate: bool = False,
    ) -> Dict[str, Any]:
        """智能章节摘要生成 - 使用LLM提炼章节关键点.

        读取完整章节内容，使用AI提炼关键信息，避免固定截断导致信息丢失。

        Args:
            novel_id: 小说ID
            chapter_numbers: 要生成摘要的章节号列表
            force_regenerate: 是否强制重新生成（忽略已有摘要）

        Returns:
            包含所有章节摘要的结果字典
        """
        from sqlalchemy import select

        from core.models.novel import Novel

        try:
            UUID(novel_id)
        except ValueError:
            logger.error(f"无效的小说 ID 格式: {novel_id}")
            return {"error": "无效的小说 ID 格式"}

        results = {
            "novel_id": novel_id,
            "summaries": [],
            "total_chapters_requested": len(chapter_numbers),
            "generated_count": 0,
            "cached_count": 0,
        }

        # 验证小说存在
        novel_result = await self.db.execute(select(Novel).where(Novel.id == novel_id))
        novel = novel_result.scalar_one_or_none()
        if not novel:
            return {"error": "小说不存在"}

        results["novel_title"] = novel.title

        # 获取所有请求的章节
        from core.models.chapter import Chapter

        chapters_query = (
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .where(Chapter.chapter_number.in_(chapter_numbers))
            .order_by(Chapter.chapter_number)
        )
        chapters_result = await self.db.execute(chapters_query)
        chapters = chapters_result.scalars().all()

        for chapter in chapters:
            chapter_num = chapter.chapter_number

            # 检查是否已有摘要（除非强制重新生成）
            existing_summary = None
            if not force_regenerate:
                existing_summary = self.persistent_memory.storage.get_chapter_summary(
                    novel_id, chapter_num
                )

            if existing_summary and not force_regenerate:
                # 使用已有摘要
                results["summaries"].append(
                    {
                        "chapter_number": chapter_num,
                        "title": chapter.title,
                        "summary": existing_summary,
                        "source": "cached",
                    }
                )
                results["cached_count"] += 1
                logger.info(f"使用缓存的章节摘要: 第{chapter_num}章")
            else:
                # 使用AI生成新摘要
                summary = await self._extract_chapter_key_points(
                    chapter.content or "",
                    chapter.title,
                    chapter_num,
                    novel.genre,
                )
                results["summaries"].append(
                    {
                        "chapter_number": chapter_num,
                        "title": chapter.title,
                        "summary": summary,
                        "source": "generated",
                    }
                )
                results["generated_count"] += 1

                # 保存摘要到持久化记忆
                self.persistent_memory.storage.save_chapter_summary(
                    novel_id,
                    chapter_num,
                    summary,
                    self.persistent_memory.storage._compute_hash(chapter.content),
                )
                logger.info(f"生成并保存章节摘要: 第{chapter_num}章")

        return results

    async def _extract_chapter_key_points(
        self,
        content: str,
        title: str,
        chapter_number: int,
        genre: str = "",
    ) -> Dict[str, Any]:
        """使用LLM从章节内容中提炼关键点.

        Args:
            content: 章节完整内容
            title: 章节标题
            chapter_number: 章节号
            genre: 小说类型（用于类型特定的分析）

        Returns:
            结构化的章节摘要
        """
        if not content or len(content.strip()) < 100:
            return {
                "key_events": [],
                "plot_summary": "章节内容过短或为空",
                "character_interactions": [],
                "emotional_arc": "",
                "foreshadowing": [],
                "ending_state": "",
                "word_count": len(content) if content else 0,
            }

        # 构建AI分析提示词
        prompt = f"""请分析以下小说章节内容，提炼关键信息。章节标题：{title}（第{chapter_number}章）
小说类型：{genre or "未知"}

章节内容：
{content[:8000]}{"...(内容过长，仅显示前8000字)" if len(content) > 8000 else ""}

请以JSON格式输出以下信息：
1. key_events: 关键事件列表（3-5个重要事件，简短描述）
2. plot_summary: 情节摘要（100字以内概括本章主要情节）
3. character_interactions: 人物互动列表（主要角色的对话、冲突、合作等）
4. emotional_arc: 情感走向（本章的情感基调变化）
5. foreshadowing: 伏笔/暗示列表（为后续情节埋下的线索）
6. ending_state: 结尾状态（本章结尾时的人物处境或悬念）

只输出JSON，不要其他内容。"""

        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一位专业的小说分析助手，擅长提炼章节关键信息。请以结构化的方式输出分析结果。",
                temperature=0.3,
            )

            # 解析AI响应
            content_response = response.get("content", "{}")
            # 清理可能的markdown格式
            content_response = content_response.strip()
            if content_response.startswith("```json"):
                content_response = content_response[7:]
            if content_response.startswith("```"):
                content_response = content_response[3:]
            if content_response.endswith("```"):
                content_response = content_response[:-3]
            content_response = content_response.strip()

            summary = json.loads(content_response)

            # 确保所有字段存在
            summary.setdefault("key_events", [])
            summary.setdefault("plot_summary", "")
            summary.setdefault("character_interactions", [])
            summary.setdefault("emotional_arc", "")
            summary.setdefault("foreshadowing", [])
            summary.setdefault("ending_state", "")
            summary["word_count"] = len(content)
            summary["chapter_number"] = chapter_number
            summary["title"] = title

            return summary

        except json.JSONDecodeError as e:
            logger.error(f"解析章节摘要JSON失败: {e}")
            # 返回基础摘要
            return {
                "key_events": [],
                "plot_summary": content[:200] + "..." if len(content) > 200 else content,
                "character_interactions": [],
                "emotional_arc": "",
                "foreshadowing": [],
                "ending_state": content[-100:] if len(content) > 100 else content,
                "word_count": len(content),
                "chapter_number": chapter_number,
                "title": title,
            }
        except Exception as e:
            logger.error(f"生成章节摘要失败: {e}")
            return {
                "key_events": [],
                "plot_summary": "",
                "character_interactions": [],
                "emotional_arc": "",
                "foreshadowing": [],
                "ending_state": "",
                "word_count": len(content),
                "chapter_number": chapter_number,
                "title": title,
                "error": str(e),
            }

    async def get_novel_chapters_summary(
        self,
        novel_id: str,
        chapter_start: int = 1,
        chapter_end: int = 10,
        use_smart_summary: bool = True,
    ) -> Dict[str, Any]:
        """获取小说章节摘要（支持智能摘要模式）.

        Args:
            novel_id: 小说ID
            chapter_start: 开始章节号
            chapter_end: 结束章节号
            use_smart_summary: 是否使用智能摘要（LLM提炼），否则使用简单截断

        Returns:
            章节摘要结果
        """
        chapter_numbers = list(range(chapter_start, chapter_end + 1))

        if use_smart_summary:
            return await self.generate_smart_chapter_summary(novel_id, chapter_numbers)
        else:
            # 使用原有的截断方式（已优化为2000字）
            novel_info = await self.get_novel_info(novel_id, chapter_start, chapter_end)
            return {
                "novel_id": novel_id,
                "novel_title": novel_info.get("title"),
                "summaries": [
                    {
                        "chapter_number": ch.get("chapter_number"),
                        "title": ch.get("title"),
                        "summary": {
                            "plot_summary": ch.get("content", ""),
                            "word_count": len(ch.get("content", "")),
                        },
                        "source": "truncated",
                    }
                    for ch in novel_info.get("chapters", [])
                ],
                "total_chapters_requested": len(chapter_numbers),
                "generated_count": 0,
                "cached_count": 0,
            }

    async def save_session(self, session: ChatSession) -> None:
        """保存会话到数据库."""
        from sqlalchemy import insert

        from core.database import async_session_factory
        from core.models.ai_chat_session import AIChatMessage, AIChatSession

        async with async_session_factory() as db:
            try:
                # 保存会话信息，包含 novel_id 和 title
                session_data = {
                    "session_id": session.session_id,
                    "scene": session.scene,
                    "context": session.context,
                    "novel_id": session.novel_id,
                    "title": session.title,
                }

                # 检查会话是否已存在
                from sqlalchemy import select

                existing = await db.execute(
                    select(AIChatSession).where(AIChatSession.session_id == session.session_id)
                )
                if existing.scalar_one_or_none():
                    # 更新现有会话
                    from sqlalchemy import update

                    await db.execute(
                        update(AIChatSession)
                        .where(AIChatSession.session_id == session.session_id)
                        .values(**session_data)
                    )
                else:
                    # 插入新会话
                    await db.execute(insert(AIChatSession).values(**session_data))

                # 保存消息 - 获取已存在的消息数量，只保存新消息
                existing_msgs = await db.execute(
                    select(AIChatMessage)
                    .where(AIChatMessage.session_id == session.session_id)
                    .order_by(AIChatMessage.created_at)
                )
                existing_msg_list = existing_msgs.scalars().all()
                existing_count = len(existing_msg_list)

                # 只保存新消息（跳过已存在的消息）
                for msg in session.messages[existing_count:]:
                    msg_data = {
                        "session_id": session.session_id,
                        "role": msg.role,
                        "content": msg.content,
                    }
                    await db.execute(insert(AIChatMessage).values(**msg_data))

                await db.commit()
            except Exception as e:
                logger.error(f"保存会话失败: {e}")
                await db.rollback()

    async def load_session(self, session_id: str) -> Optional[ChatSession]:
        """从数据库加载会话."""
        from sqlalchemy import select

        from core.database import async_session_factory
        from core.models.ai_chat_session import AIChatMessage, AIChatSession

        async with async_session_factory() as db:
            try:
                # 加载会话信息
                session_result = await db.execute(
                    select(AIChatSession).where(AIChatSession.session_id == session_id)
                )
                session_data = session_result.scalar_one_or_none()

                if not session_data:
                    return None

                # 创建会话对象，包含 novel_id 和 title
                session = ChatSession(
                    session_data.session_id,
                    session_data.scene,
                    session_data.context,
                    novel_id=(str(session_data.novel_id) if session_data.novel_id else None),
                    title=session_data.title,
                )

                # 清空构造函数自动添加的欢迎消息，避免重复
                session.messages.clear()
                session.conversation_history.clear()

                # 加载消息
                messages_result = await db.execute(
                    select(AIChatMessage)
                    .where(AIChatMessage.session_id == session_id)
                    .order_by(AIChatMessage.created_at)
                )
                messages = messages_result.scalars().all()

                for msg in messages:
                    if msg.role == "user":
                        session.add_user_message(msg.content)
                    else:
                        session.add_assistant_message(msg.content)

                return session
            except Exception as e:
                logger.error(f"加载会话失败: {e}")
                return None

    async def get_sessions(
        self, scene: Optional[str] = None, novel_id: Optional[str] = None
    ) -> list[dict]:
        """获取会话列表.

        Args:
            scene: 场景过滤
            novel_id: 小说ID过滤，用于按小说隔离会话
        """
        from sqlalchemy import select

        from core.database import async_session_factory
        from core.models.ai_chat_session import AIChatSession

        async with async_session_factory() as db:
            try:
                query = select(AIChatSession)
                if scene:
                    query = query.where(AIChatSession.scene == scene)
                if novel_id:
                    # 按小说ID过滤会话
                    import uuid as uuid_module

                    query = query.where(AIChatSession.novel_id == uuid_module.UUID(novel_id))
                query = query.order_by(AIChatSession.updated_at.desc())

                result = await db.execute(query)
                sessions = result.scalars().all()

                session_list = []
                for session in sessions:
                    session_list.append(
                        {
                            "id": str(session.id),
                            "session_id": session.session_id,
                            "scene": session.scene,
                            "novel_id": (str(session.novel_id) if session.novel_id else None),
                            "title": session.title,
                            "context": session.context,
                            "created_at": session.created_at.isoformat(),
                            "updated_at": session.updated_at.isoformat(),
                        }
                    )

                return session_list
            except Exception as e:
                logger.error(f"获取会话列表失败: {e}")
                return []

    async def delete_session(self, session_id: str) -> bool:
        """删除会话."""
        from sqlalchemy import delete

        from core.database import async_session_factory
        from core.models.ai_chat_session import AIChatMessage, AIChatSession

        async with async_session_factory() as db:
            try:
                # 删除消息
                await db.execute(
                    delete(AIChatMessage).where(AIChatMessage.session_id == session_id)
                )

                # 删除会话
                await db.execute(
                    delete(AIChatSession).where(AIChatSession.session_id == session_id)
                )

                await db.commit()
                return True
            except Exception as e:
                logger.error(f"删除会话失败: {e}")
                await db.rollback()
                return False

    async def create_session(self, scene: str, context: Optional[dict] = None) -> ChatSession:
        import uuid

        session_id = str(uuid.uuid4())

        # 提取 novel_id 用于会话隔离
        novel_id = context.get("novel_id") if context else None

        session = ChatSession(session_id, scene, context, novel_id=novel_id)

        # 如果是小说相关场景，加载小说信息（按需加载章节内容）
        if context and "novel_id" in context:
            # 初始只加载基本信息，不加载章节内容（按需加载）
            novel_info = await self.get_novel_info(novel_id, 1, 0)  # end=0 表示不加载章节内容
            session.context["novel_info"] = novel_info
            session.context["chapter_range"] = {
                "start": 1,
                "end": 0,  # 表示尚未加载章节
            }
            # 记录当前版本号
            session.context["novel_version"] = self.memory_service.get_novel_version(novel_id)

            # 获取变化状态
            has_changes = novel_info.get("has_changes", False)

            logger.info(
                f"为场景 {scene} 加载小说信息: {novel_id}, 章节范围: 1-0(按需加载), 有变化: {has_changes}"
            )

            # 初始化持久化记忆（如果还没有）
            if novel_info and "error" not in novel_info:
                self._initialize_persistent_memory_for_novel(novel_id, novel_info)

            # 生成并存储分析结果到记忆服务
            analysis = self._analyze_novel_content(novel_info)
            session.context["analysis"] = analysis

            # 检测小说内容变化并更新记忆（使用增量合并）
            current_memory = self.memory_service.get_novel_memory(novel_id)
            if current_memory:
                # 获取现有分析结果
                existing_analysis = current_memory.get("analysis", {})
                # 增量合并分析结果
                merged_analysis = self._merge_analysis(existing_analysis, analysis)
                current_memory["analysis"] = merged_analysis
                # 只有在内容有变化时才更新记忆
                if has_changes:
                    self.memory_service.set_novel_memory(novel_id, current_memory)
                    logger.info(f"小说分析结果已增量更新: {novel_id}")
                else:
                    # 即使内容没变化，也更新分析（直接更新缓存，不触发版本递增）
                    self.memory_service.cache.set(f"novel:{novel_id}", current_memory)
            else:
                novel_info["analysis"] = analysis
                self.memory_service.set_novel_memory(novel_id, novel_info)

            # 章节助手场景：预加载当前章节内容和增强上下文
            if scene == SCENE_CHAPTER_ASSISTANT and "chapter_number" in context:
                chapter_number = context["chapter_number"]
                logger.info(f"章节助手场景: 尝试预加载第{chapter_number}章, novel_id={novel_id}")
                try:
                    # 加载当前章节内容
                    chapter_info = await self._get_chapter_by_number(novel_id, chapter_number)
                    if chapter_info and "error" not in chapter_info:
                        session.context["current_chapter"] = chapter_info
                        logger.info(
                            f"章节助手场景预加载章节内容成功: 第{chapter_number}章 - {chapter_info.get('title', '无标题')}"
                        )

                        # 构建增强上下文
                        from .chapter_context_builder import ChapterContextBuilder

                        context_builder = ChapterContextBuilder(self.db, self.memory_service)
                        assistant_context = await context_builder.build_context(
                            novel_id, chapter_number, chapter_info
                        )
                        session.context["assistant_context"] = assistant_context.to_dict()
                        logger.info(
                            f"章节助手场景构建增强上下文成功: 角色{len(assistant_context.chapter_characters)}个"
                        )
                    else:
                        logger.warning(f"章节助手场景预加载章节内容失败: {chapter_info}")
                except Exception as e:
                    logger.warning(f"预加载章节内容失败: {e}")
        else:
            logger.info(f"非小说相关场景或无novel_id: scene={scene}, context={context}")

        # 章节助手场景：动态生成欢迎消息
        welcome_message = WELCOME_MESSAGES.get(scene, "你好！我是AI助手，有什么可以帮助你的吗？")
        if scene == SCENE_CHAPTER_ASSISTANT:
            novel_title = session.context.get("novel_info", {}).get("title", "未知小说")
            chapter_info = session.context.get("current_chapter", {})
            chapter_num = (
                chapter_info.get("chapter_number", context.get("chapter_number", "?"))
                if context
                else "?"
            )
            chapter_title = chapter_info.get("title", f"第{chapter_num}章")
            logger.info(
                f"生成章节助手欢迎消息: novel_title={novel_title}, chapter_num={chapter_num}, chapter_title={chapter_title}"
            )
            welcome_message = f"""你好！我是章节编辑AI助手。

当前正在编辑：**《{novel_title}》** - **第{chapter_num}章：{chapter_title}**

我可以帮助你：
- 润色章节文字
- 扩展或精简情节
- 修复连贯性问题
- 增强描写和氛围

请告诉我你想对这章做什么修改？"""

        # 替换初始化时添加的默认欢迎消息
        if session.messages:
            session.messages[0] = ChatMessage("assistant", welcome_message)
        else:
            session.add_assistant_message(welcome_message)

        self.sessions[session_id] = session

        # 异步保存会话到数据库
        import asyncio

        asyncio.create_task(self.save_session(session))

        logger.info(f"创建AI对话会话: {session_id}, 场景: {scene}, 小说ID: {novel_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)

    async def _generate_session_title(self, session: ChatSession) -> str:
        """使用 AI 从对话内容中生成会话标题."""
        # 获取对话内容用于生成标题
        conversation_content = []
        for msg in session.messages[:6]:  # 只取前6条消息
            if msg.role == "user":
                conversation_content.append(f"用户: {msg.content[:200]}")
            else:
                conversation_content.append(f"助手: {msg.content[:200]}")

        if not conversation_content:
            return "新会话"

        prompt = f"""请根据以下对话内容，生成一个简洁的会话标题（10-20个字符），用于识别这次对话的主题。

对话内容:
{chr(10).join(conversation_content)}

要求:
1. 标题要简洁明了，能概括对话主题
2. 不超过20个字符
3. 直接输出标题，不需要任何解释或前缀

标题:"""

        try:
            response = await self.client.chat(
                prompt=prompt,
                system="你是一个专业的内容总结助手，擅长从对话中提炼出简洁的标题。",
                temperature=0.3,
            )
            title = response.get("content", "").strip()
            # 清理可能的前缀和多余内容
            title = title.replace("标题:", "").replace("标题：", "").strip()
            # 限制长度
            if len(title) > 50:
                title = title[:50]
            if not title:
                title = "新会话"
            return title
        except Exception as e:
            logger.error(f"生成会话标题失败: {e}")
            # 回退方案：从第一条用户消息截取
            for msg in session.messages:
                if msg.role == "user":
                    return msg.content[:20] + "..." if len(msg.content) > 20 else msg.content
            return "新会话"

    async def _update_session_title(self, session: ChatSession) -> None:
        """更新会话标题到数据库."""
        if session.title:
            return  # 已有标题，不更新

        # 只有当有用户消息时才生成标题
        user_messages = [m for m in session.messages if m.role == "user"]
        if not user_messages:
            return

        # 生成标题
        title = await self._generate_session_title(session)
        session.title = title

        # 更新数据库
        from sqlalchemy import update

        from core.database import async_session_factory
        from core.models.ai_chat_session import AIChatSession

        async with async_session_factory() as db:
            try:
                await db.execute(
                    update(AIChatSession)
                    .where(AIChatSession.session_id == session.session_id)
                    .values(title=title)
                )
                await db.commit()
                logger.info(f"会话 {session.session_id} 标题已更新为: {title}")
            except Exception as e:
                logger.error(f"更新会话标题失败: {e}")
                await db.rollback()

    async def _classify_intent_llm(self, user_message: str, scene: str) -> dict[str, Any]:
        """使用LLM进行意图分类.

        Args:
            user_message: 用户消息
            scene: 当前场景

        Returns:
            包含 primary_intent, confidence, reasoning, entities 的字典
        """
        scene_descriptions = {
            SCENE_NOVEL_CREATION: "用户正在创建新小说，需要世界观、角色、情节等方面的帮助",
            SCENE_NOVEL_REVISION: "用户正在修订已有的小说内容",
            SCENE_NOVEL_ANALYSIS: "用户正在分析小说的结构、市场定位或质量",
        }
        scene_context = scene_descriptions.get(scene, "用户在 general 对话中")

        messages = [
            {
                "role": "system",
                "content": INTENT_CLASSIFICATION_PROMPT + f"\n\n当前场景: {scene_context}",
            },
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.client.chat_with_tools(
                messages=messages,
                tools=INTENT_TOOLS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=1024,
            )

            if response.get("type") == "tool_call":
                tool_calls = response.get("tool_calls", [])
                for tool_call in tool_calls:
                    if tool_call.get("function", {}).get("name") == "classify_intent":
                        args_str = tool_call.get("function", {}).get("arguments", "{}")
                        result = json.loads(args_str)
                        logger.info(
                            f"LLM意图分类结果: {result.get('primary_intent')}, "
                            f"confidence: {result.get('confidence')}"
                        )
                        return result

            if response.get("type") == "text":
                content = response.get("content", "{}")
                result = json.loads(content)
                logger.info(
                    f"LLM意图分类结果(文本): {result.get('primary_intent')}, "
                    f"confidence: {result.get('confidence')}"
                )
                return result

            logger.warning(f"LLM返回了意外格式: {response}")
            return await self._classify_intent_fallback(user_message, scene)

        except json.JSONDecodeError as e:
            logger.error(f"LLM意图分类JSON解析失败: {e}")
            return await self._classify_intent_fallback(user_message, scene)
        except Exception as e:
            logger.error(f"LLM意图分类失败: {e}")
            return await self._classify_intent_fallback(user_message, scene)

    async def _classify_intent_fallback(self, user_message: str, scene: str) -> dict[str, Any]:
        """基于规则的工具意图分类（fallback方法）.

        Args:
            user_message: 用户消息
            scene: 当前场景

        Returns:
            包含 primary_intent, confidence, reasoning, entities 的字典
        """
        import re

        intent = self._analyze_user_intent_rule_based(user_message, scene)

        mentioned_characters = []
        char_patterns = [
            r"[主角|配角|角色|人物]\s*名叫[叫做]?\s*([^\s，。,\.]+)",
            r"([^\s，。,\.]+)\s*(?:这个角色|这个人物|主角|配角)",
        ]
        for pattern in char_patterns:
            matches = re.finditer(pattern, user_message)
            for match in matches:
                name = match.group(1).strip()
                if name and len(name) <= 10:
                    mentioned_characters.append(name)

        mentioned_chapters = []
        chapter_matches = re.finditer(r"第(\d+)章", user_message)
        for match in chapter_matches:
            try:
                mentioned_chapters.append(int(match.group(1)))
            except ValueError:
                pass

        genre = ""
        genre_keywords = {
            "玄幻": "玄幻",
            "都市": "都市",
            "仙侠": "仙侠",
            "历史": "历史",
            "科幻": "科幻",
            "游戏": "游戏",
            "轻小说": "轻小说",
        }
        for keyword, genre_value in genre_keywords.items():
            if keyword in user_message:
                genre = genre_value
                break

        confidence = 0.5
        reasoning = "Based on keyword matching"

        logger.info(f"Fallback意图分类结果: {intent}, confidence: {confidence}")
        return {
            "primary_intent": intent,
            "confidence": confidence,
            "reasoning": reasoning,
            "entities": {
                "mentioned_characters": list(set(mentioned_characters)),
                "mentioned_chapters": list(set(mentioned_chapters)),
                "genre": genre,
            },
        }

    async def _analyze_user_intent(self, user_message: str, scene: str) -> str:
        """分析用户的意图，识别用户需求类型（LLM + fallback）."""
        try:
            result = await self._classify_intent_llm(user_message, scene)
            if result.get("confidence", 0) >= 0.5:
                return result.get("primary_intent", "general")
            return result.get(
                "primary_intent", self._analyze_user_intent_rule_based(user_message, scene)
            )
        except Exception as e:
            logger.error(f"LLM意图分类异常: {e}")
            return self._analyze_user_intent_rule_based(user_message, scene)

    def _analyze_user_intent_rule_based(self, user_message: str, scene: str) -> str:
        """基于规则的意图分析（原始逻辑）."""
        if scene == SCENE_NOVEL_REVISION:
            return self._analyze_revision_intent(user_message)
        elif scene == SCENE_NOVEL_CREATION:
            # 分析创作意图
            if any(keyword in user_message for keyword in ["世界观", "世界设定", "背景"]):
                return "world_creation"
            elif any(keyword in user_message for keyword in ["角色", "人物", "主角"]):
                return "character_creation"
            elif any(keyword in user_message for keyword in ["大纲", "剧情", "情节"]):
                return "plot_creation"
            elif any(keyword in user_message for keyword in ["类型", "风格", "定位"]):
                return "genre_creation"
            else:
                return "general_creation"
        elif scene == SCENE_NOVEL_ANALYSIS:
            # 分析分析意图
            if any(keyword in user_message for keyword in ["结构", "整体", "框架"]):
                return "structure_analysis"
            elif any(keyword in user_message for keyword in ["市场", "定位", "读者"]):
                return "market_analysis"
            elif any(keyword in user_message for keyword in ["优势", "不足", "问题"]):
                return "strengths_weaknesses"
            elif any(keyword in user_message for keyword in ["建议", "改进", "优化"]):
                return "improvement_suggestions"
            else:
                return "general_analysis"
        else:
            return "general"

    def _analyze_revision_intent(self, user_message: str) -> str:
        """分析用户的修订意图，识别修订类型."""
        # 特殊模式识别：包含"改成"、"改为"等操作指令的消息
        action_patterns = [
            (r"把(.+?)改成", "update_field"),
            (r"把(.+?)改为", "update_field"),
            (r"把(.+?)修改", "update_field"),
            (r"(.+?)改成", "update_field"),
            (r"(.+?)改为", "update_field"),
            (r"(.+?)修改成", "update_field"),
            (r"添加(.+?)", "add"),
            (r"增加(.+?)", "add"),
            (r"删除(.+?)", "delete"),
            (r"移除(.+?)", "delete"),
        ]

        for pattern, action in action_patterns:
            if re.search(pattern, user_message):
                return "specific_revision"  # 特殊修订，需要精确执行

        # 扩展关键词列表
        world_keywords = [
            "世界观",
            "世界设定",
            "修炼体系",
            "地理环境",
            "势力划分",
            "规则设定",
            "世界背景",
            "宇宙观",
            "设定",
            "体系",
            "背景设定",
        ]
        character_keywords = [
            "角色",
            "人物",
            "性格",
            "背景",
            "能力",
            "成长路线",
            "主角",
            "配角",
            "人物塑造",
            "形象",
            "个性",
            "角色设定",
        ]
        outline_keywords = [
            "大纲",
            "剧情",
            "主线",
            "支线",
            "转折点",
            "高潮",
            "情节",
            "故事",
            "结构",
            "框架",
            "剧情发展",
            "情节设计",
        ]
        chapter_keywords = [
            "章节",
            "内容",
            "情节",
            "描写",
            "对话",
            "节奏",
            "章节内容",
            "段落",
            "细节",
            "叙述",
            "文风",
            "语言",
        ]

        # 统计关键词出现次数（加权）
        world_count = 0
        for keyword in world_keywords:
            if keyword in user_message:
                # 为更具体的关键词增加权重
                if keyword in ["修炼体系", "地理环境", "势力划分"]:
                    world_count += 2
                else:
                    world_count += 1

        character_count = 0
        for keyword in character_keywords:
            if keyword in user_message:
                if keyword in ["性格", "背景", "能力", "成长路线"]:
                    character_count += 2
                else:
                    character_count += 1

        outline_count = 0
        for keyword in outline_keywords:
            if keyword in user_message:
                if keyword in ["主线", "支线", "转折点", "高潮"]:
                    outline_count += 2
                else:
                    outline_count += 1

        chapter_count = 0
        for keyword in chapter_keywords:
            if keyword in user_message:
                if keyword in ["描写", "对话", "节奏", "细节"]:
                    chapter_count += 2
                else:
                    chapter_count += 1

        # 确定主要修订类型
        max_count = max(world_count, character_count, outline_count, chapter_count)

        # 设置阈值，低于阈值的视为通用修订
        threshold = 1
        if max_count >= threshold:
            if max_count == world_count:
                return "world_setting"
            elif max_count == character_count:
                return "character"
            elif max_count == outline_count:
                return "outline"
            elif max_count == chapter_count:
                return "chapter"

        # 特殊模式识别
        # 识别章节号
        chapter_match = re.search(r"第(\d+)章", user_message)
        if chapter_match:
            return "chapter"

        # 识别角色名（如果用户提到了具体角色）
        if any(keyword in user_message for keyword in ["角色", "人物", "主角", "配角"]):
            return "character"

        return "general"  # 通用修订

    def _extract_chapter_range(
        self, user_message: str, total_chapters: int
    ) -> Optional[tuple[int, int]]:
        """从用户消息中提取章节范围.

        Args:
            user_message: 用户消息
            total_chapters: 小说总章节数

        Returns:
            (start, end) 章节范围，如果未识别到则返回 None
        """
        import re

        # 1. 识别具体章节号："第3章"、"第5-8章"
        single_chapter = re.search(r"第(\d+)章", user_message)
        range_chapter = re.search(r"第(\d+)[-~至到](\d+)章", user_message)

        if range_chapter:
            start = int(range_chapter.group(1))
            end = int(range_chapter.group(2))
            return (max(1, start), min(end, total_chapters))
        elif single_chapter:
            ch_num = int(single_chapter.group(1))
            # 加载该章节及其前后各1章（上下文）
            start = max(1, ch_num - 1)
            end = min(ch_num + 1, total_chapters)
            return (start, end)

        # 2. 识别关键词范围
        if any(kw in user_message for kw in ["前几章", "开头", "开篇", "前面章节"]):
            return (1, min(5, total_chapters))
        elif any(kw in user_message for kw in ["后面章节", "后面", "结尾", "结局"]):
            return (max(1, total_chapters - 4), total_chapters)
        elif any(kw in user_message for kw in ["所有章节", "全部章节", "所有内容", "全部内容"]):
            return (1, total_chapters)
        elif any(kw in user_message for kw in ["最近章节", "最新章节", "最近几章"]):
            return (max(1, total_chapters - 4), total_chapters)

        # 3. 识别章节内容相关请求 - 加载前5章作为默认
        chapter_keywords = ["章节", "内容", "情节", "描写", "对话", "节奏", "段落", "叙述"]
        if any(kw in user_message for kw in chapter_keywords):
            return (1, min(5, total_chapters))

        return None  # 未识别到章节范围

    def _generate_follow_up_questions(
        self, intent: str, scene: str, novel_info: Optional[dict] = None
    ) -> list[str]:
        """根据用户意图生成后续问题."""
        questions = []

        if scene == SCENE_NOVEL_REVISION:
            if intent == "world_setting":
                questions.append(
                    "你希望在世界观设定中重点改进哪个方面？（如修炼体系、地理环境、势力划分等）"
                )
                questions.append("你对当前世界观设定有什么具体的不满意之处？")
            elif intent == "character":
                questions.append("你希望重点改进哪个角色？")
                questions.append("你觉得该角色当前存在哪些问题？")
            elif intent == "outline":
                questions.append("你希望改进剧情的哪个部分？（如主线、支线、高潮等）")
                questions.append("你对当前剧情发展有什么具体的想法？")
            elif intent == "chapter":
                questions.append("你希望改进哪个章节？")
                questions.append("你觉得该章节存在哪些具体问题？")
            else:
                questions.append("你对小说的哪些方面不满意？")
                questions.append("你希望达到什么样的改进效果？")

        elif scene == SCENE_NOVEL_CREATION:
            if intent == "world_creation":
                questions.append("你希望创建什么样的世界观？（如玄幻、科幻、历史等）")
                questions.append("你对世界观有什么具体的设定想法？")
            elif intent == "character_creation":
                questions.append("你希望创建什么样的角色？")
                questions.append("角色的性格和背景是怎样的？")
            elif intent == "plot_creation":
                questions.append("你希望讲述什么样的故事？")
                questions.append("故事的主要冲突和高潮是什么？")
            elif intent == "genre_creation":
                questions.append("你希望创作什么类型的小说？")
                questions.append("你对该类型小说有什么特别的要求？")
            else:
                questions.append("你希望创作什么类型的小说？")
                questions.append("你对小说有什么具体的创意想法？")

        elif scene == SCENE_NOVEL_ANALYSIS:
            if intent == "structure_analysis":
                questions.append("你对小说的结构有什么具体的关注点？")
                questions.append("你希望分析小说的哪些结构要素？")
            elif intent == "market_analysis":
                questions.append("你希望了解小说在哪个市场的表现？")
                questions.append("你对小说的市场定位有什么疑问？")
            elif intent == "strengths_weaknesses":
                questions.append("你特别关注小说的哪些优势或不足？")
                questions.append("你希望在哪些方面得到改进建议？")
            elif intent == "improvement_suggestions":
                questions.append("你希望在哪些方面得到具体的改进建议？")
                questions.append("你对改进的优先级有什么想法？")
            else:
                questions.append("你希望从哪些方面分析这部小说？")
                questions.append("你对分析结果有什么特别的期望？")

        return questions

    def _check_need_clarification(self, user_message: str, scene: str) -> bool:
        """检查是否需要澄清用户意图."""
        # 检查用户输入是否过于简短或模糊
        if len(user_message) < 10:
            return True

        # 检查是否包含模糊词汇
        vague_terms = ["帮忙", "改进", "分析", "建议", "看看", "检查"]
        if any(term in user_message for term in vague_terms):
            # 如果只是模糊请求，需要澄清
            if all(
                term not in user_message
                for term in ["世界观", "角色", "剧情", "章节", "结构", "市场"]
            ):
                return True

        return False

    def _safe_get(self, data: dict, path: str, default: Any = "") -> Any:
        """安全访问嵌套字典字段.

        Args:
            data: 字典数据
            path: 点分隔的路径，如 'world_setting.content'
            default: 默认值

        Returns:
            字段值或默认值
        """
        if not data or not isinstance(data, dict):
            return default

        keys = path.split(".")
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current if current is not None else default

    def _merge_analysis(self, existing: dict, new: dict) -> dict:
        """增量合并分析结果.

        strengths/weaknesses/suggestions 追加不重复项，
        genre_specific 替换为新值。

        Args:
            existing: 现有分析结果
            new: 新的分析结果

        Returns:
            合并后的分析结果
        """
        if not existing:
            return new.copy() if new else {}
        if not new:
            return existing.copy()

        merged = existing.copy()

        # strengths/weaknesses/suggestions 追加不重复项
        for key in ["strengths", "weaknesses", "suggestions"]:
            existing_items = set(existing.get(key, []))
            new_items = set(new.get(key, []))
            merged[key] = list(existing_items | new_items)

        # genre_specific 替换（因为类型特定建议应该更新）
        if new.get("genre_specific"):
            merged["genre_specific"] = new["genre_specific"]

        return merged

    def _analyze_novel_content(self, novel_info: dict) -> dict:
        """分析小说内容，生成分析结果."""
        analysis = {
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "genre_specific": [],
        }

        # 分析世界观（使用安全访问）
        world_content = self._safe_get(novel_info, "world_setting.content", "")
        if world_content:
            if len(world_content) > 500:
                analysis["strengths"].append("世界观设定详细丰富")
            else:
                analysis["weaknesses"].append("世界观设定可能过于简单")
                analysis["suggestions"].append("建议扩展世界观设定，增加更多细节和深度")
        else:
            analysis["weaknesses"].append("缺乏世界观设定")
            analysis["suggestions"].append("建议添加详细的世界观设定")

        # 分析角色
        characters = novel_info.get("characters") or []
        if len(characters) >= 3:
            analysis["strengths"].append(f"角色数量充足（{len(characters)}个）")
        else:
            analysis["weaknesses"].append("角色数量较少")
            analysis["suggestions"].append("建议增加更多有特色的角色")

        # 分析大纲（使用安全访问）
        outline_content = self._safe_get(novel_info, "plot_outline.content", "")
        if outline_content:
            if len(outline_content) > 300:
                analysis["strengths"].append("剧情大纲完整")
            else:
                analysis["weaknesses"].append("剧情大纲可能过于简单")
                analysis["suggestions"].append("建议扩展剧情大纲，增加更多情节细节")
        else:
            analysis["weaknesses"].append("缺乏剧情大纲")
            analysis["suggestions"].append("建议添加详细的剧情大纲")

        # 分析章节
        chapters = novel_info.get("chapters") or []
        if len(chapters) >= 3:
            analysis["strengths"].append(f"章节数量充足（{len(chapters)}章）")
        else:
            analysis["weaknesses"].append("章节数量较少")
            analysis["suggestions"].append("建议增加更多章节内容")

        # 基于小说类型的分析
        genre = novel_info.get("genre", "")
        if genre == "玄幻":
            analysis["genre_specific"].append(
                "作为玄幻小说，建议加强修炼体系的设定和战斗场景的描写"
            )
        elif genre == "都市":
            analysis["genre_specific"].append("作为都市小说，建议加强人物关系和现实感的描写")
        elif genre == "仙侠":
            analysis["genre_specific"].append(
                "作为仙侠小说，建议加强仙风道骨的氛围营造和修仙境界的设定"
            )
        elif genre == "历史":
            analysis["genre_specific"].append(
                "作为历史小说，建议加强历史细节的准确性和时代背景的描写"
            )

        return analysis

    def _get_persistent_memory_context(self, novel_id: str, current_chapter: int = 0) -> str:
        """从持久化记忆获取增强上下文信息.

        Args:
            novel_id: 小说ID
            current_chapter: 当前章节号（用于获取相关章节摘要）

        Returns:
            格式化的上下文信息字符串
        """
        context_parts = []

        try:
            # 1. 获取章节摘要（最近10章）- 直接使用 storage 的同步方法
            recent_summaries = self.persistent_memory.storage.get_recent_chapter_summaries(
                novel_id,
                current_chapter or 100,  # 如果未指定章节，假设获取最近章节
                count=10,
            )
            if recent_summaries:
                context_parts.append("## 章节摘要（最近章节）")
                for summary in recent_summaries[:5]:  # 只取最近5章摘要
                    chapter_num = summary.get("chapter_number", "?")
                    key_events = summary.get("key_events", [])
                    if key_events:
                        events_str = "、".join(key_events[:3])
                        context_parts.append(f"- 第{chapter_num}章: {events_str}")

            # 2. 获取角色状态
            character_states = self.persistent_memory.storage.get_all_character_states(novel_id)
            if character_states:
                context_parts.append("\n## 主要角色当前状态")
                for name, state in list(character_states.items())[:5]:  # 只取5个主要角色
                    location = state.get("current_location", "未知")
                    level = state.get("cultivation_level", "")
                    emotional = state.get("emotional_state", "")
                    status_parts = [f"位置: {location}"]
                    if level:
                        status_parts.append(f"境界: {level}")
                    if emotional:
                        status_parts.append(f"状态: {emotional}")
                    context_parts.append(f"- {name}: {', '.join(status_parts)}")

            # 3. 获取未解决的伏笔
            foreshadowing_list = self.persistent_memory.storage.get_foreshadowing(
                novel_id, status="planted"
            )
            if foreshadowing_list:
                context_parts.append("\n## 待解决的伏笔")
                for fs in foreshadowing_list[:5]:  # 只取5个伏笔
                    desc = fs.get("description", "未知")
                    planted_ch = fs.get("planted_chapter", "?")
                    context_parts.append(f"- 第{planted_ch}章埋下: {desc[:50]}...")

            # 4. 获取时间线事件
            timeline = self.persistent_memory.storage.get_timeline_events(novel_id, limit=5)
            if timeline:
                context_parts.append("\n## 关键时间线")
                for event in timeline:
                    chapter = event.get("chapter_number", "?")
                    desc = event.get("description", "未知")
                    context_parts.append(f"- 第{chapter}章: {desc[:30]}")

        except Exception as e:
            logger.warning(f"获取持久化记忆上下文失败: {e}")
            return ""

        if context_parts:
            return "\n".join(context_parts)
        return ""

    def _initialize_persistent_memory_for_novel(self, novel_id: str, novel_info: dict) -> None:
        """为小说初始化持久化记忆.

        Args:
            novel_id: 小说ID
            novel_info: 小说信息字典
        """
        try:
            # 保存小说元数据
            metadata = {
                "title": novel_info.get("title", ""),
                "genre": novel_info.get("genre", ""),
                "synopsis": novel_info.get("synopsis", ""),
                "status": novel_info.get("status", ""),
                "word_count": novel_info.get("word_count", 0),
                "chapter_count": novel_info.get("chapter_count", 0),
            }
            self.persistent_memory.storage.save_novel_metadata(novel_id, metadata)

            # 保存角色状态（从现有角色信息初始化）
            characters = novel_info.get("characters", [])
            for char in characters[:20]:  # 最多20个角色
                char_name = char.get("name", "")
                if char_name:
                    # 解析背景信息
                    background = char.get("background", "")
                    starting_location = ""
                    if isinstance(background, dict):
                        starting_location = background.get("starting_location", "")

                    state = {
                        "role_type": char.get("role_type", ""),
                        "current_location": starting_location or "未知",
                        "cultivation_level": "",
                        "emotional_state": "正常",
                        "last_appearance_chapter": 0,
                    }
                    self.persistent_memory.storage.save_character_state(novel_id, char_name, state)

            logger.info(f"为小说 {novel_id} 初始化持久化记忆完成")

        except Exception as e:
            logger.warning(f"初始化持久化记忆失败: {e}")

    def _generate_revision_prompt(
        self, user_message: str, revision_type: str, novel_info: dict
    ) -> str:
        """根据修订类型和小说内容生成针对性的提示词."""
        # 生成小说分析
        analysis = self._analyze_novel_content(novel_info)

        # 构建基础提示
        prompt = f"# 用户修订需求\n{user_message}\n"

        # 添加修订目标说明
        prompt += "\n# 修订目标\n"

        # 添加小说分析结果
        prompt += "\n# 小说分析\n"
        if analysis["strengths"]:
            prompt += "## 优势\n"
            for strength in analysis["strengths"]:
                prompt += f"- {strength}\n"
        if analysis["weaknesses"]:
            prompt += "\n## 不足\n"
            for weakness in analysis["weaknesses"]:
                prompt += f"- {weakness}\n"
        if analysis["suggestions"]:
            prompt += "\n## 初步建议\n"
            for suggestion in analysis["suggestions"]:
                prompt += f"- {suggestion}\n"
        if analysis["genre_specific"]:
            prompt += "\n## 类型特定建议\n"
            for suggestion in analysis["genre_specific"]:
                prompt += f"- {suggestion}\n"

        # 添加持久化记忆上下文（章节摘要、角色状态、伏笔等）
        novel_id = novel_info.get("id")
        if novel_id:
            persistent_context = self._get_persistent_memory_context(novel_id)
            if persistent_context:
                prompt += "\n# 持久化记忆上下文\n"
                prompt += persistent_context + "\n"

        # 检查用户是否询问世界观相关问题
        is_worldview_question = any(
            keyword in user_message
            for keyword in [
                "世界观",
                "世界设定",
                "背景",
                "修炼体系",
                "地理环境",
                "势力划分",
            ]
        )

        # 无论修订类型如何，只要用户询问世界观问题，就添加世界观信息
        if is_worldview_question or revision_type == "world_setting":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的世界观设定，包括以下方面：\n"
            prompt += "1. 修炼体系的合理性和层次感\n"
            prompt += "2. 地理环境的丰富性和独特性\n"
            prompt += "3. 势力划分的逻辑性和平衡性\n"
            prompt += "4. 世界规则的一致性和创新性\n"
            prompt += "并提供具体的修订建议，包括如何扩展世界观深度和广度。\n"
            if novel_info.get("world_setting"):
                prompt += "\n## 当前世界观\n"
                world_content = novel_info.get("world_setting", {}).get("content", "") or ""
                # 优化内容呈现，确保重要信息不被截断
                if len(world_content) > 600:
                    # 提取关键信息
                    try:
                        import json

                        # 尝试解析JSON格式的世界观内容
                        world_data = json.loads(world_content)
                        # 提取关键信息
                        key_points = []
                        if "world_name" in world_data:
                            key_points.append(f"世界名称: {world_data['world_name']}")
                        if "world_type" in world_data:
                            key_points.append(f"世界类型: {world_data['world_type']}")
                        if "power_system" in world_data:
                            power_system = world_data["power_system"]
                            key_points.append(f"修炼体系: {power_system.get('name', '未知')}")
                            if "levels" in power_system:
                                levels = power_system["levels"][:3]  # 只取前3个境界
                                for level in levels:
                                    key_points.append(
                                        f"  - {level.get('name', '未知')}: {level.get('description', '无描述')}"
                                    )
                        if "geography" in world_data:
                            geography = world_data["geography"]
                            if geography:
                                # 安全处理 geography，可能是字典、列表或字符串
                                if isinstance(geography, (dict, list)):
                                    geography_str = json.dumps(geography, ensure_ascii=False)
                                else:
                                    geography_str = str(geography)
                                key_points.append(f"地理环境: {geography_str[:100]}...")
                        if "factions" in world_data:
                            factions = world_data["factions"]
                            if factions:
                                # 安全处理 factions，可能是字典、列表或字符串
                                if isinstance(factions, (dict, list)):
                                    factions_str = json.dumps(factions, ensure_ascii=False)
                                else:
                                    factions_str = str(factions)
                                key_points.append(f"势力划分: {factions_str[:100]}...")
                        prompt += "\n".join(key_points) + "...\n"
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，按普通文本处理
                        lines = world_content.split("\n")
                        key_points = []
                        for line in lines:
                            if line.strip() and len(" ".join(key_points)) < 500:
                                key_points.append(line.strip())
                        prompt += "\n".join(key_points[:10]) + "...\n"
                else:
                    prompt += world_content + "\n"

        elif revision_type == "character":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的角色设定，包括以下方面：\n"
            prompt += "1. 角色性格的鲜明性和一致性\n"
            prompt += "2. 角色背景的丰富性和合理性\n"
            prompt += "3. 角色能力的平衡性和成长性\n"
            prompt += "4. 角色关系的复杂性和真实性\n"
            prompt += "并提供具体的修订建议，包括如何让角色更加立体和有吸引力。\n"
            if novel_info.get("characters"):
                prompt += "\n## 当前主要角色\n"
                for char in novel_info.get("characters", [])[:3]:
                    prompt += f"### {char.get('name', '未知')}\n"
                    prompt += f"- 角色类型: {char.get('role_type', '未知')}\n"
                    if char.get("description"):
                        desc = char.get("description", "")[:300]
                        prompt += f"- 描述: {desc}...\n"
                    if char.get("personality"):
                        prompt += f"- 性格: {char.get('personality', '无')[:100]}...\n"
                    if char.get("background"):
                        prompt += f"- 背景: {char.get('background', '无')[:100]}...\n"
                    prompt += "\n"

        elif revision_type == "outline":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的剧情大纲，包括以下方面：\n"
            prompt += "1. 主线剧情的逻辑性和吸引力\n"
            prompt += "2. 支线故事的丰富性和关联性\n"
            prompt += "3. 关键转折点的合理性和冲击力\n"
            prompt += "4. 高潮设计的震撼性和满意度\n"
            prompt += "并提供具体的修订建议，包括如何让剧情更加紧凑和引人入胜。\n"
            if novel_info.get("plot_outline"):
                prompt += "\n## 当前大纲\n"
                outline_content = novel_info.get("plot_outline", {}).get("content", "") or ""
                if len(outline_content) > 600:
                    # 提取关键信息
                    key_points = []
                    lines = outline_content.split("\n")
                    for line in lines:
                        if line.strip() and len(" ".join(key_points)) < 500:
                            key_points.append(line.strip())
                    prompt += "\n".join(key_points[:10]) + "...\n"
                else:
                    prompt += outline_content + "\n"

        elif revision_type == "chapter":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的章节内容，包括以下方面：\n"
            prompt += "1. 情节逻辑的连贯性和合理性\n"
            prompt += "2. 描写细节的生动性和准确性\n"
            prompt += "3. 人物对话的自然性和个性化\n"
            prompt += "4. 节奏控制的张弛度和吸引力\n"
            prompt += "并提供具体的修订建议，包括如何让章节内容更加精彩和流畅。\n"

            if novel_info.get("chapters"):
                prompt += "\n## 当前章节内容分析\n"

                # 尝试获取智能摘要（如果已有）
                novel_id = novel_info.get("id")
                # 不限制章节数量，分析所有已加载的章节
                chapters_to_analyze = novel_info.get("chapters", [])

                # 检查是否有章节内容已加载
                chapters_with_content = [ch for ch in chapters_to_analyze if ch.get("content")]
                if not chapters_with_content:
                    prompt += (
                        '（章节内容尚未加载，请指定您想分析的章节范围，如"第1-5章"或"第3章"）\n'
                    )
                else:
                    for chapter in chapters_with_content:
                        chapter_num = chapter.get("chapter_number", "?")
                        chapter_title = chapter.get("title", "未知")
                        chapter_content = chapter.get("content", "") or ""
                        word_count = chapter.get("word_count", len(chapter_content))

                        prompt += f"\n### 第{chapter_num}章: {chapter_title}（{word_count}字）\n"

                        # 尝试获取已有的智能摘要作为补充
                        smart_summary = None
                        if novel_id:
                            try:
                                smart_summary = self.persistent_memory.storage.get_chapter_summary(
                                    novel_id, chapter_num
                                )
                            except Exception:
                                pass

                        # 始终优先提供完整章节内容（不再截断）
                        if chapter_content:
                            prompt += "#### 章节完整内容\n"
                            prompt += chapter_content + "\n"
                        else:
                            prompt += "（章节内容为空）\n"

                        # 智能摘要作为补充信息
                        if smart_summary:
                            prompt += "\n#### 章节智能摘要（补充信息）\n"
                            if smart_summary.get("plot_summary"):
                                prompt += f"**情节概要**: {smart_summary['plot_summary']}\n"
                            if smart_summary.get("key_events"):
                                prompt += (
                                    f"**关键事件**: {'、'.join(smart_summary['key_events'][:5])}\n"
                                )
                            if smart_summary.get("character_interactions"):
                                prompt += f"**人物互动**: {'、'.join(smart_summary['character_interactions'][:3])}\n"
                            if smart_summary.get("emotional_arc"):
                                prompt += f"**情感走向**: {smart_summary['emotional_arc']}\n"
                            if smart_summary.get("foreshadowing"):
                                prompt += f"**伏笔暗示**: {'、'.join(smart_summary['foreshadowing'][:3])}\n"
                            if smart_summary.get("ending_state"):
                                prompt += f"**结尾状态**: {smart_summary['ending_state']}\n"

                        prompt += "\n"

        else:  # general
            prompt += "\n# 详细分析要求\n"
            prompt += "请分析小说的整体情况，包括世界观、角色、大纲和章节等方面，并根据用户的需求提供综合性的修订建议。\n"
            prompt += "建议从以下几个方面进行分析：\n"
            prompt += "1. 小说整体结构的合理性\n"
            prompt += "2. 各元素之间的协调性\n"
            prompt += "3. 类型特点的体现程度\n"
            prompt += "4. 潜在的改进空间\n"
            # 添加小说概览
            if novel_info.get("title"):
                prompt += "\n## 小说概览\n"
                prompt += f"- 标题: {novel_info.get('title', '未知')}\n"
                prompt += f"- 类型: {novel_info.get('genre', '未知')}\n"
                prompt += f"- 状态: {novel_info.get('status', '未知')}\n"
                prompt += f"- 章节数: {novel_info.get('chapter_count', 0)}\n"
                prompt += f"- 字数: {novel_info.get('word_count', 0)}\n"
                if novel_info.get("synopsis"):
                    prompt += f"- 简介: {novel_info.get('synopsis')[:200]}...\n"

        # 根据问题类型给出回复指导
        prompt += "\n# 回复要求\n"
        prompt += "请根据用户的具体问题自然地回复，不要拘泥于固定格式。\n"
        prompt += "- 如果用户问的是简单问题，直接简洁回答即可\n"
        prompt += "- 如果用户需要详细分析，再提供结构化的分析结果\n"
        prompt += "- 回复要贴合用户的问题意图，语气亲切自然\n"

        return prompt

    async def send_message(self, session_id: str, user_message: str) -> str:
        """发送消息并获取AI回复（工具调用模式）."""
        import asyncio

        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        session.add_user_message(user_message)
        system_prompt = self._get_system_prompt(session.scene)

        # 小说相关场景使用工具调用模式
        if session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS, SCENE_CHAPTER_ASSISTANT]:
            novel_id = session.context.get("novel_id")
            if not novel_id:
                novel_info = session.context.get("novel_info", {})
                novel_id = novel_info.get("id") if novel_info else None

            if novel_id:
                # 使用工具调用模式处理小说相关请求
                return await self._send_message_with_tools(
                    session, user_message, system_prompt, novel_id
                )

        # 非小说场景：直接调用LLM
        response = await self.client.chat(
            prompt=user_message,
            system=system_prompt,
            temperature=0.8,
        )

        assistant_message = response.get("content", "抱歉，我暂时无法回答这个问题。")
        session.add_assistant_message(assistant_message)

        asyncio.create_task(self.save_session(session))
        if not session.title:
            asyncio.create_task(self._update_session_title(session))

        logger.info(f"会话 {session_id} 收到用户消息: {user_message[:50]}...")
        return assistant_message

    async def _send_message_with_tools(
        self,
        session: "ChatSession",
        user_message: str,
        system_prompt: str,
        novel_id: str,
    ) -> str:
        """使用工具调用模式处理小说相关消息.

        包含完整的对话历史，当上下文超过阈值时执行压缩。
        """
        import asyncio

        from backend.config import settings
        from llm.token_calculator import TokenCalculator

        executor = NovelToolExecutor(db=self.db, novel_id=novel_id)
        token_calc = TokenCalculator()

        # 构建消息列表：system + 历史对话 + 当前用户消息
        # 对于 chapter_assistant 场景，使用增强的 System Prompt
        actual_system_prompt = system_prompt
        if session.scene == SCENE_CHAPTER_ASSISTANT:
            current_chapter = session.context.get("current_chapter", {})
            assistant_context = session.context.get("assistant_context", {})
            if current_chapter and "error" not in current_chapter:
                # 构建增强的 System Prompt
                actual_system_prompt = self._build_chapter_assistant_prompt(
                    system_prompt, current_chapter, assistant_context
                )
                logger.info("章节助手场景: 已构建增强的 System Prompt")

        messages = [{"role": "system", "content": actual_system_prompt}]

        # 添加历史对话
        history = session.get_conversation_history(limit=20)  # 获取最近20条
        if history:
            messages.extend(history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        # 检查上下文长度，超过阈值时压缩
        total_content = " ".join([m.get("content", "") for m in messages if m.get("content")])
        total_tokens = token_calc.count_tokens(total_content)

        if total_tokens > settings.CONTEXT_COMPRESSOR_MAX_TOKENS:
            logger.info(
                f"对话上下文达到 {total_tokens} tokens，超过阈值 {settings.CONTEXT_COMPRESSOR_MAX_TOKENS}，执行压缩"
            )
            messages = self._compress_conversation_history(
                messages, system_prompt, token_calc, settings.CONTEXT_COMPRESSOR_MAX_TOKENS
            )
            # 重新计算token
            total_content = " ".join([m.get("content", "") for m in messages if m.get("content")])
            total_tokens = token_calc.count_tokens(total_content)
            logger.info(f"压缩后上下文: {total_tokens} tokens")

        # 工具调用循环（支持查询和修改工具）
        max_iterations = settings.MAX_TOOL_CALL_ITERATIONS
        for iteration in range(max_iterations):
            logger.info(f"工具调用迭代: 第{iteration + 1}次")
            response = await self.client.chat_with_tools(
                messages=messages,
                tools=NOVEL_ALL_TOOLS,  # 包含查询和修改工具
                temperature=0.7,
            )

            if response["type"] == "text":
                # LLM返回文本回复，结束循环
                logger.info(f"工具调用完成: 共{iteration}次迭代")
                assistant_message = response["content"]
                break

            if response["type"] == "tool_call":
                # 处理工具调用
                tool_results = []
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}

                    logger.info(f"执行工具: {tool_name}, 参数: {list(arguments.keys())}")
                    result = await executor.execute(tool_name, arguments)
                    tool_results.append(
                        {
                            "tool_call_id": tool_call["id"],
                            "name": tool_name,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

                # 添加工具结果到消息
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": response["tool_calls"],
                    }
                )
                for tr in tool_results:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tr["tool_call_id"],
                            "content": tr["content"],
                        }
                    )

                continue

            # 未知响应类型
            assistant_message = "抱歉，处理您的请求时出现问题。"
            break
        else:
            # 达到最大迭代次数，生成一个总结性回复
            assistant_message = "我已完成了部分修改操作。由于操作较多，我已暂停执行。请告诉我是否需要继续，或者您可以查看当前的修改结果。"

        session.add_assistant_message(assistant_message)
        asyncio.create_task(self.save_session(session))
        if not session.title:
            asyncio.create_task(self._update_session_title(session))

        return assistant_message

    def _build_chapter_assistant_prompt(
        self,
        base_prompt: str,
        chapter_info: dict,
        context: dict,
    ) -> str:
        """构建章节助手的增强 System Prompt.

        Args:
            base_prompt: 基础 System Prompt
            chapter_info: 当前章节信息
            context: 增强上下文信息

        Returns:
            完整的 System Prompt
        """
        from .chapter_context_builder import format_characters_for_prompt

        chapter_num = chapter_info.get("chapter_number", "?")
        chapter_title = chapter_info.get("title", f"第{chapter_num}章")
        chapter_content = chapter_info.get("content", "")
        word_count = chapter_info.get("word_count", len(chapter_content))

        # 小说基本信息
        novel_title = context.get("novel_title", "未知小说")
        novel_genre = context.get("novel_genre", "")

        # 前序章节摘要
        prev_summary = context.get("previous_chapters_summary", "暂无前序章节信息")

        # 本章涉及角色
        characters = context.get("chapter_characters", [])
        characters_text = format_characters_for_prompt(characters)

        # 情节上下文
        plot_context = context.get("plot_context", "")

        return f"""{base_prompt}

---

## 当前工作上下文

### 小说信息
- 标题: 《{novel_title}》
- 类型: {novel_genre}
- 当前章节: 第{chapter_num}章 - {chapter_title}（{word_count}字）

### 前序章节摘要
{prev_summary}

### 本章涉及角色
{characters_text}

### 情节背景
{plot_context if plot_context else "暂无情节大纲"}

---

## 当前章节内容

{chapter_content}

---"""

    def _compress_conversation_history(
        self,
        messages: list[dict],
        system_prompt: str,
        token_calc: Any,
        max_tokens: int,
    ) -> list[dict]:
        """压缩对话历史，保留关键信息.

        策略：
        1. 始终保留 system 消息
        2. 保留最近 4 轮对话（8条消息：4个user + 4个assistant）
        3. 对更早的对话生成摘要压缩

        Args:
            messages: 原始消息列表
            system_prompt: 系统提示词
            token_calc: Token计算器
            max_tokens: 最大token阈值

        Returns:
            压缩后的消息列表
        """
        # 分离 system 消息
        system_messages = [m for m in messages if m.get("role") == "system"]
        other_messages = [m for m in messages if m.get("role") != "system"]

        # 保留最近 4 轮对话（8条消息）
        keep_recent_count = min(8, len(other_messages))
        recent_messages = other_messages[-keep_recent_count:] if keep_recent_count > 0 else []
        old_messages = (
            other_messages[:-keep_recent_count] if keep_recent_count < len(other_messages) else []
        )

        if not old_messages:
            # 没有旧消息需要压缩，直接返回
            return messages

        # 对旧消息生成摘要
        old_content_parts = []
        for msg in old_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if content:
                old_content_parts.append(f"[{role}]: {content}")

        old_content = "\n".join(old_content_parts)

        # 生成压缩摘要（简单截取关键信息）
        # 如果旧内容太长，截取关键部分
        if token_calc.count_tokens(old_content) > 1000:
            # 截取每条消息的前200字符
            compressed_parts = []
            for part in old_content_parts:
                if len(part) > 200:
                    compressed_parts.append(part[:200] + "...")
                else:
                    compressed_parts.append(part)
            old_content = "\n".join(compressed_parts)

        # 创建摘要消息
        summary_message = {
            "role": "system",
            "content": f"【历史对话摘要】\n{old_content}",
        }

        # 构建压缩后的消息列表
        compressed_messages = system_messages + [summary_message] + recent_messages

        logger.info(
            f"对话历史压缩完成: 原始 {len(messages)} 条消息 -> 压缩后 {len(compressed_messages)} 条消息"
        )

        return compressed_messages

    # === 以下为保留的旧方法，供 send_message_stream 等其他方法使用 ===

    async def _send_message_legacy(self, session_id: str, user_message: str) -> str:
        """旧版消息处理方法（保留用于兼容）."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        session.add_user_message(user_message)

        # 分析用户意图
        user_intent = await self._analyze_user_intent(user_message, session.scene)
        session.set_last_user_intent(user_intent)

        # 检查是否需要澄清
        # 如果是小说相关场景且包含小说信息，直接回答而不澄清
        is_novel_related = session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]
        has_novel_info = session.context.get(
            "novel_info", {}
        ) and "error" not in session.context.get("novel_info", {})

        # 只有在非小说场景或没有小说信息时才需要澄清
        need_clarification = self._check_need_clarification(user_message, session.scene)
        if is_novel_related and has_novel_info:
            # 有小说信息时，不需要澄清，直接基于小说信息回答
            need_clarification = False

        if need_clarification:
            # 生成追问
            follow_up_questions = self._generate_follow_up_questions(
                user_intent, session.scene, session.context.get("novel_info")
            )
            session.add_follow_up_question(follow_up_questions[0] if follow_up_questions else "")

            # 生成追问回复
            clarification_message = "为了给你提供更准确的帮助，我需要了解更多信息。"
            if follow_up_questions:
                clarification_message += f" {follow_up_questions[0]}"
            session.add_assistant_message(clarification_message)

            # 异步保存会话到数据库
            import asyncio

            asyncio.create_task(self.save_session(session))

            logger.info(f"会话 {session_id} 需要澄清: {user_message[:50]}...")
            return clarification_message

        session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)

        # 如果是小说相关场景，添加小说信息到提示词
        prompt = user_message
        if session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]:
            novel_info = session.context.get("novel_info", {})
            novel_id = novel_info.get("id") if novel_info else None

            # 检查小说信息是否需要刷新（版本号变化或数据为空）
            if novel_id:
                # 获取当前记忆版本
                current_version = self.memory_service.get_novel_version(novel_id)
                session_version = session.context.get("novel_version", 0)

                # 如果版本号不一致，重新加载小说信息
                if current_version != session_version:
                    logger.info(
                        f"检测到小说 {novel_id} 数据更新（版本 {session_version} -> {current_version}），重新加载小说信息"
                    )
                    chapter_start = session.context.get("chapter_range", {}).get("start", 1)
                    chapter_end = session.context.get("chapter_range", {}).get("end", 10)
                    # 强制从数据库加载最新数据
                    novel_info = await self.get_novel_info(
                        novel_id, chapter_start, chapter_end, force_db=True
                    )
                    session.context["novel_info"] = novel_info
                    session.context["novel_version"] = current_version
                    logger.info(f"小说 {novel_id} 信息已从数据库刷新到最新版本")
            else:
                # novel_id 为空，说明 novel_info 数据为空，需要重新加载
                stored_novel_id = session.context.get("novel_id")
                if stored_novel_id:
                    logger.warning(
                        f"会话 {session.session_id} 的 novel_info 为空，重新加载小说 {stored_novel_id} 信息"
                    )
                    chapter_start = session.context.get("chapter_range", {}).get("start", 1)
                    chapter_end = session.context.get("chapter_range", {}).get("end", 10)
                    novel_info = await self.get_novel_info(
                        stored_novel_id, chapter_start, chapter_end, force_db=True
                    )
                    session.context["novel_info"] = novel_info
                    session.context["novel_version"] = self.memory_service.get_novel_version(
                        stored_novel_id
                    )
                    logger.info(f"小说 {stored_novel_id} 信息已重新加载")

            if novel_info and "error" not in novel_info:
                # 按需加载章节内容：根据用户消息识别需要加载的章节范围
                total_chapters = novel_info.get("chapter_count", 0) or len(
                    novel_info.get("chapters", [])
                )
                chapter_range_needed = self._extract_chapter_range(user_message, total_chapters)

                # 检查当前已加载的章节范围
                current_range = session.context.get("chapter_range", {})
                current_start = current_range.get("start", 1)
                current_end = current_range.get("end", 0)

                # 如果需要加载新范围且与当前范围不同
                if chapter_range_needed:
                    need_start, need_end = chapter_range_needed
                    # 检查是否需要重新加载（范围不同）
                    if need_start != current_start or need_end != current_end:
                        logger.info(f"按需加载章节内容: {novel_id}, 范围 {need_start}-{need_end}")
                        # 重新加载指定范围的章节内容
                        novel_info = await self.get_novel_info(
                            novel_id, need_start, need_end, force_db=True
                        )
                        session.context["novel_info"] = novel_info
                        session.context["chapter_range"] = {"start": need_start, "end": need_end}

                # 检查用户是否询问世界观相关问题
                is_worldview_question = any(
                    keyword in user_message
                    for keyword in [
                        "世界观",
                        "世界设定",
                        "背景",
                        "修炼体系",
                        "地理环境",
                        "势力划分",
                    ]
                )

                if session.scene == SCENE_NOVEL_REVISION:
                    # 分析用户修订意图
                    revision_type = self._analyze_revision_intent(user_message)

                    # 检查是否需要生成修订计划
                    pending_plan_id = session.context.get("pending_revision_plan_id")
                    is_confirming_revision = user_message.lower() in [
                        "是",
                        "好",
                        "可以",
                        "确认",
                        "执行",
                        "yes",
                        "ok",
                        "confirm",
                    ]
                    is_rejecting_revision = user_message.lower() in [
                        "否",
                        "不",
                        "算了",
                        "取消",
                        "no",
                        "cancel",
                    ]

                    if pending_plan_id and is_confirming_revision:
                        # 用户确认执行修订
                        from .revision_execution_service import RevisionExecutionService

                        execution_service = RevisionExecutionService(db=self.db)
                        try:
                            exec_result = await execution_service.execute_plan(pending_plan_id)
                            if exec_result.success:
                                prompt = f"修订计划已执行：{exec_result.message}"
                            else:
                                prompt = f"修订计划执行失败：{exec_result.message}"
                        except Exception as e:
                            logger.error(f"执行修订计划 {pending_plan_id} 失败: {e}")
                            prompt = f"修订计划执行过程中出现错误：{str(e)}"
                        session.context["pending_revision_plan_id"] = None
                    elif is_rejecting_revision:
                        # 用户拒绝修订
                        session.context["pending_revision_plan_id"] = None
                        prompt = "好的，已取消本次修订。"
                    elif revision_type == "specific_revision":
                        # 用户有明确的修订指令，调用parse_natural_revision解析并执行
                        try:
                            parse_result = await self.parse_natural_revision(
                                novel_id=novel_info.get("id"), instruction=user_message
                            )
                            if parse_result.get("preview"):
                                preview = parse_result["preview"]
                                # 直接执行修订
                                execute_result = await self.execute_revision(
                                    novel_id=novel_info.get("id"), preview_id=preview["preview_id"]
                                )
                                if execute_result.get("success"):
                                    return f"✅ 修订完成：{execute_result.get('message', '修订已成功执行')}"
                                else:
                                    return (
                                        f"修订执行失败：{execute_result.get('error', '未知错误')}"
                                    )
                            else:
                                # 解析失败，返回消息
                                return parse_result.get(
                                    "message", "抱歉，我无法理解您的修订指令，请换一种表达方式。"
                                )
                        except Exception as e:
                            logger.error(f"执行自然语言修订失败: {e}")
                            return f"抱歉，处理您的修订请求时出现错误：{str(e)}"
                    else:
                        # 检测是否是需要生成修订计划的反馈
                        revision_keywords = [
                            "有问题",
                            "不对",
                            "不满意",
                            "修改",
                            "调整",
                            "改一下",
                            "性格",
                            "不一致",
                            "矛盾",
                        ]
                        needs_plan = any(keyword in user_message for keyword in revision_keywords)

                        if needs_plan and revision_type in [
                            "character_revision",
                            "chapter_revision",
                            "plot_revision",
                        ]:
                            # 使用修订理解服务生成计划
                            try:
                                plan = await self.revision_service.understand_feedback(
                                    user_feedback=user_message,
                                    novel_id=novel_info.get("id"),
                                )
                                session.context["pending_revision_plan_id"] = str(plan.id)
                                plan_display = self.revision_service.format_plan_for_display(plan)
                                session.add_assistant_message(plan_display)
                                import asyncio

                                asyncio.create_task(self.save_session(session))
                                return plan_display
                            except Exception as e:
                                logger.warning(f"生成修订计划失败: {e}")
                                prompt = self._generate_revision_prompt(
                                    user_message, revision_type, novel_info
                                )
                        else:
                            prompt = self._generate_revision_prompt(
                                user_message, revision_type, novel_info
                            )

                    # 生成并存储分析结果到记忆服务
                    analysis = self._analyze_novel_content(novel_info)
                    novel_id = novel_info.get("id")
                    if novel_id:
                        # 更新记忆服务中的分析结果
                        current_memory = self.memory_service.get_novel_memory(novel_id)
                        if current_memory:
                            current_memory["analysis"] = analysis
                            self.memory_service.set_novel_memory(novel_id, current_memory)
                        else:
                            # 如果记忆中没有，创建新的记忆
                            novel_info["analysis"] = analysis
                            self.memory_service.set_novel_memory(novel_id, novel_info)
                elif session.scene == SCENE_NOVEL_ANALYSIS:
                    # 生成小说分析提示词
                    analysis = session.context.get(
                        "analysis", self._analyze_novel_content(novel_info)
                    )

                    prompt = f"# 用户分析需求\n{user_message}\n"
                    prompt += "\n# 小说分析\n"
                    prompt += "## 小说概览\n"
                    prompt += f"- 标题: {novel_info.get('title', '未知')}\n"
                    prompt += f"- 类型: {novel_info.get('genre', '未知')}\n"
                    prompt += f"- 章节数: {novel_info.get('chapter_count', 0)}\n"
                    prompt += f"- 字数: {novel_info.get('word_count', 0)}\n"

                    # 特别添加世界观信息
                    if is_worldview_question and novel_info.get("world_setting"):
                        prompt += "\n## 世界观信息\n"
                        world_content = novel_info.get("world_setting", {}).get("content", "") or ""
                        if len(world_content) > 500:
                            # 提取关键信息
                            key_points = []
                            lines = world_content.split("\n")
                            for line in lines:
                                if line.strip() and len(" ".join(key_points)) < 400:
                                    key_points.append(line.strip())
                            prompt += "\n".join(key_points[:8]) + "...\n"
                        else:
                            prompt += world_content + "\n"

                    if analysis:
                        if analysis.get("strengths"):
                            prompt += "\n## 优势\n"
                            for strength in analysis["strengths"]:
                                prompt += f"- {strength}\n"
                        if analysis.get("weaknesses"):
                            prompt += "\n## 不足\n"
                            for weakness in analysis["weaknesses"]:
                                prompt += f"- {weakness}\n"
                        if analysis.get("suggestions"):
                            prompt += "\n## 建议\n"
                            for suggestion in analysis["suggestions"]:
                                prompt += f"- {suggestion}\n"
                        if analysis.get("genre_specific"):
                            prompt += "\n## 类型特定建议\n"
                            for suggestion in analysis["genre_specific"]:
                                prompt += f"- {suggestion}\n"

                    # 添加持久化记忆上下文
                    persistent_context = self._get_persistent_memory_context(novel_id)
                    if persistent_context:
                        prompt += "\n# 持久化记忆上下文\n"
                        prompt += persistent_context + "\n"

                    prompt += "\n# 回复指导\n"
                    prompt += "请根据用户的具体问题自然地回复：\n"
                    prompt += "- 如果用户问的是简单问题，直接简洁回答\n"
                    prompt += "- 如果用户需要全面分析，再提供详细的分析结果\n"
                    prompt += "- 回复要贴合用户的问题意图，不要拘泥于固定格式\n"

        response = await self.client.chat(
            prompt=prompt,
            system=system_prompt,
            temperature=0.8,
        )

        assistant_message = response.get("content", "抱歉，我暂时无法回答这个问题。")

        # 生成后续问题
        follow_up_questions = self._generate_follow_up_questions(
            user_intent, session.scene, session.context.get("novel_info")
        )
        if follow_up_questions:
            assistant_message += f"\n\n为了进一步帮助你，我可以：{follow_up_questions[0]}"

        session.add_assistant_message(assistant_message)

        # 异步保存会话到数据库
        import asyncio

        asyncio.create_task(self.save_session(session))

        # 如果会话没有标题，异步生成标题
        if not session.title:
            asyncio.create_task(self._update_session_title(session))

        logger.info(f"会话 {session_id} 收到用户消息: {user_message[:50]}...")

        return assistant_message

    async def send_message_stream(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        session.add_user_message(user_message)

        # 分析用户意图
        user_intent = await self._analyze_user_intent(user_message, session.scene)
        session.set_last_user_intent(user_intent)

        # 检查是否需要澄清
        # 如果是小说相关场景且包含小说信息，直接回答而不澄清
        is_novel_related = session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]
        has_novel_info = session.context.get(
            "novel_info", {}
        ) and "error" not in session.context.get("novel_info", {})

        # 只有在非小说场景或没有小说信息时才需要澄清
        need_clarification = self._check_need_clarification(user_message, session.scene)
        if is_novel_related and has_novel_info:
            # 有小说信息时，不需要澄清，直接基于小说信息回答
            need_clarification = False

        if need_clarification:
            # 生成追问
            follow_up_questions = self._generate_follow_up_questions(
                user_intent, session.scene, session.context.get("novel_info")
            )
            session.add_follow_up_question(follow_up_questions[0] if follow_up_questions else "")

            # 生成追问回复
            clarification_message = "为了给你提供更准确的帮助，我需要了解更多信息。"
            if follow_up_questions:
                clarification_message += f" {follow_up_questions[0]}"

            session.add_assistant_message(clarification_message)
            logger.info(f"会话 {session_id} 需要澄清: {user_message[:50]}...")

            # 保存会话到数据库
            await self.save_session(session)

            yield clarification_message
            return

        session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)

        # 如果是章节助手场景，添加章节内容到系统提示词
        if session.scene == SCENE_CHAPTER_ASSISTANT:
            current_chapter = session.context.get("current_chapter", {})
            logger.info(
                f"章节助手场景检查: current_chapter存在={bool(current_chapter)}, keys={list(current_chapter.keys()) if current_chapter else 'empty'}"
            )
            if current_chapter and "error" not in current_chapter:
                chapter_num = current_chapter.get("chapter_number", "?")
                chapter_title = current_chapter.get("title", f"第{chapter_num}章")
                chapter_content = current_chapter.get("content", "")
                system_prompt = f"""{system_prompt}

---
**当前章节内容（第{chapter_num}章：{chapter_title}）**：

{chapter_content}
---"""
                logger.info(
                    f"章节助手流式消息: 已将第{chapter_num}章内容添加到系统提示词, 内容长度={len(chapter_content)}"
                )
            else:
                logger.warning(
                    f"章节助手场景: current_chapter为空或包含错误, current_chapter={type(current_chapter)}, error={'error' in current_chapter if current_chapter else 'N/A'}"
                )

        # 如果是小说相关场景，添加小说信息到提示词
        prompt = user_message
        if session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]:
            novel_info = session.context.get("novel_info", {})
            if novel_info and "error" not in novel_info:
                # 检查用户是否询问世界观相关问题
                is_worldview_question = any(
                    keyword in user_message
                    for keyword in [
                        "世界观",
                        "世界设定",
                        "背景",
                        "修炼体系",
                        "地理环境",
                        "势力划分",
                    ]
                )

                if session.scene == SCENE_NOVEL_REVISION:
                    # 分析用户修订意图
                    revision_type = self._analyze_revision_intent(user_message)

                    # 检查是否需要生成修订计划
                    pending_plan_id = session.context.get("pending_revision_plan_id")
                    is_confirming_revision = user_message.lower() in [
                        "是",
                        "好",
                        "可以",
                        "确认",
                        "执行",
                        "yes",
                        "ok",
                        "confirm",
                    ]
                    is_rejecting_revision = user_message.lower() in [
                        "否",
                        "不",
                        "算了",
                        "取消",
                        "no",
                        "cancel",
                    ]

                    if pending_plan_id and is_confirming_revision:
                        # 用户确认执行修订
                        from .revision_execution_service import RevisionExecutionService

                        execution_service = RevisionExecutionService(db=self.db)
                        try:
                            exec_result = await execution_service.execute_plan(pending_plan_id)
                            if exec_result.success:
                                prompt = f"修订计划已执行：{exec_result.message}"
                            else:
                                prompt = f"修订计划执行失败：{exec_result.message}"
                        except Exception as e:
                            logger.error(f"执行修订计划 {pending_plan_id} 失败: {e}")
                            prompt = f"修订计划执行过程中出现错误：{str(e)}"
                        session.context["pending_revision_plan_id"] = None
                    elif is_rejecting_revision:
                        # 用户拒绝修订
                        session.context["pending_revision_plan_id"] = None
                        prompt = "好的，已取消本次修订。"
                    elif revision_type == "specific_revision":
                        # 用户有明确的修订指令，调用parse_natural_revision解析并执行
                        try:
                            parse_result = await self.parse_natural_revision(
                                novel_id=novel_info.get("id"), instruction=user_message
                            )
                            if parse_result.get("preview"):
                                preview = parse_result["preview"]
                                # 直接执行修订
                                execute_result = await self.execute_revision(
                                    novel_id=novel_info.get("id"), preview_id=preview["preview_id"]
                                )
                                if execute_result.get("success"):
                                    yield f"✅ 修订完成：{execute_result.get('message', '修订已成功执行')}"
                                    return
                                else:
                                    yield f"修订执行失败：{execute_result.get('error', '未知错误')}"
                                    return
                            else:
                                # 解析失败，返回消息
                                yield parse_result.get(
                                    "message", "抱歉，我无法理解您的修订指令，请换一种表达方式。"
                                )
                                return
                        except Exception as e:
                            logger.error(f"执行自然语言修订失败: {e}")
                            yield f"抱歉，处理您的修订请求时出现错误：{str(e)}"
                            return
                    else:
                        # 检测是否是需要生成修订计划的反馈
                        revision_keywords = [
                            "有问题",
                            "不对",
                            "不满意",
                            "修改",
                            "调整",
                            "改一下",
                            "性格",
                            "不一致",
                            "矛盾",
                        ]
                        needs_plan = any(keyword in user_message for keyword in revision_keywords)

                        if needs_plan and revision_type in [
                            "character_revision",
                            "chapter_revision",
                            "plot_revision",
                        ]:
                            # 使用修订理解服务生成计划
                            try:
                                plan = await self.revision_service.understand_feedback(
                                    user_feedback=user_message,
                                    novel_id=novel_info.get("id"),
                                )
                                session.context["pending_revision_plan_id"] = str(plan.id)
                                plan_display = self.revision_service.format_plan_for_display(plan)
                                session.add_assistant_message(plan_display)
                                import asyncio

                                asyncio.create_task(self.save_session(session))
                                yield plan_display
                                return
                            except Exception as e:
                                logger.warning(f"生成修订计划失败: {e}")
                                prompt = self._generate_revision_prompt(
                                    user_message, revision_type, novel_info
                                )
                        else:
                            prompt = self._generate_revision_prompt(
                                user_message, revision_type, novel_info
                            )

                    # 生成并存储分析结果到记忆服务
                    analysis = self._analyze_novel_content(novel_info)
                    novel_id = novel_info.get("id")
                    if novel_id:
                        # 更新记忆服务中的分析结果
                        current_memory = self.memory_service.get_novel_memory(novel_id)
                        if current_memory:
                            current_memory["analysis"] = analysis
                            self.memory_service.set_novel_memory(novel_id, current_memory)
                        else:
                            # 如果记忆中没有，创建新的记忆
                            novel_info["analysis"] = analysis
                            self.memory_service.set_novel_memory(novel_id, novel_info)
                elif session.scene == SCENE_NOVEL_ANALYSIS:
                    # 生成小说分析提示词
                    analysis = session.context.get(
                        "analysis", self._analyze_novel_content(novel_info)
                    )

                    prompt = f"# 用户分析需求\n{user_message}\n"
                    prompt += "\n# 小说分析\n"
                    prompt += "## 小说概览\n"
                    prompt += f"- 标题: {novel_info.get('title', '未知')}\n"
                    prompt += f"- 类型: {novel_info.get('genre', '未知')}\n"
                    prompt += f"- 章节数: {novel_info.get('chapter_count', 0)}\n"
                    prompt += f"- 字数: {novel_info.get('word_count', 0)}\n"

                    # 特别添加世界观信息
                    if is_worldview_question and novel_info.get("world_setting"):
                        prompt += "\n## 世界观信息\n"
                        world_content = novel_info.get("world_setting", {}).get("content", "") or ""
                        if len(world_content) > 500:
                            # 提取关键信息
                            key_points = []
                            lines = world_content.split("\n")
                            for line in lines:
                                if line.strip() and len(" ".join(key_points)) < 400:
                                    key_points.append(line.strip())
                            prompt += "\n".join(key_points[:8]) + "...\n"
                        else:
                            prompt += world_content + "\n"

                    if analysis:
                        if analysis.get("strengths"):
                            prompt += "\n## 优势\n"
                            for strength in analysis["strengths"]:
                                prompt += f"- {strength}\n"
                        if analysis.get("weaknesses"):
                            prompt += "\n## 不足\n"
                            for weakness in analysis["weaknesses"]:
                                prompt += f"- {weakness}\n"
                        if analysis.get("suggestions"):
                            prompt += "\n## 建议\n"
                            for suggestion in analysis["suggestions"]:
                                prompt += f"- {suggestion}\n"
                        if analysis.get("genre_specific"):
                            prompt += "\n## 类型特定建议\n"
                            for suggestion in analysis["genre_specific"]:
                                prompt += f"- {suggestion}\n"

                    # 添加持久化记忆上下文
                    novel_id = novel_info.get("id")
                    if novel_id:
                        persistent_context = self._get_persistent_memory_context(novel_id)
                        if persistent_context:
                            prompt += "\n# 持久化记忆上下文\n"
                            prompt += persistent_context + "\n"

                    prompt += "\n# 回复指导\n"
                    prompt += "请根据用户的具体问题自然地回复：\n"
                    prompt += "- 如果用户问的是简单问题，直接简洁回答\n"
                    prompt += "- 如果用户需要全面分析，再提供详细的分析结果\n"
                    prompt += "- 回复要贴合用户的问题意图，不要拘泥于固定格式\n"

        full_response = ""

        try:
            async for chunk in self.client.stream_chat(
                prompt=prompt,
                system=system_prompt,
                temperature=0.8,
            ):
                full_response += chunk
                yield chunk

            # 生成后续问题
            follow_up_questions = self._generate_follow_up_questions(
                user_intent, session.scene, session.context.get("novel_info")
            )
            if follow_up_questions:
                follow_up_text = f"\n\n为了进一步帮助你，我可以：{follow_up_questions[0]}"
                full_response += follow_up_text
                yield follow_up_text

            session.add_assistant_message(full_response)
            logger.info(f"会话 {session_id} 流式响应完成，共 {len(full_response)} 字符")

            # 保存会话到数据库
            await self.save_session(session)

            # 如果会话没有标题，异步生成标题
            if not session.title:
                import asyncio

                asyncio.create_task(self._update_session_title(session))

        except Exception as e:
            logger.error(f"流式响应出错: {e}", exc_info=True)
            error_msg = "抱歉，响应生成过程中出现错误，请稍后重试。"
            yield error_msg
            session.add_assistant_message(error_msg)
            try:
                await self.save_session(session)
            except Exception as save_error:
                logger.error(f"保存会话失败: {save_error}")

    async def parse_novel_intent(self, user_input: str) -> dict:
        """解析小说创建意图，将用户自然语言转换为结构化数据."""

        parse_prompt = f"""请分析以下用户输入，提取小说创建所需的信息。
请以 JSON 格式返回结果，包含以下字段（如果没有相关信息则为空字符串或空列表）：
- title: 小说标题建议
- genre: 小说类型（必须是以下之一：{', '.join(NOVEL_GENRES)}）
- tags: 标签列表
- synopsis: 简介/大纲

用户输入：{user_input}

请只返回 JSON，不要其他内容。"""

        try:
            response = await self.client.chat(
                prompt=parse_prompt,
                system="你是一个信息提取助手，请从用户输入中提取结构化信息。",
                temperature=0.3,
            )

            content = response.get("content", "{}")

            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            validated_result = {
                "title": result.get("title", ""),
                "genre": (result.get("genre", "") if result.get("genre") in NOVEL_GENRES else ""),
                "tags": result.get("tags", []),
                "synopsis": result.get("synopsis", ""),
            }

            logger.info(f"小说意图解析结果: {validated_result}")
            return validated_result

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, content: {content}")
            return {"title": "", "genre": "", "tags": [], "synopsis": ""}
        except Exception as e:
            logger.error(f"小说意图解析失败: {e}")
            return {"title": "", "genre": "", "tags": [], "synopsis": ""}

    async def parse_crawler_intent(self, user_input: str) -> dict:
        """解析爬虫任务意图，将用户自然语言转换为结构化数据."""

        parse_prompt = f"""请分析以下用户输入，提取爬虫任务创建所需的信息。
请以 JSON 格式返回结果，包含以下字段：
- crawl_type: 爬取类型（必须是以下之一：{', '.join(CRAWLER_TYPES)}）
- ranking_type: 排行榜类型（必须是以下之一：{', '.join(RANKING_TYPES)}），仅当 crawl_type 为 ranking 时有效
- max_pages: 最大页数（数字）
- book_ids: 书籍ID列表（字符串，逗号分隔），仅当 crawl_type 为 book_metadata 时有效

用户输入：{user_input}

请只返回 JSON，不要其他内容。"""

        try:
            response = await self.client.chat(
                prompt=parse_prompt,
                system="你是一个信息提取助手，请从用户输入中提取结构化信息。",
                temperature=0.3,
            )

            content = response.get("content", "{}")

            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            crawl_type = result.get("crawl_type", "")
            if crawl_type not in CRAWLER_TYPES:
                if "排行" in user_input or "榜" in user_input:
                    crawl_type = "ranking"
                elif "标签" in user_input:
                    crawl_type = "trending_tags"
                elif "书籍" in user_input or "详情" in user_input:
                    crawl_type = "book_metadata"
                elif "分类" in user_input:
                    crawl_type = "genre_list"
                else:
                    crawl_type = ""

            validated_result = {
                "crawl_type": crawl_type,
                "ranking_type": (
                    result.get("ranking_type", "")
                    if result.get("ranking_type") in RANKING_TYPES
                    else "yuepiao"
                ),
                "max_pages": result.get("max_pages", 3),
                "book_ids": result.get("book_ids", ""),
            }

            logger.info(f"爬虫意图解析结果: {validated_result}")
            return validated_result

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, content: {content}")
            return {
                "crawl_type": "",
                "ranking_type": "yuepiao",
                "max_pages": 3,
                "book_ids": "",
            }
        except Exception as e:
            logger.error(f"爬虫意图解析失败: {e}")
            return {
                "crawl_type": "",
                "ranking_type": "yuepiao",
                "max_pages": 3,
                "book_ids": "",
            }

    async def extract_structured_suggestions(
        self, ai_response: str, novel_info: dict, revision_type: str
    ) -> List[Dict[str, Any]]:
        """从AI响应中提取结构化的修订建议.

        Args:
            ai_response: AI的回复文本
            novel_info: 小说信息
            revision_type: 修订类型 (world_setting, character, outline, chapter, general)

        Returns:
            结构化建议列表
        """
        extract_prompt = f"""请分析以下AI修订建议，提取出具体的、可执行的修改建议。

AI修订建议内容：
{ai_response[:3000]}

小说当前信息：
- 标题: {novel_info.get('title', '未知')}
- 类型: {novel_info.get('genre', '未知')}
- 修订类型: {revision_type}

当前角色列表：
{json.dumps([{'id': c.get('id'), 'name': c.get('name')} for c in novel_info.get('characters', [])[:10]], ensure_ascii=False)}

当前章节列表：
{json.dumps([{'chapter_number': c.get('chapter_number'), 'title': c.get('title')} for c in novel_info.get('chapters', [])[:10]], ensure_ascii=False)}

请以JSON数组格式返回提取的建议，每个建议包含以下字段：
- type: 建议类型（novel/world_setting/character/outline/chapter）
- target_id: 目标对象ID（如角色ID、章节号），如果是小说基本信息、世界观或大纲则为null
  * 对于角色类型，target_id 必须是上面「当前角色列表」中已存在角色的真实UUID，不要使用虚拟标识符如'new_xxx'
  * 如果建议创建新角色，请忽略该建议，只针对已存在的角色提供修订建议
- target_name: 目标对象名称（如角色名、章节标题）
- field: 要修改的字段名，必须使用以下有效字段名：
  * 小说基本信息(novel): title, author, synopsis, genre, tags, status, length_type, target_platform
  * 世界观(world_setting): power_system, geography, factions, rules, timeline, special_elements, raw_content
  * 角色(character): name, role_type, gender, age, appearance, personality, background, goals, abilities, relationships, growth_arc
  * 大纲(outline): structure_type, volumes, main_plot, sub_plots, key_turning_points, climax_chapter, raw_content
  * 章节(chapter): title, content, outline
- suggested_value: 建议的新值（简洁明了，不超过500字）
- description: 修改描述（说明为什么要这样修改）
- confidence: 置信度（0-1之间的数字）

只返回JSON数组，不要其他内容。如果没有可提取的具体建议，返回空数组[]。"""

        try:
            response = await self.client.chat(
                prompt=extract_prompt,
                system="你是一个专业的文本分析助手，擅长从文本中提取结构化信息。请准确提取修订建议中的具体修改内容。",
                temperature=0.3,
            )

            content = response.get("content", "[]")
            content = content.strip()

            # 清理JSON格式
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            suggestions = json.loads(content)

            # 验证和清理建议
            valid_suggestions = []
            for suggestion in suggestions:
                if isinstance(suggestion, dict) and suggestion.get("type") in [
                    "novel",
                    "world_setting",
                    "character",
                    "outline",
                    "chapter",
                ]:
                    valid_suggestions.append(
                        {
                            "type": suggestion.get("type"),
                            "target_id": suggestion.get("target_id"),
                            "target_name": suggestion.get("target_name"),
                            "field": suggestion.get("field"),
                            "suggested_value": suggestion.get("suggested_value", "")[
                                :2000
                            ],  # 限制长度
                            "description": suggestion.get("description", "")[:500],
                            "confidence": min(max(float(suggestion.get("confidence", 0.7)), 0), 1),
                        }
                    )

            logger.info(f"提取到 {len(valid_suggestions)} 条结构化建议")
            return valid_suggestions

        except json.JSONDecodeError as e:
            logger.error(f"提取结构化建议时JSON解析失败: {e}")
            return []
        except Exception as e:
            logger.error(f"提取结构化建议失败: {e}")
            return []

    async def apply_suggestion_to_database(
        self, novel_id: str, suggestion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将单个修订建议应用到数据库.

        Args:
            novel_id: 小说ID
            suggestion: 结构化建议

        Returns:
            应用结果
        """
        from core.database import async_session_factory
        from core.models.chapter import Chapter
        from core.models.character import Character
        from core.models.novel import Novel
        from core.models.plot_outline import PlotOutline
        from core.models.world_setting import WorldSetting

        suggestion_type = suggestion.get("type")
        field = suggestion.get("field")
        suggested_value = suggestion.get("suggested_value")
        target_id = suggestion.get("target_id")
        target_name = suggestion.get("target_name")

        # 详细日志：输出建议内容
        logger.info(
            f"应用建议: type={suggestion_type}, field={field}, target_id={target_id}, target_name={target_name}, value_length={len(str(suggested_value)) if suggested_value else 0}"
        )

        if not field or not suggested_value:
            error_msg = f"缺少必要的字段或建议值: field={field}, suggested_value={suggested_value}"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}

        # 处理建议值：确保 JSONB 字段使用正确的数据结构
        # 如果是字符串，需要包装成 dict 或 list
        if isinstance(suggested_value, str):
            # 需要 dict 的字段
            dict_fields = [
                "power_system",
                "geography",
                "abilities",
                "relationships",
                "growth_arc",
                "main_plot",
            ]
            # 需要 list 的字段（关键结构化数据）
            list_fields = [
                "factions",
                "rules",
                "timeline",
                "special_elements",
                "volumes",
                "sub_plots",
                "key_turning_points",
            ]

            if field in dict_fields:
                # 尝试解析 JSON 字符串
                try:
                    parsed = json.loads(suggested_value)
                    if isinstance(parsed, dict):
                        suggested_value = parsed
                    else:
                        suggested_value = {"content": suggested_value}
                except json.JSONDecodeError:
                    suggested_value = {"content": suggested_value}
            elif field in list_fields:
                # 对于关键的 list 字段，拒绝简单的字符串替换
                # 尝试解析 JSON 字符串
                try:
                    parsed = json.loads(suggested_value)
                    if isinstance(parsed, list):
                        suggested_value = parsed
                    else:
                        # 尝试解析多行字典格式
                        import ast

                        items = []
                        for line in suggested_value.strip().split("\n"):
                            line = line.strip()
                            if line.startswith("{") and line.endswith("}"):
                                try:
                                    items.append(ast.literal_eval(line))
                                except (ValueError, SyntaxError):
                                    continue
                        if items:
                            suggested_value = items
                        else:
                            # 无法解析为结构化数据，拒绝更新
                            logger.warning(
                                f"无法将字符串解析为结构化列表数据，拒绝更新字段 {field}"
                            )
                            return {
                                "success": False,
                                "error": f"字段 {field} 需要结构化数据，无法从文本自动解析。请手动编辑。",
                                "skip": True,
                            }
                except json.JSONDecodeError:
                    # 尝试解析多行字典格式
                    import ast

                    items = []
                    for line in suggested_value.strip().split("\n"):
                        line = line.strip()
                        if line.startswith("{") and line.endswith("}"):
                            try:
                                items.append(ast.literal_eval(line))
                            except (ValueError, SyntaxError):
                                continue
                    if items:
                        suggested_value = items
                    else:
                        # 无法解析为结构化数据，拒绝更新
                        logger.warning(f"无法将字符串解析为结构化列表数据，拒绝更新字段 {field}")
                        return {
                            "success": False,
                            "error": f"字段 {field} 需要结构化数据，无法从文本自动解析。请手动编辑。",
                            "skip": True,
                        }

        async with async_session_factory() as db:
            try:
                if suggestion_type == "novel":
                    # 更新小说基本信息
                    query = select(Novel).where(Novel.id == novel_id)
                    result = await db.execute(query)
                    novel = result.scalar_one_or_none()

                    if not novel:
                        return {"success": False, "error": "小说不存在"}

                    # 根据字段更新
                    if hasattr(novel, field):
                        setattr(novel, field, suggested_value)
                    else:
                        return {"success": False, "error": f"无效的字段: {field}"}

                    await db.commit()
                    logger.info(f"已更新小说 {novel_id} 的字段 {field}")
                    return {"success": True, "type": "novel", "field": field}

                elif suggestion_type == "world_setting":
                    # 更新世界观设定
                    query = select(WorldSetting).where(WorldSetting.novel_id == novel_id)
                    result = await db.execute(query)
                    world_setting = result.scalar_one_or_none()

                    if not world_setting:
                        return {"success": False, "error": "世界观设定不存在"}

                    # 根据字段更新
                    if field == "raw_content" or field == "content":
                        world_setting.raw_content = suggested_value
                    elif hasattr(world_setting, field):
                        setattr(world_setting, field, suggested_value)
                    else:
                        return {"success": False, "error": f"无效的字段: {field}"}

                    await db.commit()
                    logger.info(f"已更新小说 {novel_id} 的世界观设定字段 {field}")
                    return {"success": True, "type": "world_setting", "field": field}

                elif suggestion_type == "character":
                    # 更新角色信息
                    # 检查是否是创建新角色的建议（target_id 为虚拟标识符）
                    if target_id and (target_id.startswith("new_") or len(target_id) < 32):
                        # 这是创建新角色的建议，跳过
                        logger.warning(f"跳过创建新角色的建议: {target_name}, 需要手动创建角色")
                        return {
                            "success": False,
                            "error": f"请先创建角色: {target_name}，然后再应用修订建议",
                            "skip": True,
                        }

                    if target_id:
                        query = select(Character).where(
                            Character.id == target_id, Character.novel_id == novel_id
                        )
                    elif target_name:
                        query = select(Character).where(
                            Character.name == target_name,
                            Character.novel_id == novel_id,
                        )
                    else:
                        return {"success": False, "error": "需要指定角色ID或角色名称"}

                    result = await db.execute(query)
                    character = result.scalar_one_or_none()

                    if not character:
                        return {
                            "success": False,
                            "error": f"角色不存在: {target_name or target_id}",
                        }

                    if hasattr(character, field):
                        setattr(character, field, suggested_value)
                    else:
                        return {"success": False, "error": f"无效的字段: {field}"}

                    await db.commit()
                    logger.info(f"已更新角色 {character.name} 的字段 {field}")
                    return {
                        "success": True,
                        "type": "character",
                        "character_name": character.name,
                        "field": field,
                    }

                elif suggestion_type == "outline":
                    # 更新大纲
                    query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
                    result = await db.execute(query)
                    plot_outline = result.scalar_one_or_none()

                    if not plot_outline:
                        return {"success": False, "error": "大纲不存在"}

                    if field == "raw_content" or field == "content":
                        plot_outline.raw_content = suggested_value
                    elif hasattr(plot_outline, field):
                        setattr(plot_outline, field, suggested_value)
                    else:
                        return {"success": False, "error": f"无效的字段: {field}"}

                    await db.commit()
                    logger.info(f"已更新小说 {novel_id} 的大纲字段 {field}")
                    return {"success": True, "type": "outline", "field": field}

                elif suggestion_type == "chapter":
                    # 更新章节
                    if target_id:
                        # target_id 可能是章节号
                        try:
                            chapter_number = int(target_id)
                            query = select(Chapter).where(
                                Chapter.chapter_number == chapter_number,
                                Chapter.novel_id == novel_id,
                            )
                        except (ValueError, TypeError):
                            query = select(Chapter).where(
                                Chapter.id == target_id, Chapter.novel_id == novel_id
                            )
                    elif target_name:
                        query = select(Chapter).where(
                            Chapter.title == target_name, Chapter.novel_id == novel_id
                        )
                    else:
                        return {"success": False, "error": "需要指定章节ID或章节标题"}

                    result = await db.execute(query)
                    chapter = result.scalar_one_or_none()

                    if not chapter:
                        return {
                            "success": False,
                            "error": f"章节不存在: {target_name or target_id}",
                        }

                    if hasattr(chapter, field):
                        setattr(chapter, field, suggested_value)
                        # 如果更新了内容，同时更新字数
                        if field == "content" and suggested_value:
                            chapter.word_count = len(suggested_value)
                    else:
                        return {"success": False, "error": f"无效的字段: {field}"}

                    await db.commit()
                    logger.info(f"已更新章节 {chapter.chapter_number} 的字段 {field}")
                    return {
                        "success": True,
                        "type": "chapter",
                        "chapter_number": chapter.chapter_number,
                        "field": field,
                    }

                else:
                    return {
                        "success": False,
                        "error": f"不支持的建议类型: {suggestion_type}",
                    }

            except Exception as e:
                logger.error(f"应用建议到数据库失败: {e}")
                await db.rollback()
                return {"success": False, "error": str(e)}

    async def apply_suggestions_batch(
        self, novel_id: str, suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量应用修订建议到数据库.

        Args:
            novel_id: 小说ID
            suggestions: 建议列表

        Returns:
            批量应用结果
        """
        results = {
            "total": len(suggestions),
            "success_count": 0,
            "failed_count": 0,
            "details": [],
        }

        for suggestion in suggestions:
            result = await self.apply_suggestion_to_database(novel_id, suggestion)
            results["details"].append(result)
            if result.get("success"):
                results["success_count"] += 1
            else:
                results["failed_count"] += 1

        # 应用成功后，使记忆服务缓存失效，确保下次获取最新数据
        if results["success_count"] > 0:
            self.memory_service.invalidate_novel_memory(novel_id)
            # 增加版本号
            current_version = self.memory_service.get_novel_version(novel_id)
            self.memory_service.version_map[novel_id] = current_version + 1
            logger.info(f"已使小说 {novel_id} 的记忆缓存失效，版本号更新为 {current_version + 1}")

        return results

    async def get_novel_characters(self, novel_id: str) -> List[Dict[str, Any]]:
        """获取小说的所有角色.

        Args:
            novel_id: 小说ID

        Returns:
            角色列表
        """
        from core.database import async_session_factory
        from core.models.character import Character

        async with async_session_factory() as db:
            try:
                query = (
                    select(Character)
                    .where(Character.novel_id == novel_id)
                    .order_by(Character.created_at)
                )
                result = await db.execute(query)
                characters = result.scalars().all()

                return [
                    {
                        "id": str(char.id),
                        "name": char.name,
                        "role_type": (
                            char.role_type.value
                            if hasattr(char.role_type, "value")
                            else char.role_type
                        ),
                        "personality": char.personality,
                        "background": char.background,
                    }
                    for char in characters
                ]
            except Exception as e:
                logger.error(f"获取角色列表失败: {e}")
                return []

    async def get_novel_chapters(self, novel_id: str) -> List[Dict[str, Any]]:
        """获取小说的所有章节.

        Args:
            novel_id: 小说ID

        Returns:
            章节列表
        """
        from core.database import async_session_factory
        from core.models.chapter import Chapter

        async with async_session_factory() as db:
            try:
                query = (
                    select(Chapter)
                    .where(Chapter.novel_id == novel_id)
                    .order_by(Chapter.chapter_number)
                )
                result = await db.execute(query)
                chapters = result.scalars().all()

                return [
                    {
                        "id": str(chap.id),
                        "chapter_number": chap.chapter_number,
                        "title": chap.title,
                        "word_count": chap.word_count,
                        "status": (
                            chap.status.value if hasattr(chap.status, "value") else chap.status
                        ),
                    }
                    for chap in chapters
                ]
            except Exception as e:
                logger.error(f"获取章节列表失败：{e}")
                return []

    # ==================== 小说对话流程集成方法 ====================

    async def start_novel_dialogue_flow(self, session_id: str, scene: str = "create") -> str:
        """启动小说对话流程（创建/查询/修改）.

        Args:
            session_id: 会话 ID
            scene: 场景类型 (create/query/revise)

        Returns:
            欢迎消息
        """
        from backend.schemas.novel_creation_flow import NovelDialogueScene
        from backend.services.novel_creation_flow_manager import (
            NovelCreationFlowManager,
        )

        # 映射场景字符串到枚举
        scene_mapping = {
            "create": NovelDialogueScene.CREATE,
            "query": NovelDialogueScene.QUERY,
            "revise": NovelDialogueScene.REVISE,
            "novel_creation": NovelDialogueScene.CREATE,
            "novel_query": NovelDialogueScene.QUERY,
            "novel_revision": NovelDialogueScene.REVISE,
        }

        flow_scene = scene_mapping.get(scene, NovelDialogueScene.CREATE)

        # 初始化流程
        flow_manager = NovelCreationFlowManager(self.db, self.client)
        await flow_manager.initialize_flow(session_id, flow_scene)

        # 根据场景返回不同的欢迎消息
        if flow_scene == NovelDialogueScene.CREATE:
            return """您好！我是您的小说创作助手📚.

我将通过对话帮您完成小说的创建，包括：
✅ 确认小说类型
✅ 构建世界观设定
✅ 提炼核心简介
✅ 自动生成创建请求

让我们开始吧！请告诉我：您想创作什么类型的小说呢？

比如：玄幻、科幻、言情、都市、历史、悬疑等"""

        elif flow_scene == NovelDialogueScene.QUERY:
            return """您好！我是您的小说查询助手📖.

我可以帮您查询已有小说的各种信息：
- 📚 基本信息（标题、类型、字数等）
- 🌍 世界观设定（时代、地理、势力、规则等）
- 👥 角色信息（外貌、性格、背景、能力等）
- 📖 剧情大纲（主线、支线、转折点等）
- 📄 章节列表和内容

请告诉我您想查询哪部小说？您可以提供小说 ID、名称或关键词。"""

        elif flow_scene == NovelDialogueScene.REVISE:
            return """您好！我是您的小说修订助手✏️.

我可以帮您通过对话修改小说内容：
- 🌍 修改世界观设定
- 👥 修改角色信息
- 📖 修改剧情大纲
- 📝 修改小说基本信息

请告诉我您想修改哪部小说？"""

        else:
            return "您好！我是您的小说创作助手，请问有什么可以帮助您的？"

    async def process_novel_dialogue_message(self, session_id: str, user_message: str) -> str:
        """处理小说对话流程中的消息.

        Args:
            session_id: 会话 ID
            user_message: 用户消息

        Returns:
            AI 回复消息
        """
        from backend.services.novel_creation_flow_manager import (
            NovelCreationFlowManager,
        )

        flow_manager = NovelCreationFlowManager(self.db, self.client)
        response = await flow_manager.process_message(session_id, user_message)

        # 保存对话历史到 AI 会话
        session = self.get_session(session_id)
        if session:
            session.add_user_message(user_message)
            session.add_assistant_message(response.message)

            # 更新会话上下文
            session.context["flow_state"] = {
                "current_step": response.next_step.value,
                "scene": response.context.scene.value,
                "selected_novel_id": response.context.selected_novel_id,
                "genre": response.context.genre,
                "revision_target": response.context.revision_target,
            }

            # 异步保存会话
            import asyncio

            asyncio.create_task(self.save_session(session))

        return response.message

    # 自然语言修订相关
    # 存储待执行的修订预览
    _revision_previews: dict[str, dict] = {}

    async def parse_natural_revision(self, novel_id: str, instruction: str) -> dict:
        """解析自然语言修订指令.

        Args:
            novel_id: 小说ID
            instruction: 用户指令，如「把主角年龄改成25岁」

        Returns:
            解析结果，包含预览信息和消息
        """
        import uuid

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from core.models.novel import Novel

        # 获取小说信息
        query = select(Novel).where(Novel.id == novel_id).options(selectinload(Novel.characters))
        result = await self.db.execute(query)
        novel = result.scalar_one_or_none()

        if not novel:
            return {
                "preview": None,
                "message": "未找到该小说",
                "needs_confirmation": False,
                "error": "小说不存在",
            }

        # 构建上下文信息
        characters_info = []
        for char in novel.characters:
            role_type = char.role_type or "配角"
            characters_info.append(
                f"角色「{char.name}」(ID:{char.id}): "
                f"类型={role_type}, 性别={char.gender or '未设置'}, "
                f"年龄={char.age or '未设置'}, 职业={char.occupation or '未设置'}"
            )

        characters_text = "\n".join(characters_info) if characters_info else "暂无角色"

        # 使用 LLM 解析指令
        system_prompt = f"""你是一个小说修订指令解析器。

小说信息：
- 小说ID: {novel_id}
- 小说标题: {novel.title}

已有角色列表：
{characters_text}

你的任务是根据用户的自然语言指令，生成一个结构化的修订操作。

支持的指令类型：
1. 修改角色信息：「把XX年龄改成YY」「修改XX的名字为YY」
2. 新增角色：「增加一个配角叫XX」
3. 删除角色：「删除角色XX」
4. 修改小说信息：「把小说名改成XX」

请严格按照以下JSON格式输出（不要有其他内容）：
{{
  "action": "update_field|add|delete",
  "target_type": "character|novel|world_setting|outline",
  "target_name": "角色名或目标名",
  "target_id": "目标ID（如果能找到的话）",
  "field": "要修改的字段名",
  "old_value": "旧值",
  "new_value": "新值",
  "description": "用中文描述这个操作"
}}

如果无法解析指令，返回：
{{
  "action": "unknown",
  "description": "无法理解你的指令，请换一种说法"
}}"""

        try:
            response = await self.client.chat(
                prompt=instruction,
                system=system_prompt,
                temperature=0.3,
                max_tokens=500,
            )

            content = response.get("content", "")

            # 提取 JSON - 改进解析逻辑
            import json
            import re

            # 尝试多种方式解析 JSON
            parsed = None

            # 方式1: 直接解析完整内容
            try:
                parsed = json.loads(content.strip())
            except json.JSONDecodeError:
                pass

            # 方式2: 提取代码块中的 JSON
            if not parsed:
                code_block_match = re.search(
                    r"```(?:json)?\s*([^{}]+\{[^{}]+\}[^{}]*)\$", content, re.DOTALL
                )
                if code_block_match:
                    try:
                        parsed = json.loads(code_block_match.group(1).strip())
                    except json.JSONDecodeError:
                        pass

            # 方式3: 提取普通 JSON 对象
            if not parsed:
                json_match = re.search(r"\{[^{}]+\}", content, re.DOTALL)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass

            # 方式4: 尝试提取最外层的 JSON
            if not parsed:
                try:
                    # 找第一个 { 和最后一个 }
                    start = content.find("{")
                    end = content.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        json_str = content[start : end + 1]
                        parsed = json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            if not parsed:
                logger.warning(f"无法解析LLM响应为JSON: {content[:200]}...")
                parsed = {"action": "unknown", "description": content or "无法解析指令"}

            if parsed.get("action") == "unknown":
                return {
                    "preview": None,
                    "message": parsed.get("description", "无法理解你的指令"),
                    "needs_confirmation": False,
                    "error": None,
                }

            # 如果是 update_field，尝试查找目标角色
            if parsed.get("action") in ["update_field", "delete"]:
                target_name = parsed.get("target_name", "")
                # 忽略「主角」「男主」「女主」等通用称呼，改为查找第一个主角/男主/女主
                if target_name in ["主角", "男主", "女主"]:
                    # 查找对应类型的角色（数据库存储英文枚举值 protagonist）
                    for char in novel.characters:
                        if char.role_type == "protagonist":
                            # "男主"要求性别为male，"女主"要求female，"主角"匹配任意性别
                            if target_name == "男主" and char.gender != "male":
                                continue
                            if target_name == "女主" and char.gender != "female":
                                continue
                            parsed["target_id"] = str(char.id)
                            parsed["target_name"] = char.name
                            break
                else:
                    # 根据名称查找角色
                    for char in novel.characters:
                        if char.name == target_name:
                            parsed["target_id"] = str(char.id)
                            break

                # 获取旧值
                if parsed.get("target_id"):
                    for char in novel.characters:
                        if str(char.id) == parsed["target_id"]:
                            field = parsed.get("field", "")
                            if field == "age":
                                parsed["old_value"] = str(char.age) if char.age else "未设置"
                            elif field == "name":
                                parsed["old_value"] = char.name
                            elif field == "gender":
                                parsed["old_value"] = char.gender or "未设置"
                            elif field == "occupation":
                                parsed["old_value"] = char.occupation or "未设置"
                            elif field == "personality":
                                parsed["old_value"] = char.personality or "未设置"
                            break

            # 生成预览ID
            preview_id = str(uuid.uuid4())

            # 保存预览
            self._revision_previews[preview_id] = {
                "novel_id": novel_id,
                "action": parsed.get("action"),
                "target_type": parsed.get("target_type"),
                "target_name": parsed.get("target_name"),
                "target_id": parsed.get("target_id"),
                "field": parsed.get("field"),
                "old_value": parsed.get("old_value"),
                "new_value": parsed.get("new_value"),
                "description": parsed.get("description"),
            }

            preview = {
                "preview_id": preview_id,
                "action": parsed.get("action"),
                "target_type": parsed.get("target_type"),
                "target_name": parsed.get("target_name"),
                "target_id": parsed.get("target_id"),
                "field": parsed.get("field"),
                "old_value": parsed.get("old_value"),
                "new_value": parsed.get("new_value"),
                "description": parsed.get("description"),
            }

            # 生成确认消息
            action = parsed.get("action")
            target = parsed.get("target_name", "目标")
            field = parsed.get("field", "")
            old_val = parsed.get("old_value", "")
            new_val = parsed.get("new_value", "")

            if action == "update_field":
                msg = f"📝 确认修改：\n- 目标：{target}\n- 字段：{field}\n- {old_val} → {new_val}"
            elif action == "add":
                msg = f"➕ 确认新增：\n- {parsed.get('description', '')}"
            elif action == "delete":
                msg = f"🗑️ 确认删除：\n- {target}\n- {parsed.get('description', '')}"
            else:
                msg = parsed.get("description", "请确认操作")

            return {
                "preview": preview,
                "message": msg,
                "needs_confirmation": True,
                "error": None,
            }

        except Exception as e:
            logger.error(f"解析自然语言修订指令失败: {e}")
            return {
                "preview": None,
                "message": f"解析失败：{str(e)}",
                "needs_confirmation": False,
                "error": str(e),
            }

    async def execute_revision(self, novel_id: str, preview_id: str) -> dict:
        """执行已确认的修订操作.

        Args:
            novel_id: 小说ID
            preview_id: 预览ID

        Returns:
            执行结果
        """
        from sqlalchemy import update

        from core.models.character import Character

        # 获取预览
        preview = self._revision_previews.get(preview_id)
        if not preview:
            return {
                "success": False,
                "message": "预览已过期或不存在，请重新解析指令",
                "error": "预览不存在",
            }

        if preview.get("novel_id") != novel_id:
            return {
                "success": False,
                "message": "小说ID不匹配",
                "error": "小说ID不匹配",
            }

        action = preview.get("action")
        target_id = preview.get("target_id")
        field = preview.get("field")
        new_value = preview.get("new_value")
        target_name = preview.get("target_name", "")

        try:
            if action == "update_field" and target_id:
                # 更新角色字段
                if field == "age":
                    # 年龄转为整数
                    new_val_int = int(new_value) if new_value else None
                    stmt = (
                        update(Character).where(Character.id == target_id).values(age=new_val_int)
                    )
                elif field == "name":
                    stmt = update(Character).where(Character.id == target_id).values(name=new_value)
                elif field == "gender":
                    stmt = (
                        update(Character).where(Character.id == target_id).values(gender=new_value)
                    )
                elif field == "occupation":
                    stmt = (
                        update(Character)
                        .where(Character.id == target_id)
                        .values(occupation=new_value)
                    )
                elif field == "personality":
                    stmt = (
                        update(Character)
                        .where(Character.id == target_id)
                        .values(personality=new_value)
                    )
                else:
                    return {
                        "success": False,
                        "message": f"不支持的字段：{field}",
                        "error": f"不支持的字段：{field}",
                    }

                await self.db.execute(stmt)
                await self.db.commit()

                # 删除预览
                del self._revision_previews[preview_id]

                return {
                    "success": True,
                    "message": f"✅ 已更新「{target_name}」的{field}为「{new_value}」",
                    "action": action,
                    "field": field,
                    "target_name": target_name,
                }

            elif action == "delete" and target_id:
                # 删除角色
                from core.models.character import Character

                stmt = update(Character).where(Character.id == target_id).values(is_deleted=True)
                await self.db.execute(stmt)
                await self.db.commit()

                del self._revision_previews[preview_id]

                return {
                    "success": True,
                    "message": f"✅ 已删除角色「{target_name}」",
                    "action": action,
                    "target_name": target_name,
                }

            else:
                return {
                    "success": False,
                    "message": "暂不支持该操作类型",
                    "error": "不支持的操作类型",
                }

        except Exception as e:
            logger.error(f"执行修订失败: {e}")
            await self.db.rollback()
            return {
                "success": False,
                "message": f"执行失败：{str(e)}",
                "error": str(e),
            }

    async def extract_chapter_modifications(
        self,
        novel_id: str,
        chapter_number: int,
        ai_response: str,
    ) -> dict:
        """从AI响应中提取结构化的章节修改建议.

        使用LLM解析AI响应中的修改建议，返回结构化数据供前端展示和应用。

        Args:
            novel_id: 小说ID
            chapter_number: 章节号
            ai_response: AI助手的回复内容

        Returns:
            包含 suggestions, overall_score, pros, cons 的字典
        """
        extraction_prompt = f"""请从以下AI助手回复中提取章节修改建议，并以JSON格式返回。

AI回复内容:
{ai_response}

请返回以下JSON格式:
{{
    "suggestions": [
        {{
            "type": "replace",
            "position": "第X段" 或 "原文片段",
            "old_text": "要替换的原文（仅replace类型需要）",
            "new_text": "建议的新内容",
            "reason": "修改理由",
            "confidence": 0.85
        }}
    ],
    "overall_score": 8,
    "pros": ["本章优点1", "本章优点2"],
    "cons": ["需要改进的方面1", "需要改进的方面2"]
}}

注意事项：
1. type 只能是 replace、insert 或 append
2. position 描述要具体，方便定位
3. old_text 必须是原文中的精确片段
4. confidence 范围是 0-1
5. overall_score 范围是 1-10

只返回JSON，不要有其他内容。"""

        try:
            response = await self.client.chat(
                prompt=extraction_prompt,
                system="你是一个文本解析专家，擅长从非结构化文本中提取结构化信息。只返回JSON格式的结果。",
                temperature=0.1,
            )

            content = response.get("content", "{}")
            # 尝试清理可能的前缀
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"解析章节修改建议JSON失败: {e}")
            return {"suggestions": [], "error": "解析失败"}
        except Exception as e:
            logger.error(f"提取章节修改建议失败: {e}")
            return {"suggestions": [], "error": str(e)}
