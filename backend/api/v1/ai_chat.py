"""AI Chat API 端点"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from backend.schemas.ai_chat import (
    AIChatSessionCreate,
    AIChatSessionResponse,
    AIChatMessageCreate,
    AIChatMessageResponse,
    NovelParseRequest,
    NovelParseResponse,
    CrawlerParseRequest,
    CrawlerParseResponse,
)
from backend.services.ai_chat_service import (
    AiChatService,
    SCENE_NOVEL_CREATION,
    SCENE_CRAWLER_TASK,
)

router = APIRouter(prefix="/ai-chat", tags=["ai-chat"])

_ai_chat_service_instance: Optional[AiChatService] = None


def get_ai_chat_service() -> AiChatService:
    global _ai_chat_service_instance
    if _ai_chat_service_instance is None:
        _ai_chat_service_instance = AiChatService(db=None)
    return _ai_chat_service_instance


@router.post("/sessions", response_model=AIChatSessionResponse)
async def create_session(
    session_in: AIChatSessionCreate,
    service: AiChatService = Depends(get_ai_chat_service),
):
    """创建新的 AI 对话会话"""
    if session_in.scene not in [SCENE_NOVEL_CREATION, SCENE_CRAWLER_TASK]:
        raise HTTPException(
            status_code=400,
            detail=f"无效的场景。可选: {SCENE_NOVEL_CREATION}, {SCENE_CRAWLER_TASK}"
        )
    
    session = service.create_session(
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
    try:
        response_text = service.send_message(session_id, message_in.message)
        
        return AIChatMessageResponse(
            session_id=session_id,
            message=response_text,
            role="assistant",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
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
        result = service.parse_novel_intent(request.user_input)
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
        result = service.parse_crawler_intent(request.user_input)
        return CrawlerParseResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")
