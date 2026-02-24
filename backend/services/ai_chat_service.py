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
}

WELCOME_MESSAGES = {
    SCENE_NOVEL_CREATION: "你好！我是小说创作AI助手。你可以告诉我你想写什么类型的小说，或者有什么创意想法，我来帮你完善世界观、角色和情节设定。",
    
    SCENE_CRAWLER_TASK: "你好！我是爬虫策略AI助手。你可以告诉我你想爬取什么数据，或者想了解哪些市场趋势，我来帮你分析并制定合适的爬取方案。",
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
    
    def create_session(self, scene: str, context: Optional[dict] = None) -> ChatSession:
        import uuid
        session_id = str(uuid.uuid4())
        session = ChatSession(session_id, scene, context)
        self.sessions[session_id] = session
        logger.info(f"创建AI对话会话: {session_id}, 场景: {scene}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)
    
    def send_message(self, session_id: str, user_message: str) -> str:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        
        session.add_user_message(user_message)
        
        messages = session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)
        
        response = self.client.chat(
            prompt=user_message,
            system=system_prompt,
            temperature=0.8,
        )
        
        assistant_message = response.get("content", "抱歉，我暂时无法回答这个问题。")
        session.add_assistant_message(assistant_message)
        
        logger.info(f"会话 {session_id} 收到用户消息: {user_message[:50]}...")
        
        return assistant_message
    
    async def send_message_stream(self, session_id: str, user_message: str) -> AsyncIterator[str]:
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        
        session.add_user_message(user_message)
        
        messages = session.get_messages_for_api()
        system_prompt = self._get_system_prompt(session.scene)
        
        full_response = ""
        
        try:
            for chunk in self.client.stream_chat(
                prompt=user_message,
                system=system_prompt,
                temperature=0.8,
            ):
                full_response += chunk
                yield chunk
            
            session.add_assistant_message(full_response)
            logger.info(f"会话 {session_id} 流式响应完成，共 {len(full_response)} 字符")
            
        except Exception as e:
            logger.error(f"流式响应出错: {e}")
            error_msg = "抱歉，响应生成过程中出现错误，请稍后重试。"
            yield error_msg
            session.add_assistant_message(error_msg)
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
