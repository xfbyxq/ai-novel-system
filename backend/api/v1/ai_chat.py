"""AI Chat API 端点"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from backend.dependencies import get_db

from backend.schemas.ai_chat import (
    AIChatSessionCreate,
    AIChatSessionResponse,
    AIChatMessageCreate,
    AIChatMessageResponse,
    NovelParseRequest,
    NovelParseResponse,
    CrawlerParseRequest,
    CrawlerParseResponse,
    ExtractSuggestionsRequest,
    ExtractSuggestionsResponse,
    ApplySuggestionRequest,
    ApplySuggestionsRequest,
    ApplySuggestionsResponse,
    RevisionSuggestion,
    NovelCharactersResponse,
    NovelChaptersResponse,
    CharacterListItem,
    ChapterListItem,
)
from backend.services.ai_chat_service import (
    AiChatService,
    SCENE_NOVEL_CREATION,
    SCENE_CRAWLER_TASK,
    SCENE_NOVEL_REVISION,
    SCENE_NOVEL_ANALYSIS,
)

router = APIRouter(prefix="/ai-chat", tags=["ai-chat"])

_ai_chat_service_instance: Optional[AiChatService] = None


def get_ai_chat_service(db: AsyncSession = Depends(get_db)) -> AiChatService:
    global _ai_chat_service_instance
    if _ai_chat_service_instance is None:
        _ai_chat_service_instance = AiChatService(db=db)
    else:
        # 更新数据库会话
        _ai_chat_service_instance.db = db
    return _ai_chat_service_instance


@router.post("/sessions", response_model=AIChatSessionResponse)
async def create_session(
    session_in: AIChatSessionCreate,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """创建新的 AI 对话会话"""
    if session_in.scene not in [SCENE_NOVEL_CREATION, SCENE_CRAWLER_TASK, SCENE_NOVEL_REVISION, SCENE_NOVEL_ANALYSIS]:
        raise HTTPException(
            status_code=400,
            detail=f"无效的场景。可选: {SCENE_NOVEL_CREATION}, {SCENE_CRAWLER_TASK}, {SCENE_NOVEL_REVISION}, {SCENE_NOVEL_ANALYSIS}"
        )
    
    session = await service.create_session(
        scene=session_in.scene,
        context=session_in.context,
    )
    
    return AIChatSessionResponse(
        session_id=session.session_id,
        scene=session.scene,
        welcome_message=session.messages[0].content,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/sessions/{session_id}/messages", response_model=AIChatMessageResponse)
async def send_message(
    session_id: str,
    message_in: AIChatMessageCreate,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """发送消息并获取 AI 回复"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        response_text = await service.send_message(session_id, message_in.message)
        
        return AIChatMessageResponse(
            session_id=session_id,
            message=response_text,
            role="assistant",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except ValueError as e:
        logger.error(f"发送消息失败 (ValueError): {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"发送消息失败 (Exception): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成回复失败: {str(e)}")


@router.websocket("/ws/{session_id}")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """WebSocket 流式对话"""
    await websocket.accept()
    
    session = service.get_session(session_id)
    if not session:
        await websocket.send_json({"error": f"会话 {session_id} 不存在"})
        await websocket.close()
        return
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message:
                continue
            
            await websocket.send_json({"chunk": "", "done": False})
            
            full_response = ""
            try:
                async for chunk in service.send_message_stream(session_id, user_message):
                    await websocket.send_json({"chunk": chunk, "done": False})
                    full_response += chunk
                
                await websocket.send_json({"chunk": "", "done": True})
                
            except Exception as e:
                await websocket.send_json({"error": str(e), "done": True})
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
    finally:
        await websocket.close()


@router.post("/parse-novel", response_model=NovelParseResponse)
async def parse_novel_intent(
    request: NovelParseRequest,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """解析小说创建意图，将自然语言转换为结构化数据"""
    try:
        result = await service.parse_novel_intent(request.user_input)
        return NovelParseResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/parse-crawler", response_model=CrawlerParseResponse)
async def parse_crawler_intent(
    request: CrawlerParseRequest,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """解析爬虫任务意图，将自然语言转换为结构化数据"""
    try:
        result = await service.parse_crawler_intent(request.user_input)
        return CrawlerParseResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.get("/sessions")
async def list_sessions(
    scene: Optional[str] = None,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """获取会话列表"""
    try:
        sessions = await service.get_sessions(scene)
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """获取会话详情"""
    try:
        # 先尝试从内存中获取
        session = service.get_session(session_id)
        if not session:
            # 从数据库加载
            session = await service.load_session(session_id)
            if session:
                # 加载到内存
                service.sessions[session_id] = session
        
        if not session:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        
        return {
            "session_id": session.session_id,
            "scene": session.scene,
            "context": session.context,
            "messages": [msg.to_dict() for msg in session.messages],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取会话失败: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """删除会话"""
    try:
        # 从内存中删除
        if session_id in service.sessions:
            del service.sessions[session_id]
        
        # 从数据库删除
        success = await service.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        
        return {"message": "会话删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


@router.post("/extract-suggestions", response_model=ExtractSuggestionsResponse)
async def extract_suggestions(
    request: ExtractSuggestionsRequest,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """从AI响应中提取结构化的修订建议"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 获取小说信息
        novel_info = await service.get_novel_info(request.novel_id)
        if "error" in novel_info:
            raise HTTPException(status_code=404, detail=novel_info["error"])
        
        # 提取结构化建议
        suggestions = await service.extract_structured_suggestions(
            request.ai_response,
            novel_info,
            request.revision_type
        )
        
        # 转换为响应格式
        suggestion_models = []
        for s in suggestions:
            # 处理 target_id，确保是字符串类型
            target_id = s.get('target_id')
            if target_id is not None and not isinstance(target_id, str):
                target_id = str(target_id)
            
            suggestion_models.append(
                RevisionSuggestion(
                    type=s.get('type'),
                    target_id=target_id,
                    target_name=s.get('target_name'),
                    field=s.get('field'),
                    suggested_value=s.get('suggested_value'),
                    description=s.get('description', ''),
                    confidence=s.get('confidence', 0.8)
                )
            )
        
        return ExtractSuggestionsResponse(suggestions=suggestion_models)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提取建议失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"提取建议失败: {str(e)}")


@router.post("/apply-suggestion")
async def apply_suggestion(
    request: ApplySuggestionRequest,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """应用单个修订建议到数据库"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        result = await service.apply_suggestion_to_database(
            request.novel_id,
            request.suggestion.model_dump()
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', '应用失败'))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"应用建议失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"应用建议失败: {str(e)}")


@router.post("/apply-suggestions", response_model=ApplySuggestionsResponse)
async def apply_suggestions_batch(
    request: ApplySuggestionsRequest,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """批量应用修订建议到数据库"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        suggestions_dicts = [s.model_dump() for s in request.suggestions]
        result = await service.apply_suggestions_batch(
            request.novel_id,
            suggestions_dicts
        )
        
        return ApplySuggestionsResponse(
            total=result['total'],
            success_count=result['success_count'],
            failed_count=result['failed_count'],
            details=result['details']
        )
    except Exception as e:
        logger.error(f"批量应用建议失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量应用建议失败: {str(e)}")


@router.get("/novels/{novel_id}/characters-list", response_model=NovelCharactersResponse)
async def get_novel_characters_for_revision(
    novel_id: str,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """获取小说的角色列表（用于修订时选择角色）"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        characters = await service.get_novel_characters(novel_id)
        
        character_items = [
            CharacterListItem(
                id=c['id'],
                name=c['name'],
                role_type=c.get('role_type'),
                personality=c.get('personality'),
                background=c.get('background')
            )
            for c in characters
        ]
        
        return NovelCharactersResponse(characters=character_items)
    except Exception as e:
        logger.error(f"获取角色列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")


@router.get("/novels/{novel_id}/chapters-list", response_model=NovelChaptersResponse)
async def get_novel_chapters_for_revision(
    novel_id: str,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """获取小说的章节列表（用于修订时选择章节）"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        chapters = await service.get_novel_chapters(novel_id)
        
        chapter_items = [
            ChapterListItem(
                id=c['id'],
                chapter_number=c['chapter_number'],
                title=c.get('title'),
                word_count=c.get('word_count', 0),
                status=c.get('status')
            )
            for c in chapters
        ]
        
        return NovelChaptersResponse(chapters=chapter_items)
    except Exception as e:
        logger.error(f"获取章节列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取章节列表失败: {str(e)}")
