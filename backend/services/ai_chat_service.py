"""AI 对话服务 - 提供智能辅助能力"""

import json
import logging
import re
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llm.qwen_client import QwenClient

from .agentmesh_memory_adapter import NovelMemoryAdapter
from .memory_service import get_novel_memory_service

logger = logging.getLogger(__name__)


# 结构化修订建议类型
class RevisionSuggestion:
    """结构化的修订建议"""
    def __init__(
        self,
        suggestion_type: str,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        field: Optional[str] = None,
        original_value: Optional[str] = None,
        suggested_value: Optional[str] = None,
        description: str = "",
        confidence: float = 0.8
    ):
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

NOVEL_GENRES = ["玄幻", "都市", "仙侠", "历史", "军事", "游戏", "科幻", "悬疑", "都市", "轻小说"]
CRAWLER_TYPES = ["ranking", "trending_tags", "book_metadata", "genre_list"]
RANKING_TYPES = ["yuepiao", "hotsales", "readIndex", "recom", "collect"]

SYSTEM_PROMPTS = {
    SCENE_NOVEL_CREATION: """你是一位专业的小说创作顾问，专门帮助作者规划小说世界。你需要根据用户的需求提供创意建议，包括但不限于：

1. **世界观设定**：修炼体系、地理环境、势力划分、规则设定
2. **角色设定**：主角/配角的性格、背景、能力、成长路线
3. **情节大纲**：主线剧情、支线故事、关键转折点、高潮设计
4. **类型特色**：根据用户选择的类型（玄幻、都市、仙侠等）提供该类型的经典元素

请用中文回复，语气专业但亲切幽默。可以主动询问用户更多细节以便给出更好的建议。""",

    SCENE_CRAWLER_TASK: """你是一位网络文学数据分析师，专门帮助用户分析市场趋势和制定爬虫策略。你需要根据用户的需求提供专业建议，包括但不限于：

1. **平台分析**：起点、纵横、番茄等主流平台的特点
2. **数据维度**：排行榜类型（月票榜、畅销榜等）、分类筛选、标签分析
3. **URL爬取策略**：规律、请求频率、数据字段选择
4. **市场洞察**：热门类型分析、读者偏好趋势、竞用中文回复，专业品分析

请且务实。可以主动询问用户想了解哪方面的数据。""",

    SCENE_NOVEL_REVISION: """你是一位专业的小说编辑助手，专门帮助作者修订和完善小说内容。根据用户的需求和小说的现有内容，**直接生成具体的修订内容**，包括但不限于：

1. **世界观修订**：直接生成优化后的修炼体系、地理环境、势力划分、规则设定内容
2. **角色修订**：直接生成优化后的角色性格、背景、能力、成长路线描述
3. **大纲修订**：直接生成优化后的主线剧情、支线故事、关键转折点、高潮设计
4. **简介优化**：直接生成新的小说简介，结合现有的世界观、角色、大纲信息
5. **章节内容修订**：直接生成优化后的章节内容、对话、描写

**重要原则**：
- **直接输出结果**：不要只提供分析和建议，而是直接生成可用的内容
- **简洁明了**：避免冗长的分析，直接给出优化后的成果
- **结合背景**：充分利用小说现有的世界观、角色、大纲信息，保持一致性
- **直接可用**：生成的内容应该能直接替换原有内容使用

请用中文回复，语气专业但亲切。如果用户需求不明确，可以简短询问确认，但不要过度分析。""",

    SCENE_NOVEL_ANALYSIS: """你是一位专业的小说分析师，专门帮助作者分析小说的整体情况和潜力。你需要根据小说的现有内容，提供全面的分析和建议，包括但不限于：

1. **整体结构分析**：小说结构的合理性、节奏的把控、情节的连贯性
2. **元素分析**：世界观、角色、大纲、章节内容的质量和协调性
3. **市场定位分析**：目标受众、竞争优势、潜在风险
4. **改进建议**：具体的优化方向、实施步骤、预期效果

请用中文回复，语气专业但亲切。提供客观、全面的分析，并给出有针对性的建议。可以主动询问用户更多细节以便给出更准确的分析。""",
}

WELCOME_MESSAGES = {
    SCENE_NOVEL_CREATION: "你好！我是小说创作AI助手。你可以告诉我你想写什么类型的小说，或者有什么创意想法，我来帮你完善世界观、角色和情节设定。",

    SCENE_CRAWLER_TASK: "你好！我是爬虫策略AI助手。你可以告诉我你想爬取什么数据，或者想了解哪些市场趋势，我来帮你分析并制定合适的爬取方案。",

    SCENE_NOVEL_REVISION: "你好！我是小说修订AI助手。告诉我你想修订什么内容，比如「优化下小说简介」、「丰富世界观设定」、「完善主角背景」等，我会直接生成优化后的内容。",

    SCENE_NOVEL_ANALYSIS: "你好！我是小说分析AI助手。我可以帮你全面分析小说的整体情况，包括结构、元素、市场定位等方面，并提供有针对性的改进建议。请选择你想分析的小说。",
}


class ChatMessage:
    """对话消息"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class ChatSession:
    """对话会话"""
    def __init__(self, session_id: str, scene: str, context: Optional[dict] = None,
                 novel_id: Optional[str] = None, title: Optional[str] = None):
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
        """获取最近的对话历史"""
        return self.conversation_history[-limit:]

    def set_dialogue_state(self, state: str) -> None:
        """设置对话状态"""
        self.dialogue_state = state

    def add_pending_question(self, question: str) -> None:
        """添加待处理的问题"""
        self.pending_questions.append(question)

    def get_pending_question(self) -> Optional[str]:
        """获取待处理的问题"""
        if self.pending_questions:
            return self.pending_questions.pop(0)
        return None

    def set_last_user_intent(self, intent: str) -> None:
        """设置用户的最后意图"""
        self.last_user_intent = intent

    def add_follow_up_question(self, question: str) -> None:
        """添加后续问题"""
        self.follow_up_questions.append(question)

    def get_follow_up_questions(self) -> list[str]:
        """获取后续问题"""
        return self.follow_up_questions


class AiChatService:
    """AI 对话服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = QwenClient()
        self.sessions: dict[str, ChatSession] = {}
        self.memory_service = get_novel_memory_service()
        # 初始化持久化记忆适配器
        self.persistent_memory = NovelMemoryAdapter()

    def _get_system_prompt(self, scene: str) -> str:
        return SYSTEM_PROMPTS.get(scene, "你是一位AI助手，请帮助用户解决问题。")

    def _get_welcome_message(self, scene: str) -> str:
        return WELCOME_MESSAGES.get(scene, "你好！有什么我可以帮助你的？")

    async def get_novel_info(self, novel_id: str, chapter_start: int = 1, chapter_end: int = 10, force_db: bool = False) -> dict:
        """获取小说的完整信息，包括世界观、角色、大纲和章节
        
        Args:
            novel_id: 小说ID
            chapter_start: 开始章节（默认1）
            chapter_end: 结束章节（默认10）
            force_db: 强制从数据库加载，忽略记忆缓存（默认False）
        
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
        memory_data = None if force_db else self.memory_service.get_novel_memory(novel_id)
        if memory_data:
            logger.info(f"从记忆服务获取小说信息: {novel_id}")
            # 转换为预期的格式
            novel_info = {
                "id": memory_data['base']['id'],
                "title": memory_data['base']['title'],
                "author": memory_data['base'].get('author'),
                "genre": memory_data['base']['genre'],
                "tags": memory_data['base'].get('tags', []),
                "status": memory_data['base']['status'],
                "length_type": memory_data['base'].get('length_type'),
                "word_count": memory_data['base'].get('word_count'),
                "chapter_count": memory_data['base'].get('chapter_count'),
                "cover_url": memory_data['base'].get('cover_url'),
                "synopsis": memory_data['base']['synopsis'],
                "target_platform": memory_data['base'].get('target_platform'),
                "world_setting": memory_data['details']['world_setting'],
                "characters": memory_data['details']['characters'],
                "plot_outline": memory_data['details']['plot_outline'],
                "chapters": memory_data['chapters'],
                "metadata": memory_data['base'].get('metadata', {}),
                "created_at": memory_data['base'].get('created_at'),
                "updated_at": memory_data['base'].get('updated_at'),
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
                "status": novel.status.value if hasattr(novel.status, 'value') else novel.status,
                "length_type": novel.length_type.value if hasattr(novel.length_type, 'value') else novel.length_type,
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
                "created_at": novel.created_at.isoformat() if novel.created_at else None,
                "updated_at": novel.updated_at.isoformat() if novel.updated_at else None,
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
                novel_info["characters"].append({
                    "id": str(character.id),
                    "name": character.name,
                    "role_type": character.role_type,
                    "description": character.appearance or character.personality or "",
                    "personality": character.personality,
                    "background": character.background,
                })

            # 添加大纲信息
            if novel.plot_outline:
                novel_info["plot_outline"] = {
                    "id": str(novel.plot_outline.id),
                    "content": novel.plot_outline.raw_content or "",
                }

            # 优化章节内容截断逻辑
            def truncate_content(content, max_length=500):
                if content is None:
                    return ""
                if len(content) <= max_length:
                    return content
                # 尝试在句子边界截断
                truncated = content[:max_length]
                last_period = truncated.rfind('。')
                if last_period > max_length * 0.8:  # 确保截断位置合理
                    return truncated[:last_period+1] + "..."
                return truncated + "..."

            # 添加章节信息（根据指定范围加载）
            for chapter in novel.chapters:
                if chapter_start <= chapter.chapter_number <= chapter_end:
                    novel_info["chapters"].append({
                        "id": str(chapter.id),
                        "chapter_number": chapter.chapter_number,
                        "title": chapter.title,
                        "content": truncate_content(chapter.content),
                    })

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

    async def save_session(self, session: ChatSession) -> None:
        """保存会话到数据库"""
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
        """从数据库加载会话"""
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
                    novel_id=str(session_data.novel_id) if session_data.novel_id else None,
                    title=session_data.title
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

    async def get_sessions(self, scene: Optional[str] = None, novel_id: Optional[str] = None) -> list[dict]:
        """获取会话列表
        
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
                    session_list.append({
                        "id": str(session.id),
                        "session_id": session.session_id,
                        "scene": session.scene,
                        "novel_id": str(session.novel_id) if session.novel_id else None,
                        "title": session.title,
                        "context": session.context,
                        "created_at": session.created_at.isoformat(),
                        "updated_at": session.updated_at.isoformat(),
                    })

                return session_list
            except Exception as e:
                logger.error(f"获取会话列表失败: {e}")
                return []

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
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

        # 如果是小说相关场景，加载小说信息
        if context and "novel_id" in context:
            chapter_start = context.get("chapter_start", 1)
            chapter_end = context.get("chapter_end", 10)
            novel_info = await self.get_novel_info(novel_id, chapter_start, chapter_end)
            session.context["novel_info"] = novel_info
            session.context["chapter_range"] = {"start": chapter_start, "end": chapter_end}
            # 记录当前版本号
            session.context['novel_version'] = self.memory_service.get_novel_version(novel_id)

            # 获取变化状态
            has_changes = novel_info.get("has_changes", False)

            logger.info(f"为场景 {scene} 加载小说信息: {novel_id}, 章节范围: {chapter_start}-{chapter_end}, 有变化: {has_changes}")

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
                existing_analysis = current_memory.get('analysis', {})
                # 增量合并分析结果
                merged_analysis = self._merge_analysis(existing_analysis, analysis)
                current_memory['analysis'] = merged_analysis
                # 只有在内容有变化时才更新记忆
                if has_changes:
                    self.memory_service.set_novel_memory(novel_id, current_memory)
                    logger.info(f"小说分析结果已增量更新: {novel_id}")
                else:
                    # 即使内容没变化，也更新分析（直接更新缓存，不触发版本递增）
                    self.memory_service.cache.set(f"novel:{novel_id}", current_memory)
            else:
                novel_info['analysis'] = analysis
                self.memory_service.set_novel_memory(novel_id, novel_info)

        self.sessions[session_id] = session

        # 异步保存会话到数据库
        import asyncio
        asyncio.create_task(self.save_session(session))

        logger.info(f"创建AI对话会话: {session_id}, 场景: {scene}, 小说ID: {novel_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)

    async def _generate_session_title(self, session: ChatSession) -> str:
        """使用 AI 从对话内容中生成会话标题"""
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
        """更新会话标题到数据库"""
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

    def _analyze_user_intent(self, user_message: str, scene: str) -> str:
        """分析用户的意图，识别用户需求类型"""
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
        """分析用户的修订意图，识别修订类型"""
        # 扩展关键词列表
        world_keywords = [
            "世界观", "世界设定", "修炼体系", "地理环境", "势力划分", "规则设定",
            "世界背景", "宇宙观", "设定", "体系", "背景设定"
        ]
        character_keywords = [
            "角色", "人物", "性格", "背景", "能力", "成长路线",
            "主角", "配角", "人物塑造", "形象", "个性", "角色设定"
        ]
        outline_keywords = [
            "大纲", "剧情", "主线", "支线", "转折点", "高潮",
            "情节", "故事", "结构", "框架", "剧情发展", "情节设计"
        ]
        chapter_keywords = [
            "章节", "内容", "情节", "描写", "对话", "节奏",
            "章节内容", "段落", "细节", "叙述", "文风", "语言"
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

    def _generate_follow_up_questions(self, intent: str, scene: str, novel_info: Optional[dict] = None) -> list[str]:
        """根据用户意图生成后续问题"""
        questions = []

        if scene == SCENE_NOVEL_REVISION:
            if intent == "world_setting":
                questions.append("你希望在世界观设定中重点改进哪个方面？（如修炼体系、地理环境、势力划分等）")
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
        """检查是否需要澄清用户意图"""
        # 检查用户输入是否过于简短或模糊
        if len(user_message) < 10:
            return True

        # 检查是否包含模糊词汇
        vague_terms = ["帮忙", "改进", "分析", "建议", "看看", "检查"]
        if any(term in user_message for term in vague_terms):
            # 如果只是模糊请求，需要澄清
            if all(term not in user_message for term in ["世界观", "角色", "剧情", "章节", "结构", "市场"]):
                return True

        return False

    def _safe_get(self, data: dict, path: str, default: Any = "") -> Any:
        """安全访问嵌套字典字段
        
        Args:
            data: 字典数据
            path: 点分隔的路径，如 'world_setting.content'
            default: 默认值
            
        Returns:
            字段值或默认值
        """
        if not data or not isinstance(data, dict):
            return default

        keys = path.split('.')
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current if current is not None else default

    def _merge_analysis(self, existing: dict, new: dict) -> dict:
        """增量合并分析结果
        
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
        for key in ['strengths', 'weaknesses', 'suggestions']:
            existing_items = set(existing.get(key, []))
            new_items = set(new.get(key, []))
            merged[key] = list(existing_items | new_items)

        # genre_specific 替换（因为类型特定建议应该更新）
        if new.get('genre_specific'):
            merged['genre_specific'] = new['genre_specific']

        return merged

    def _analyze_novel_content(self, novel_info: dict) -> dict:
        """分析小说内容，生成分析结果"""
        analysis = {
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "genre_specific": [],
        }

        # 分析世界观（使用安全访问）
        world_content = self._safe_get(novel_info, 'world_setting.content', '')
        if world_content:
            if len(world_content) > 500:
                analysis['strengths'].append("世界观设定详细丰富")
            else:
                analysis['weaknesses'].append("世界观设定可能过于简单")
                analysis['suggestions'].append("建议扩展世界观设定，增加更多细节和深度")
        else:
            analysis['weaknesses'].append("缺乏世界观设定")
            analysis['suggestions'].append("建议添加详细的世界观设定")

        # 分析角色
        characters = novel_info.get('characters') or []
        if len(characters) >= 3:
            analysis['strengths'].append(f"角色数量充足（{len(characters)}个）")
        else:
            analysis['weaknesses'].append("角色数量较少")
            analysis['suggestions'].append("建议增加更多有特色的角色")

        # 分析大纲（使用安全访问）
        outline_content = self._safe_get(novel_info, 'plot_outline.content', '')
        if outline_content:
            if len(outline_content) > 300:
                analysis['strengths'].append("剧情大纲完整")
            else:
                analysis['weaknesses'].append("剧情大纲可能过于简单")
                analysis['suggestions'].append("建议扩展剧情大纲，增加更多情节细节")
        else:
            analysis['weaknesses'].append("缺乏剧情大纲")
            analysis['suggestions'].append("建议添加详细的剧情大纲")

        # 分析章节
        chapters = novel_info.get('chapters') or []
        if len(chapters) >= 3:
            analysis['strengths'].append(f"章节数量充足（{len(chapters)}章）")
        else:
            analysis['weaknesses'].append("章节数量较少")
            analysis['suggestions'].append("建议增加更多章节内容")

        # 基于小说类型的分析
        genre = novel_info.get('genre', '')
        if genre == "玄幻":
            analysis['genre_specific'].append("作为玄幻小说，建议加强修炼体系的设定和战斗场景的描写")
        elif genre == "都市":
            analysis['genre_specific'].append("作为都市小说，建议加强人物关系和现实感的描写")
        elif genre == "仙侠":
            analysis['genre_specific'].append("作为仙侠小说，建议加强仙风道骨的氛围营造和修仙境界的设定")
        elif genre == "历史":
            analysis['genre_specific'].append("作为历史小说，建议加强历史细节的准确性和时代背景的描写")

        return analysis

    def _get_persistent_memory_context(self, novel_id: str, current_chapter: int = 0) -> str:
        """从持久化记忆获取增强上下文信息
        
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
                count=10
            )
            if recent_summaries:
                context_parts.append("## 章节摘要（最近章节）")
                for summary in recent_summaries[:5]:  # 只取最近5章摘要
                    chapter_num = summary.get('chapter_number', '?')
                    key_events = summary.get('key_events', [])
                    if key_events:
                        events_str = '、'.join(key_events[:3])
                        context_parts.append(f"- 第{chapter_num}章: {events_str}")

            # 2. 获取角色状态
            character_states = self.persistent_memory.storage.get_all_character_states(novel_id)
            if character_states:
                context_parts.append("\n## 主要角色当前状态")
                for name, state in list(character_states.items())[:5]:  # 只取5个主要角色
                    location = state.get('current_location', '未知')
                    level = state.get('cultivation_level', '')
                    emotional = state.get('emotional_state', '')
                    status_parts = [f"位置: {location}"]
                    if level:
                        status_parts.append(f"境界: {level}")
                    if emotional:
                        status_parts.append(f"状态: {emotional}")
                    context_parts.append(f"- {name}: {', '.join(status_parts)}")

            # 3. 获取未解决的伏笔
            foreshadowing_list = self.persistent_memory.storage.get_foreshadowing(novel_id, status='planted')
            if foreshadowing_list:
                context_parts.append("\n## 待解决的伏笔")
                for fs in foreshadowing_list[:5]:  # 只取5个伏笔
                    desc = fs.get('description', '未知')
                    planted_ch = fs.get('planted_chapter', '?')
                    context_parts.append(f"- 第{planted_ch}章埋下: {desc[:50]}...")

            # 4. 获取时间线事件
            timeline = self.persistent_memory.storage.get_timeline_events(novel_id, limit=5)
            if timeline:
                context_parts.append("\n## 关键时间线")
                for event in timeline:
                    chapter = event.get('chapter_number', '?')
                    desc = event.get('description', '未知')
                    context_parts.append(f"- 第{chapter}章: {desc[:30]}")

        except Exception as e:
            logger.warning(f"获取持久化记忆上下文失败: {e}")
            return ""

        if context_parts:
            return "\n".join(context_parts)
        return ""

    def _initialize_persistent_memory_for_novel(self, novel_id: str, novel_info: dict) -> None:
        """为小说初始化持久化记忆
        
        Args:
            novel_id: 小说ID
            novel_info: 小说信息字典
        """
        try:
            # 保存小说元数据
            metadata = {
                'title': novel_info.get('title', ''),
                'genre': novel_info.get('genre', ''),
                'synopsis': novel_info.get('synopsis', ''),
                'status': novel_info.get('status', ''),
                'word_count': novel_info.get('word_count', 0),
                'chapter_count': novel_info.get('chapter_count', 0),
            }
            self.persistent_memory.storage.save_novel_metadata(novel_id, metadata)

            # 保存角色状态（从现有角色信息初始化）
            characters = novel_info.get('characters', [])
            for char in characters[:20]:  # 最多20个角色
                char_name = char.get('name', '')
                if char_name:
                    # 解析背景信息
                    background = char.get('background', '')
                    starting_location = ''
                    if isinstance(background, dict):
                        starting_location = background.get('starting_location', '')

                    state = {
                        'role_type': char.get('role_type', ''),
                        'current_location': starting_location or '未知',
                        'cultivation_level': '',
                        'emotional_state': '正常',
                        'last_appearance_chapter': 0,
                    }
                    self.persistent_memory.storage.save_character_state(novel_id, char_name, state)

            logger.info(f"为小说 {novel_id} 初始化持久化记忆完成")

        except Exception as e:
            logger.warning(f"初始化持久化记忆失败: {e}")

    def _generate_revision_prompt(self, user_message: str, revision_type: str, novel_info: dict) -> str:
        """根据修订类型和小说内容生成针对性的提示词"""
        # 生成小说分析
        analysis = self._analyze_novel_content(novel_info)

        # 构建基础提示
        prompt = f"# 用户修订需求\n{user_message}\n"

        # 添加修订目标说明
        prompt += "\n# 修订目标\n"

        # 添加小说分析结果
        prompt += "\n# 小说分析\n"
        if analysis['strengths']:
            prompt += "## 优势\n"
            for strength in analysis['strengths']:
                prompt += f"- {strength}\n"
        if analysis['weaknesses']:
            prompt += "\n## 不足\n"
            for weakness in analysis['weaknesses']:
                prompt += f"- {weakness}\n"
        if analysis['suggestions']:
            prompt += "\n## 初步建议\n"
            for suggestion in analysis['suggestions']:
                prompt += f"- {suggestion}\n"
        if analysis['genre_specific']:
            prompt += "\n## 类型特定建议\n"
            for suggestion in analysis['genre_specific']:
                prompt += f"- {suggestion}\n"

        # 添加持久化记忆上下文（章节摘要、角色状态、伏笔等）
        novel_id = novel_info.get('id')
        if novel_id:
            persistent_context = self._get_persistent_memory_context(novel_id)
            if persistent_context:
                prompt += "\n# 持久化记忆上下文\n"
                prompt += persistent_context + "\n"

        # 检查用户是否询问世界观相关问题
        is_worldview_question = any(keyword in user_message for keyword in ["世界观", "世界设定", "背景", "修炼体系", "地理环境", "势力划分"])

        # 无论修订类型如何，只要用户询问世界观问题，就添加世界观信息
        if is_worldview_question or revision_type == "world_setting":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的世界观设定，包括以下方面：\n"
            prompt += "1. 修炼体系的合理性和层次感\n"
            prompt += "2. 地理环境的丰富性和独特性\n"
            prompt += "3. 势力划分的逻辑性和平衡性\n"
            prompt += "4. 世界规则的一致性和创新性\n"
            prompt += "并提供具体的修订建议，包括如何扩展世界观深度和广度。\n"
            if novel_info.get('world_setting'):
                prompt += "\n## 当前世界观\n"
                world_content = novel_info.get('world_setting', {}).get('content', '') or ''
                # 优化内容呈现，确保重要信息不被截断
                if len(world_content) > 600:
                    # 提取关键信息
                    try:
                        import json
                        # 尝试解析JSON格式的世界观内容
                        world_data = json.loads(world_content)
                        # 提取关键信息
                        key_points = []
                        if 'world_name' in world_data:
                            key_points.append(f"世界名称: {world_data['world_name']}")
                        if 'world_type' in world_data:
                            key_points.append(f"世界类型: {world_data['world_type']}")
                        if 'power_system' in world_data:
                            power_system = world_data['power_system']
                            key_points.append(f"修炼体系: {power_system.get('name', '未知')}")
                            if 'levels' in power_system:
                                levels = power_system['levels'][:3]  # 只取前3个境界
                                for level in levels:
                                    key_points.append(f"  - {level.get('name', '未知')}: {level.get('description', '无描述')}")
                        if 'geography' in world_data:
                            geography = world_data['geography']
                            if geography:
                                # 安全处理 geography，可能是字典、列表或字符串
                                if isinstance(geography, (dict, list)):
                                    geography_str = json.dumps(geography, ensure_ascii=False)
                                else:
                                    geography_str = str(geography)
                                key_points.append(f"地理环境: {geography_str[:100]}...")
                        if 'factions' in world_data:
                            factions = world_data['factions']
                            if factions:
                                # 安全处理 factions，可能是字典、列表或字符串
                                if isinstance(factions, (dict, list)):
                                    factions_str = json.dumps(factions, ensure_ascii=False)
                                else:
                                    factions_str = str(factions)
                                key_points.append(f"势力划分: {factions_str[:100]}...")
                        prompt += '\n'.join(key_points) + '...\n'
                    except json.JSONDecodeError:
                        # 如果不是JSON格式，按普通文本处理
                        lines = world_content.split('\n')
                        key_points = []
                        for line in lines:
                            if line.strip() and len(' '.join(key_points)) < 500:
                                key_points.append(line.strip())
                        prompt += '\n'.join(key_points[:10]) + '...\n'
                else:
                    prompt += world_content + '\n'

        elif revision_type == "character":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的角色设定，包括以下方面：\n"
            prompt += "1. 角色性格的鲜明性和一致性\n"
            prompt += "2. 角色背景的丰富性和合理性\n"
            prompt += "3. 角色能力的平衡性和成长性\n"
            prompt += "4. 角色关系的复杂性和真实性\n"
            prompt += "并提供具体的修订建议，包括如何让角色更加立体和有吸引力。\n"
            if novel_info.get('characters'):
                prompt += "\n## 当前主要角色\n"
                for char in novel_info.get('characters', [])[:3]:
                    prompt += f"### {char.get('name', '未知')}\n"
                    prompt += f"- 角色类型: {char.get('role_type', '未知')}\n"
                    if char.get('description'):
                        desc = char.get('description', '')[:300]
                        prompt += f"- 描述: {desc}...\n"
                    if char.get('personality'):
                        prompt += f"- 性格: {char.get('personality', '无')[:100]}...\n"
                    if char.get('background'):
                        prompt += f"- 背景: {char.get('background', '无')[:100]}...\n"
                    prompt += '\n'

        elif revision_type == "outline":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的剧情大纲，包括以下方面：\n"
            prompt += "1. 主线剧情的逻辑性和吸引力\n"
            prompt += "2. 支线故事的丰富性和关联性\n"
            prompt += "3. 关键转折点的合理性和冲击力\n"
            prompt += "4. 高潮设计的震撼性和满意度\n"
            prompt += "并提供具体的修订建议，包括如何让剧情更加紧凑和引人入胜。\n"
            if novel_info.get('plot_outline'):
                prompt += "\n## 当前大纲\n"
                outline_content = novel_info.get('plot_outline', {}).get('content', '') or ''
                if len(outline_content) > 600:
                    # 提取关键信息
                    key_points = []
                    lines = outline_content.split('\n')
                    for line in lines:
                        if line.strip() and len(' '.join(key_points)) < 500:
                            key_points.append(line.strip())
                    prompt += '\n'.join(key_points[:10]) + '...\n'
                else:
                    prompt += outline_content + '\n'

        elif revision_type == "chapter":
            prompt += "\n# 详细分析要求\n"
            prompt += "请重点分析小说的章节内容，包括以下方面：\n"
            prompt += "1. 情节逻辑的连贯性和合理性\n"
            prompt += "2. 描写细节的生动性和准确性\n"
            prompt += "3. 人物对话的自然性和个性化\n"
            prompt += "4. 节奏控制的张弛度和吸引力\n"
            prompt += "并提供具体的修订建议，包括如何让章节内容更加精彩和流畅。\n"
            if novel_info.get('chapters'):
                prompt += "\n## 当前章节\n"
                for chapter in novel_info.get('chapters', [])[:2]:
                    prompt += f"### 第{chapter.get('chapter_number', '未知')}章: {chapter.get('title', '未知')}\n"
                    chapter_content = chapter.get('content', '') or ''
                    if len(chapter_content) > 400:
                        # 提取关键段落
                        paragraphs = chapter_content.split('\n')
                        key_paragraphs = []
                        for para in paragraphs:
                            if para.strip() and len(' '.join(key_paragraphs)) < 300:
                                key_paragraphs.append(para.strip())
                        prompt += '\n'.join(key_paragraphs[:3]) + '...\n'
                    else:
                        prompt += chapter_content + '\n'
                    prompt += '\n'

        else:  # general
            prompt += "\n# 详细分析要求\n"
            prompt += "请分析小说的整体情况，包括世界观、角色、大纲和章节等方面，并根据用户的需求提供综合性的修订建议。\n"
            prompt += "建议从以下几个方面进行分析：\n"
            prompt += "1. 小说整体结构的合理性\n"
            prompt += "2. 各元素之间的协调性\n"
            prompt += "3. 类型特点的体现程度\n"
            prompt += "4. 潜在的改进空间\n"
            # 添加小说概览
            if novel_info.get('title'):
                prompt += "\n## 小说概览\n"
                prompt += f"- 标题: {novel_info.get('title', '未知')}\n"
                prompt += f"- 类型: {novel_info.get('genre', '未知')}\n"
                prompt += f"- 状态: {novel_info.get('status', '未知')}\n"
                prompt += f"- 章节数: {novel_info.get('chapter_count', 0)}\n"
                prompt += f"- 字数: {novel_info.get('word_count', 0)}\n"
                if novel_info.get('synopsis'):
                    prompt += f"- 简介: {novel_info.get('synopsis')[:200]}...\n"

        # 添加输出格式要求
        prompt += "\n# 输出格式\n"
        prompt += "请按照以下格式输出分析结果：\n"
        prompt += "1. 分析结论：简要总结分析结果\n"
        prompt += "2. 具体建议：详细列出修订建议，每条建议要有具体的改进方向\n"
        prompt += "3. 实施步骤：提供实施这些建议的具体步骤\n"

        return prompt

    async def send_message(self, session_id: str, user_message: str) -> str:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        session.add_user_message(user_message)

        # 分析用户意图
        user_intent = self._analyze_user_intent(user_message, session.scene)
        session.set_last_user_intent(user_intent)

        # 检查是否需要澄清
        # 如果是小说相关场景且包含小说信息，直接回答而不澄清
        is_novel_related = session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]
        has_novel_info = session.context.get("novel_info", {}) and "error" not in session.context.get("novel_info", {})

        # 只有在非小说场景或没有小说信息时才需要澄清
        need_clarification = self._check_need_clarification(user_message, session.scene)
        if is_novel_related and has_novel_info:
            # 有小说信息时，不需要澄清，直接基于小说信息回答
            need_clarification = False

        if need_clarification:
            # 生成追问
            follow_up_questions = self._generate_follow_up_questions(user_intent, session.scene, session.context.get("novel_info"))
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

        messages = session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)

        # 如果是小说相关场景，添加小说信息到提示词
        prompt = user_message
        if session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]:
            novel_info = session.context.get("novel_info", {})
            novel_id = novel_info.get('id') if novel_info else None

            # 检查小说信息是否需要刷新（版本号变化或数据为空）
            if novel_id:
                # 获取当前记忆版本
                current_version = self.memory_service.get_novel_version(novel_id)
                session_version = session.context.get('novel_version', 0)

                # 如果版本号不一致，重新加载小说信息
                if current_version != session_version:
                    logger.info(f"检测到小说 {novel_id} 数据更新（版本 {session_version} -> {current_version}），重新加载小说信息")
                    chapter_start = session.context.get("chapter_range", {}).get("start", 1)
                    chapter_end = session.context.get("chapter_range", {}).get("end", 10)
                    # 强制从数据库加载最新数据
                    novel_info = await self.get_novel_info(novel_id, chapter_start, chapter_end, force_db=True)
                    session.context["novel_info"] = novel_info
                    session.context['novel_version'] = current_version
                    logger.info(f"小说 {novel_id} 信息已从数据库刷新到最新版本")
            else:
                # novel_id 为空，说明 novel_info 数据为空，需要重新加载
                stored_novel_id = session.context.get('novel_id')
                if stored_novel_id:
                    logger.warning(f"会话 {session.session_id} 的 novel_info 为空，重新加载小说 {stored_novel_id} 信息")
                    chapter_start = session.context.get("chapter_range", {}).get("start", 1)
                    chapter_end = session.context.get("chapter_range", {}).get("end", 10)
                    novel_info = await self.get_novel_info(stored_novel_id, chapter_start, chapter_end, force_db=True)
                    session.context["novel_info"] = novel_info
                    session.context['novel_version'] = self.memory_service.get_novel_version(stored_novel_id)
                    logger.info(f"小说 {stored_novel_id} 信息已重新加载")

            if novel_info and "error" not in novel_info:
                # 检查用户是否询问世界观相关问题
                is_worldview_question = any(keyword in user_message for keyword in ["世界观", "世界设定", "背景", "修炼体系", "地理环境", "势力划分"])

                if session.scene == SCENE_NOVEL_REVISION:
                    # 分析用户修订意图
                    revision_type = self._analyze_revision_intent(user_message)

                    # 生成针对性的提示词（已包含小说信息）
                    prompt = self._generate_revision_prompt(user_message, revision_type, novel_info)

                    # 生成并存储分析结果到记忆服务
                    analysis = self._analyze_novel_content(novel_info)
                    novel_id = novel_info.get('id')
                    if novel_id:
                        # 更新记忆服务中的分析结果
                        current_memory = self.memory_service.get_novel_memory(novel_id)
                        if current_memory:
                            current_memory['analysis'] = analysis
                            self.memory_service.set_novel_memory(novel_id, current_memory)
                        else:
                            # 如果记忆中没有，创建新的记忆
                            novel_info['analysis'] = analysis
                            self.memory_service.set_novel_memory(novel_id, novel_info)
                elif session.scene == SCENE_NOVEL_ANALYSIS:
                    # 生成小说分析提示词
                    analysis = session.context.get("analysis", self._analyze_novel_content(novel_info))

                    prompt = f"# 用户分析需求\n{user_message}\n"
                    prompt += "\n# 小说分析\n"
                    prompt += "## 小说概览\n"
                    prompt += f"- 标题: {novel_info.get('title', '未知')}\n"
                    prompt += f"- 类型: {novel_info.get('genre', '未知')}\n"
                    prompt += f"- 章节数: {novel_info.get('chapter_count', 0)}\n"
                    prompt += f"- 字数: {novel_info.get('word_count', 0)}\n"

                    # 特别添加世界观信息
                    if is_worldview_question and novel_info.get('world_setting'):
                        prompt += "\n## 世界观信息\n"
                        world_content = novel_info.get('world_setting', {}).get('content', '') or ''
                        if len(world_content) > 500:
                            # 提取关键信息
                            key_points = []
                            lines = world_content.split('\n')
                            for line in lines:
                                if line.strip() and len(' '.join(key_points)) < 400:
                                    key_points.append(line.strip())
                            prompt += '\n'.join(key_points[:8]) + '...\n'
                        else:
                            prompt += world_content + '\n'

                    if analysis:
                        if analysis.get('strengths'):
                            prompt += "\n## 优势\n"
                            for strength in analysis['strengths']:
                                prompt += f"- {strength}\n"
                        if analysis.get('weaknesses'):
                            prompt += "\n## 不足\n"
                            for weakness in analysis['weaknesses']:
                                prompt += f"- {weakness}\n"
                        if analysis.get('suggestions'):
                            prompt += "\n## 建议\n"
                            for suggestion in analysis['suggestions']:
                                prompt += f"- {suggestion}\n"
                        if analysis.get('genre_specific'):
                            prompt += "\n## 类型特定建议\n"
                            for suggestion in analysis['genre_specific']:
                                prompt += f"- {suggestion}\n"

                    # 添加持久化记忆上下文
                    persistent_context = self._get_persistent_memory_context(novel_id)
                    if persistent_context:
                        prompt += "\n# 持久化记忆上下文\n"
                        prompt += persistent_context + "\n"

                    prompt += "\n# 分析要求\n"
                    prompt += "请根据用户的需求，提供详细的小说分析结果，包括：\n"
                    prompt += "1. 整体结构分析\n"
                    prompt += "2. 各元素质量评估\n"
                    prompt += "3. 市场定位分析\n"
                    prompt += "4. 具体改进建议\n"
                    prompt += "5. 实施步骤\n"

                    prompt += "\n# 输出格式\n"
                    prompt += "请按照以下格式输出分析结果：\n"
                    prompt += "1. 分析结论：简要总结分析结果\n"
                    prompt += "2. 详细分析：分点详细分析小说各方面\n"
                    prompt += "3. 改进建议：具体的优化方向和实施步骤\n"
                    prompt += "4. 预期效果：实施建议后的预期改进效果\n"

        response = await self.client.chat(
            prompt=prompt,
            system=system_prompt,
            temperature=0.8,
        )

        assistant_message = response.get("content", "抱歉，我暂时无法回答这个问题。")

        # 生成后续问题
        follow_up_questions = self._generate_follow_up_questions(user_intent, session.scene, session.context.get("novel_info"))
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
        user_intent = self._analyze_user_intent(user_message, session.scene)
        session.set_last_user_intent(user_intent)

        # 检查是否需要澄清
        # 如果是小说相关场景且包含小说信息，直接回答而不澄清
        is_novel_related = session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]
        has_novel_info = session.context.get("novel_info", {}) and "error" not in session.context.get("novel_info", {})

        # 只有在非小说场景或没有小说信息时才需要澄清
        need_clarification = self._check_need_clarification(user_message, session.scene)
        if is_novel_related and has_novel_info:
            # 有小说信息时，不需要澄清，直接基于小说信息回答
            need_clarification = False

        if need_clarification:
            # 生成追问
            follow_up_questions = self._generate_follow_up_questions(user_intent, session.scene, session.context.get("novel_info"))
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

        messages = session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)

        # 如果是小说相关场景，添加小说信息到提示词
        prompt = user_message
        if session.scene in [SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]:
            novel_info = session.context.get("novel_info", {})
            if novel_info and "error" not in novel_info:
                # 检查用户是否询问世界观相关问题
                is_worldview_question = any(keyword in user_message for keyword in ["世界观", "世界设定", "背景", "修炼体系", "地理环境", "势力划分"])

                if session.scene == SCENE_NOVEL_REVISION:
                    # 分析用户修订意图
                    revision_type = self._analyze_revision_intent(user_message)

                    # 生成针对性的提示词（已包含小说信息）
                    prompt = self._generate_revision_prompt(user_message, revision_type, novel_info)

                    # 生成并存储分析结果到记忆服务
                    analysis = self._analyze_novel_content(novel_info)
                    novel_id = novel_info.get('id')
                    if novel_id:
                        # 更新记忆服务中的分析结果
                        current_memory = self.memory_service.get_novel_memory(novel_id)
                        if current_memory:
                            current_memory['analysis'] = analysis
                            self.memory_service.set_novel_memory(novel_id, current_memory)
                        else:
                            # 如果记忆中没有，创建新的记忆
                            novel_info['analysis'] = analysis
                            self.memory_service.set_novel_memory(novel_id, novel_info)
                elif session.scene == SCENE_NOVEL_ANALYSIS:
                    # 生成小说分析提示词
                    analysis = session.context.get("analysis", self._analyze_novel_content(novel_info))

                    prompt = f"# 用户分析需求\n{user_message}\n"
                    prompt += "\n# 小说分析\n"
                    prompt += "## 小说概览\n"
                    prompt += f"- 标题: {novel_info.get('title', '未知')}\n"
                    prompt += f"- 类型: {novel_info.get('genre', '未知')}\n"
                    prompt += f"- 章节数: {novel_info.get('chapter_count', 0)}\n"
                    prompt += f"- 字数: {novel_info.get('word_count', 0)}\n"

                    # 特别添加世界观信息
                    if is_worldview_question and novel_info.get('world_setting'):
                        prompt += "\n## 世界观信息\n"
                        world_content = novel_info.get('world_setting', {}).get('content', '') or ''
                        if len(world_content) > 500:
                            # 提取关键信息
                            key_points = []
                            lines = world_content.split('\n')
                            for line in lines:
                                if line.strip() and len(' '.join(key_points)) < 400:
                                    key_points.append(line.strip())
                            prompt += '\n'.join(key_points[:8]) + '...\n'
                        else:
                            prompt += world_content + '\n'

                    if analysis:
                        if analysis.get('strengths'):
                            prompt += "\n## 优势\n"
                            for strength in analysis['strengths']:
                                prompt += f"- {strength}\n"
                        if analysis.get('weaknesses'):
                            prompt += "\n## 不足\n"
                            for weakness in analysis['weaknesses']:
                                prompt += f"- {weakness}\n"
                        if analysis.get('suggestions'):
                            prompt += "\n## 建议\n"
                            for suggestion in analysis['suggestions']:
                                prompt += f"- {suggestion}\n"
                        if analysis.get('genre_specific'):
                            prompt += "\n## 类型特定建议\n"
                            for suggestion in analysis['genre_specific']:
                                prompt += f"- {suggestion}\n"

                    # 添加持久化记忆上下文
                    novel_id = novel_info.get('id')
                    if novel_id:
                        persistent_context = self._get_persistent_memory_context(novel_id)
                        if persistent_context:
                            prompt += "\n# 持久化记忆上下文\n"
                            prompt += persistent_context + "\n"

                    prompt += "\n# 分析要求\n"
                    prompt += "请根据用户的需求，提供详细的小说分析结果，包括：\n"
                    prompt += "1. 整体结构分析\n"
                    prompt += "2. 各元素质量评估\n"
                    prompt += "3. 市场定位分析\n"
                    prompt += "4. 具体改进建议\n"
                    prompt += "5. 实施步骤\n"

                    prompt += "\n# 输出格式\n"
                    prompt += "请按照以下格式输出分析结果：\n"
                    prompt += "1. 分析结论：简要总结分析结果\n"
                    prompt += "2. 详细分析：分点详细分析小说各方面\n"
                    prompt += "3. 改进建议：具体的优化方向和实施步骤\n"
                    prompt += "4. 预期效果：实施建议后的预期改进效果\n"

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
            follow_up_questions = self._generate_follow_up_questions(user_intent, session.scene, session.context.get("novel_info"))
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
        """解析小说创建意图，将用户自然语言转换为结构化数据"""

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
                "genre": result.get("genre", "") if result.get("genre") in NOVEL_GENRES else "",
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
        """解析爬虫任务意图，将用户自然语言转换为结构化数据"""

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
                "ranking_type": result.get("ranking_type", "") if result.get("ranking_type") in RANKING_TYPES else "yuepiao",
                "max_pages": result.get("max_pages", 3),
                "book_ids": result.get("book_ids", ""),
            }

            logger.info(f"爬虫意图解析结果: {validated_result}")
            return validated_result

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, content: {content}")
            return {"crawl_type": "", "ranking_type": "yuepiao", "max_pages": 3, "book_ids": ""}
        except Exception as e:
            logger.error(f"爬虫意图解析失败: {e}")
            return {"crawl_type": "", "ranking_type": "yuepiao", "max_pages": 3, "book_ids": ""}

    async def extract_structured_suggestions(
        self,
        ai_response: str,
        novel_info: dict,
        revision_type: str
    ) -> List[Dict[str, Any]]:
        """从AI响应中提取结构化的修订建议
        
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
                if isinstance(suggestion, dict) and suggestion.get('type') in ['novel', 'world_setting', 'character', 'outline', 'chapter']:
                    valid_suggestions.append({
                        'type': suggestion.get('type'),
                        'target_id': suggestion.get('target_id'),
                        'target_name': suggestion.get('target_name'),
                        'field': suggestion.get('field'),
                        'suggested_value': suggestion.get('suggested_value', '')[:2000],  # 限制长度
                        'description': suggestion.get('description', '')[:500],
                        'confidence': min(max(float(suggestion.get('confidence', 0.7)), 0), 1),
                    })

            logger.info(f"提取到 {len(valid_suggestions)} 条结构化建议")
            return valid_suggestions

        except json.JSONDecodeError as e:
            logger.error(f"提取结构化建议时JSON解析失败: {e}")
            return []
        except Exception as e:
            logger.error(f"提取结构化建议失败: {e}")
            return []

    async def apply_suggestion_to_database(
        self,
        novel_id: str,
        suggestion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将单个修订建议应用到数据库
        
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

        suggestion_type = suggestion.get('type')
        field = suggestion.get('field')
        suggested_value = suggestion.get('suggested_value')
        target_id = suggestion.get('target_id')
        target_name = suggestion.get('target_name')

        # 详细日志：输出建议内容
        logger.info(f"应用建议: type={suggestion_type}, field={field}, target_id={target_id}, target_name={target_name}, value_length={len(str(suggested_value)) if suggested_value else 0}")

        if not field or not suggested_value:
            error_msg = f'缺少必要的字段或建议值: field={field}, suggested_value={suggested_value}'
            logger.warning(error_msg)
            return {'success': False, 'error': error_msg}

        # 处理建议值：确保 JSONB 字段使用正确的数据结构
        # 如果是字符串，需要包装成 dict 或 list
        if isinstance(suggested_value, str):
            # 需要 dict 的字段
            dict_fields = ['power_system', 'geography', 'abilities', 'relationships', 'growth_arc', 'main_plot']
            # 需要 list 的字段（关键结构化数据）
            list_fields = ['factions', 'rules', 'timeline', 'special_elements', 'volumes', 'sub_plots', 'key_turning_points']

            if field in dict_fields:
                # 尝试解析 JSON 字符串
                try:
                    parsed = json.loads(suggested_value)
                    if isinstance(parsed, dict):
                        suggested_value = parsed
                    else:
                        suggested_value = {'content': suggested_value}
                except json.JSONDecodeError:
                    suggested_value = {'content': suggested_value}
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
                        for line in suggested_value.strip().split('\n'):
                            line = line.strip()
                            if line.startswith('{') and line.endswith('}'):
                                try:
                                    items.append(ast.literal_eval(line))
                                except:
                                    continue
                        if items:
                            suggested_value = items
                        else:
                            # 无法解析为结构化数据，拒绝更新
                            logger.warning(f"无法将字符串解析为结构化列表数据，拒绝更新字段 {field}")
                            return {'success': False, 'error': f'字段 {field} 需要结构化数据，无法从文本自动解析。请手动编辑。', 'skip': True}
                except json.JSONDecodeError:
                    # 尝试解析多行字典格式
                    import ast
                    items = []
                    for line in suggested_value.strip().split('\n'):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                items.append(ast.literal_eval(line))
                            except:
                                continue
                    if items:
                        suggested_value = items
                    else:
                        # 无法解析为结构化数据，拒绝更新
                        logger.warning(f"无法将字符串解析为结构化列表数据，拒绝更新字段 {field}")
                        return {'success': False, 'error': f'字段 {field} 需要结构化数据，无法从文本自动解析。请手动编辑。', 'skip': True}

        async with async_session_factory() as db:
            try:
                if suggestion_type == 'novel':
                    # 更新小说基本信息
                    query = select(Novel).where(Novel.id == novel_id)
                    result = await db.execute(query)
                    novel = result.scalar_one_or_none()

                    if not novel:
                        return {'success': False, 'error': '小说不存在'}

                    # 根据字段更新
                    if hasattr(novel, field):
                        setattr(novel, field, suggested_value)
                    else:
                        return {'success': False, 'error': f'无效的字段: {field}'}

                    await db.commit()
                    logger.info(f"已更新小说 {novel_id} 的字段 {field}")
                    return {'success': True, 'type': 'novel', 'field': field}

                elif suggestion_type == 'world_setting':
                    # 更新世界观设定
                    query = select(WorldSetting).where(WorldSetting.novel_id == novel_id)
                    result = await db.execute(query)
                    world_setting = result.scalar_one_or_none()

                    if not world_setting:
                        return {'success': False, 'error': '世界观设定不存在'}

                    # 根据字段更新
                    if field == 'raw_content' or field == 'content':
                        world_setting.raw_content = suggested_value
                    elif hasattr(world_setting, field):
                        setattr(world_setting, field, suggested_value)
                    else:
                        return {'success': False, 'error': f'无效的字段: {field}'}

                    await db.commit()
                    logger.info(f"已更新小说 {novel_id} 的世界观设定字段 {field}")
                    return {'success': True, 'type': 'world_setting', 'field': field}

                elif suggestion_type == 'character':
                    # 更新角色信息
                    # 检查是否是创建新角色的建议（target_id 为虚拟标识符）
                    if target_id and (target_id.startswith('new_') or len(target_id) < 32):
                        # 这是创建新角色的建议，跳过
                        logger.warning(f"跳过创建新角色的建议: {target_name}, 需要手动创建角色")
                        return {'success': False, 'error': f'请先创建角色: {target_name}，然后再应用修订建议', 'skip': True}

                    if target_id:
                        query = select(Character).where(
                            Character.id == target_id,
                            Character.novel_id == novel_id
                        )
                    elif target_name:
                        query = select(Character).where(
                            Character.name == target_name,
                            Character.novel_id == novel_id
                        )
                    else:
                        return {'success': False, 'error': '需要指定角色ID或角色名称'}

                    result = await db.execute(query)
                    character = result.scalar_one_or_none()

                    if not character:
                        return {'success': False, 'error': f'角色不存在: {target_name or target_id}'}

                    if hasattr(character, field):
                        setattr(character, field, suggested_value)
                    else:
                        return {'success': False, 'error': f'无效的字段: {field}'}

                    await db.commit()
                    logger.info(f"已更新角色 {character.name} 的字段 {field}")
                    return {'success': True, 'type': 'character', 'character_name': character.name, 'field': field}

                elif suggestion_type == 'outline':
                    # 更新大纲
                    query = select(PlotOutline).where(PlotOutline.novel_id == novel_id)
                    result = await db.execute(query)
                    plot_outline = result.scalar_one_or_none()

                    if not plot_outline:
                        return {'success': False, 'error': '大纲不存在'}

                    if field == 'raw_content' or field == 'content':
                        plot_outline.raw_content = suggested_value
                    elif hasattr(plot_outline, field):
                        setattr(plot_outline, field, suggested_value)
                    else:
                        return {'success': False, 'error': f'无效的字段: {field}'}

                    await db.commit()
                    logger.info(f"已更新小说 {novel_id} 的大纲字段 {field}")
                    return {'success': True, 'type': 'outline', 'field': field}

                elif suggestion_type == 'chapter':
                    # 更新章节
                    if target_id:
                        # target_id 可能是章节号
                        try:
                            chapter_number = int(target_id)
                            query = select(Chapter).where(
                                Chapter.chapter_number == chapter_number,
                                Chapter.novel_id == novel_id
                            )
                        except (ValueError, TypeError):
                            query = select(Chapter).where(
                                Chapter.id == target_id,
                                Chapter.novel_id == novel_id
                            )
                    elif target_name:
                        query = select(Chapter).where(
                            Chapter.title == target_name,
                            Chapter.novel_id == novel_id
                        )
                    else:
                        return {'success': False, 'error': '需要指定章节ID或章节标题'}

                    result = await db.execute(query)
                    chapter = result.scalar_one_or_none()

                    if not chapter:
                        return {'success': False, 'error': f'章节不存在: {target_name or target_id}'}

                    if hasattr(chapter, field):
                        setattr(chapter, field, suggested_value)
                        # 如果更新了内容，同时更新字数
                        if field == 'content' and suggested_value:
                            chapter.word_count = len(suggested_value)
                    else:
                        return {'success': False, 'error': f'无效的字段: {field}'}

                    await db.commit()
                    logger.info(f"已更新章节 {chapter.chapter_number} 的字段 {field}")
                    return {'success': True, 'type': 'chapter', 'chapter_number': chapter.chapter_number, 'field': field}

                else:
                    return {'success': False, 'error': f'不支持的建议类型: {suggestion_type}'}

            except Exception as e:
                logger.error(f"应用建议到数据库失败: {e}")
                await db.rollback()
                return {'success': False, 'error': str(e)}

    async def apply_suggestions_batch(
        self,
        novel_id: str,
        suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """批量应用修订建议到数据库
        
        Args:
            novel_id: 小说ID
            suggestions: 建议列表
        
        Returns:
            批量应用结果
        """
        results = {
            'total': len(suggestions),
            'success_count': 0,
            'failed_count': 0,
            'details': []
        }

        for suggestion in suggestions:
            result = await self.apply_suggestion_to_database(novel_id, suggestion)
            results['details'].append(result)
            if result.get('success'):
                results['success_count'] += 1
            else:
                results['failed_count'] += 1

        # 应用成功后，使记忆服务缓存失效，确保下次获取最新数据
        if results['success_count'] > 0:
            self.memory_service.invalidate_novel_memory(novel_id)
            # 增加版本号
            current_version = self.memory_service.get_novel_version(novel_id)
            self.memory_service.version_map[novel_id] = current_version + 1
            logger.info(f"已使小说 {novel_id} 的记忆缓存失效，版本号更新为 {current_version + 1}")

        return results

    async def get_novel_characters(self, novel_id: str) -> List[Dict[str, Any]]:
        """获取小说的所有角色
        
        Args:
            novel_id: 小说ID
        
        Returns:
            角色列表
        """
        from core.database import async_session_factory
        from core.models.character import Character

        async with async_session_factory() as db:
            try:
                query = select(Character).where(Character.novel_id == novel_id).order_by(Character.created_at)
                result = await db.execute(query)
                characters = result.scalars().all()

                return [
                    {
                        'id': str(char.id),
                        'name': char.name,
                        'role_type': char.role_type.value if hasattr(char.role_type, 'value') else char.role_type,
                        'personality': char.personality,
                        'background': char.background,
                    }
                    for char in characters
                ]
            except Exception as e:
                logger.error(f"获取角色列表失败: {e}")
                return []

    async def get_novel_chapters(self, novel_id: str) -> List[Dict[str, Any]]:
        """获取小说的所有章节
        
        Args:
            novel_id: 小说ID
        
        Returns:
            章节列表
        """
        from core.database import async_session_factory
        from core.models.chapter import Chapter

        async with async_session_factory() as db:
            try:
                query = select(Chapter).where(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number)
                result = await db.execute(query)
                chapters = result.scalars().all()

                return [
                    {
                        'id': str(chap.id),
                        'chapter_number': chap.chapter_number,
                        'title': chap.title,
                        'word_count': chap.word_count,
                        'status': chap.status.value if hasattr(chap.status, 'value') else chap.status,
                    }
                    for chap in chapters
                ]
            except Exception as e:
                logger.error(f"获取章节列表失败：{e}")
                return []

    # ==================== 小说对话流程集成方法 ====================

    async def start_novel_dialogue_flow(self, session_id: str, scene: str = "create") -> str:
        """启动小说对话流程（创建/查询/修改）
        
        Args:
            session_id: 会话 ID
            scene: 场景类型 (create/query/revise)
        
        Returns:
            欢迎消息
        """
        from backend.services.novel_creation_flow_manager import NovelCreationFlowManager
        from backend.schemas.novel_creation_flow import NovelDialogueScene
        
        # 映射场景字符串到枚举
        scene_mapping = {
            "create": NovelDialogueScene.CREATE,
            "query": NovelDialogueScene.QUERY,
            "revise": NovelDialogueScene.REVISE,
            "novel_creation": NovelDialogueScene.CREATE,
            "novel_query": NovelDialogueScene.QUERY,
            "novel_revision": NovelDialogueScene.REVISE
        }
        
        flow_scene = scene_mapping.get(scene, NovelDialogueScene.CREATE)
        
        # 初始化流程
        flow_manager = NovelCreationFlowManager(self.db, self.client)
        await flow_manager.initialize_flow(session_id, flow_scene)
        
        # 根据场景返回不同的欢迎消息
        if flow_scene == NovelDialogueScene.CREATE:
            return """您好！我是您的小说创作助手📚

我将通过对话帮您完成小说的创建，包括：
✅ 确认小说类型
✅ 构建世界观设定
✅ 提炼核心简介
✅ 自动生成创建请求

让我们开始吧！请告诉我：您想创作什么类型的小说呢？

比如：玄幻、科幻、言情、都市、历史、悬疑等"""
        
        elif flow_scene == NovelDialogueScene.QUERY:
            return """您好！我是您的小说查询助手📖

我可以帮您查询已有小说的各种信息：
- 📚 基本信息（标题、类型、字数等）
- 🌍 世界观设定（时代、地理、势力、规则等）
- 👥 角色信息（外貌、性格、背景、能力等）
- 📖 剧情大纲（主线、支线、转折点等）
- 📄 章节列表和内容

请告诉我您想查询哪部小说？您可以提供小说 ID、名称或关键词。"""
        
        elif flow_scene == NovelDialogueScene.REVISE:
            return """您好！我是您的小说修订助手✏️

我可以帮您通过对话修改小说内容：
- 🌍 修改世界观设定
- 👥 修改角色信息
- 📖 修改剧情大纲
- 📝 修改小说基本信息

请告诉我您想修改哪部小说？"""
        
        else:
            return "您好！我是您的小说创作助手，请问有什么可以帮助您的？"

    async def process_novel_dialogue_message(self, session_id: str, user_message: str) -> str:
        """处理小说对话流程中的消息
        
        Args:
            session_id: 会话 ID
            user_message: 用户消息
        
        Returns:
            AI 回复消息
        """
        from backend.services.novel_creation_flow_manager import NovelCreationFlowManager
        
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
                "revision_target": response.context.revision_target
            }
            
            # 异步保存会话
            import asyncio
            asyncio.create_task(self.save_session(session))
        
        return response.message
