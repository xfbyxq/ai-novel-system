"""AI 对话服务 - 提供智能辅助能力"""

import json
import logging
import re
from typing import AsyncIterator, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from llm.qwen_client import QwenClient

logger = logging.getLogger(__name__)

SCENE_NOVEL_CREATION = "novel_creation"
SCENE_CRAWLER_TASK = "crawler_task"
SCENE_NOVEL_REVISION = "novel_revision"

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
    
    SCENE_NOVEL_REVISION: """你是一位专业的小说编辑顾问，专门帮助作者修订和完善小说内容。你需要根据用户的需求和小说的现有内容，提供专业的修订建议，包括但不限于：

1. **世界观修订**：修炼体系、地理环境、势力划分、规则设定的合理性和连贯性
2. **角色修订**：主角/配角的性格、背景、能力、成长路线的塑造和发展
3. **大纲修订**：主线剧情、支线故事、关键转折点、高潮设计的逻辑性和吸引力
4. **章节内容修订**：情节逻辑、描写细节、人物对话、节奏控制的优化

请用中文回复，语气专业但亲切。分析现有内容的问题，并提供具体的修订建议。可以主动询问用户更多细节以便给出更好的建议。""",
}

WELCOME_MESSAGES = {
    SCENE_NOVEL_CREATION: "你好！我是小说创作AI助手。你可以告诉我你想写什么类型的小说，或者有什么创意想法，我来帮你完善世界观、角色和情节设定。",
    
    SCENE_CRAWLER_TASK: "你好！我是爬虫策略AI助手。你可以告诉我你想爬取什么数据，或者想了解哪些市场趋势，我来帮你分析并制定合适的爬取方案。",
    
    SCENE_NOVEL_REVISION: "你好！我是小说修订AI助手。你可以告诉我你对小说的哪些部分不满意，无论是世界观、角色、大纲还是章节内容，我都会根据现有内容提供专业的修订建议。",
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
    def __init__(self, session_id: str, scene: str, context: Optional[dict] = None):
        self.session_id = session_id
        self.scene = scene
        self.context = context or {}
        self.messages: list[ChatMessage] = []
        
        welcome = WELCOME_MESSAGES.get(scene, "你好！有什么我可以帮助你的？")
        self.messages.append(ChatMessage("assistant", welcome))
    
    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage("user", content))
    
    def add_assistant_message(self, content: str) -> None:
        self.messages.append(ChatMessage("assistant", content))
    
    def get_messages_for_api(self) -> list[dict]:
        result = []
        for msg in self.messages:
            result.append(msg.to_dict())
        return result


class AiChatService:
    """AI 对话服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = QwenClient()
        self.sessions: dict[str, ChatSession] = {}
    
    def _get_system_prompt(self, scene: str) -> str:
        return SYSTEM_PROMPTS.get(scene, "你是一位AI助手，请帮助用户解决问题。")
    
    def _get_welcome_message(self, scene: str) -> str:
        return WELCOME_MESSAGES.get(scene, "你好！有什么我可以帮助你的？")
    
    async def get_novel_info(self, novel_id: str) -> dict:
        """获取小说的完整信息，包括世界观、角色、大纲和章节"""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from core.models.novel import Novel
        from uuid import UUID
        
        try:
            # 验证 novel_id 是否为有效的 UUID
            UUID(novel_id)
        except ValueError:
            logger.error(f"无效的小说 ID 格式: {novel_id}")
            return {"error": "无效的小说 ID 格式"}
        
        logger.info(f"获取小说信息: {novel_id}")
        
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
                "genre": novel.genre,
                "status": novel.status.value if hasattr(novel.status, 'value') else novel.status,
                "synopsis": novel.synopsis,
                "world_setting": None,
                "characters": [],
                "plot_outline": None,
                "chapters": [],
            }
            
            # 添加世界观信息
            if novel.world_setting:
                novel_info["world_setting"] = {
                    "id": str(novel.world_setting.id),
                    "setting_type": novel.world_setting.setting_type,
                    "content": novel.world_setting.content,
                }
            
            # 添加角色信息（限制最多20个角色）
            for character in novel.characters[:20]:
                novel_info["characters"].append({
                    "id": str(character.id),
                    "name": character.name,
                    "role_type": character.role_type,
                    "description": character.description,
                    "personality": character.personality,
                    "background": character.background,
                })
            
            # 添加大纲信息
            if novel.plot_outline:
                novel_info["plot_outline"] = {
                    "id": str(novel.plot_outline.id),
                    "content": novel.plot_outline.content,
                }
            
            # 优化章节内容截断逻辑
            def truncate_content(content, max_length=500):
                if len(content) <= max_length:
                    return content
                # 尝试在句子边界截断
                truncated = content[:max_length]
                last_period = truncated.rfind('。')
                if last_period > max_length * 0.8:  # 确保截断位置合理
                    return truncated[:last_period+1] + "..."
                return truncated + "..."
            
            # 添加章节信息（只取前10章，避免内容过多）
            for chapter in novel.chapters[:10]:
                novel_info["chapters"].append({
                    "id": str(chapter.id),
                    "chapter_number": chapter.chapter_number,
                    "title": chapter.title,
                    "content": truncate_content(chapter.content),
                })
            
            logger.info(f"成功获取小说信息: {novel.title}")
            return novel_info
        except Exception as e:
            logger.error(f"获取小说信息失败: {e}")
            return {"error": "获取小说信息失败，请稍后重试"}

    async def save_session(self, session: ChatSession) -> None:
        """保存会话到数据库"""
        from sqlalchemy import insert
        from core.models.ai_chat_session import AIChatSession, AIChatMessage
        from core.database import async_session_factory
        
        async with async_session_factory() as db:
            try:
                # 保存会话信息
                session_data = {
                    "session_id": session.session_id,
                    "scene": session.scene,
                    "context": session.context,
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
                
                # 保存消息
                for msg in session.messages:
                    # 检查消息是否已存在（这里简化处理，只保存新消息）
                    msg_count = await db.execute(
                        select(AIChatMessage)
                        .where(AIChatMessage.session_id == session.session_id)
                    )
                    if msg_count.scalar_one_or_none() is None:
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
        from core.models.ai_chat_session import AIChatSession, AIChatMessage
        from core.database import async_session_factory
        
        async with async_session_factory() as db:
            try:
                # 加载会话信息
                session_result = await db.execute(
                    select(AIChatSession).where(AIChatSession.session_id == session_id)
                )
                session_data = session_result.scalar_one_or_none()
                
                if not session_data:
                    return None
                
                # 创建会话对象
                session = ChatSession(
                    session_data.session_id,
                    session_data.scene,
                    session_data.context
                )
                
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
    
    async def get_sessions(self, scene: Optional[str] = None) -> list[dict]:
        """获取会话列表"""
        from sqlalchemy import select
        from core.models.ai_chat_session import AIChatSession
        from core.database import async_session_factory
        
        async with async_session_factory() as db:
            try:
                query = select(AIChatSession)
                if scene:
                    query = query.where(AIChatSession.scene == scene)
                query = query.order_by(AIChatSession.updated_at.desc())
                
                result = await db.execute(query)
                sessions = result.scalars().all()
                
                session_list = []
                for session in sessions:
                    session_list.append({
                        "id": str(session.id),
                        "session_id": session.session_id,
                        "scene": session.scene,
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
        from core.models.ai_chat_session import AIChatSession, AIChatMessage
        from core.database import async_session_factory
        
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
        session = ChatSession(session_id, scene, context)
        
        # 如果是小说修订场景，加载小说信息
        if scene == SCENE_NOVEL_REVISION and context and "novel_id" in context:
            novel_id = context["novel_id"]
            novel_info = await self.get_novel_info(novel_id)
            session.context["novel_info"] = novel_info
            logger.info(f"为小说修订场景加载小说信息: {novel_id}")
        
        self.sessions[session_id] = session
        
        # 异步保存会话到数据库
        import asyncio
        asyncio.create_task(self.save_session(session))
        
        logger.info(f"创建AI对话会话: {session_id}, 场景: {scene}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)
    
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
        import re
        chapter_match = re.search(r"第(\d+)章", user_message)
        if chapter_match:
            return "chapter"
        
        # 识别角色名（如果用户提到了具体角色）
        if any(keyword in user_message for keyword in ["角色", "人物", "主角", "配角"]):
            return "character"
        
        return "general"  # 通用修订
    
    def _generate_revision_prompt(self, user_message: str, revision_type: str, novel_info: dict) -> str:
        """根据修订类型和小说内容生成针对性的提示词"""
        # 构建基础提示
        prompt = f"# 用户修订需求\n{user_message}\n"
        
        # 添加修订目标说明
        prompt += "\n# 修订目标\n"
        
        # 根据修订类型添加针对性的提示
        if revision_type == "world_setting":
            prompt += "请重点分析小说的世界观设定，包括修炼体系、地理环境、势力划分等方面的合理性和连贯性，并提供具体的修订建议。\n"
            if novel_info.get('world_setting'):
                prompt += "\n## 当前世界观\n"
                world_content = novel_info.get('world_setting', {}).get('content', '无')
                # 优化内容呈现，确保重要信息不被截断
                if len(world_content) > 600:
                    # 提取关键信息
                    key_points = []
                    lines = world_content.split('\n')
                    for line in lines:
                        if line.strip() and len(' '.join(key_points)) < 500:
                            key_points.append(line.strip())
                    prompt += '\n'.join(key_points[:10]) + '...\n'
                else:
                    prompt += world_content + '\n'
        
        elif revision_type == "character":
            prompt += "请重点分析小说的角色设定，包括性格、背景、能力、成长路线等方面的塑造和发展，并提供具体的修订建议。\n"
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
            prompt += "请重点分析小说的剧情大纲，包括主线剧情、支线故事、关键转折点、高潮设计等方面的逻辑性和吸引力，并提供具体的修订建议。\n"
            if novel_info.get('plot_outline'):
                prompt += "\n## 当前大纲\n"
                outline_content = novel_info.get('plot_outline', {}).get('content', '无')
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
            prompt += "请重点分析小说的章节内容，包括情节逻辑、描写细节、人物对话、节奏控制等方面的优化，并提供具体的修订建议。\n"
            if novel_info.get('chapters'):
                prompt += "\n## 当前章节\n"
                for chapter in novel_info.get('chapters', [])[:2]:
                    prompt += f"### 第{chapter.get('chapter_number', '未知')}章: {chapter.get('title', '未知')}\n"
                    chapter_content = chapter.get('content', '无')
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
            prompt += "请分析小说的整体情况，包括世界观、角色、大纲和章节等方面，并根据用户的需求提供综合性的修订建议。\n"
            # 添加小说概览
            if novel_info.get('title'):
                prompt += f"\n## 小说概览\n"
                prompt += f"- 标题: {novel_info.get('title', '未知')}\n"
                prompt += f"- 类型: {novel_info.get('genre', '未知')}\n"
                prompt += f"- 状态: {novel_info.get('status', '未知')}\n"
                if novel_info.get('synopsis'):
                    prompt += f"- 简介: {novel_info.get('synopsis')[:200]}...\n"
        
        return prompt
    
    def send_message(self, session_id: str, user_message: str) -> str:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        
        session.add_user_message(user_message)
        
        messages = session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)
        
        # 如果是小说修订场景，添加小说信息到提示词
        prompt = user_message
        if session.scene == SCENE_NOVEL_REVISION:
            novel_info = session.context.get("novel_info", {})
            if novel_info and "error" not in novel_info:
                # 分析用户修订意图
                revision_type = self._analyze_revision_intent(user_message)
                
                # 生成针对性的提示词（已包含小说信息）
                prompt = self._generate_revision_prompt(user_message, revision_type, novel_info)
        
        response = self.client.chat(
            prompt=prompt,
            system=system_prompt,
            temperature=0.8,
        )
        
        assistant_message = response.get("content", "抱歉，我暂时无法回答这个问题。")
        session.add_assistant_message(assistant_message)
        
        # 异步保存会话到数据库
        import asyncio
        asyncio.create_task(self.save_session(session))
        
        logger.info(f"会话 {session_id} 收到用户消息: {user_message[:50]}...")
        
        return assistant_message
    
    async def send_message_stream(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        
        session.add_user_message(user_message)
        
        messages = session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)
        
        # 如果是小说修订场景，添加小说信息到提示词
        prompt = user_message
        if session.scene == SCENE_NOVEL_REVISION:
            novel_info = session.context.get("novel_info", {})
            if novel_info and "error" not in novel_info:
                # 分析用户修订意图
                revision_type = self._analyze_revision_intent(user_message)
                
                # 生成针对性的提示词（已包含小说信息）
                prompt = self._generate_revision_prompt(user_message, revision_type, novel_info)
        
        full_response = ""
        
        try:
            for chunk in self.client.stream_chat(
                prompt=prompt,
                system=system_prompt,
                temperature=0.8,
            ):
                full_response += chunk
                yield chunk
            
            session.add_assistant_message(full_response)
            logger.info(f"会话 {session_id} 流式响应完成，共 {len(full_response)} 字符")
            
            # 保存会话到数据库
            await self.save_session(session)
            
        except Exception as e:
            logger.error(f"流式响应出错: {e}")
            error_msg = "抱歉，响应生成过程中出现错误，请稍后重试。"
            yield error_msg
            session.add_assistant_message(error_msg)
            # 保存错误信息到数据库
            await self.save_session(session)
            raise

    def parse_novel_intent(self, user_input: str) -> dict:
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
            response = self.client.chat(
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

    def parse_crawler_intent(self, user_input: str) -> dict:
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
            response = self.client.chat(
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
