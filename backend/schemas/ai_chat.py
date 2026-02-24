"""AI Chat API Schemas"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AIChatSessionCreate(BaseModel):
    scene: str = Field(..., description="场景: novel_creation / crawler_task")
    context: Optional[dict] = Field(None, description="可选的上下文信息")


class AIChatSessionResponse(BaseModel):
    session_id: str
    scene: str
    welcome_message: str
    created_at: str


class AIChatMessageCreate(BaseModel):
    message: str = Field(..., description="用户消息内容")


class AIChatMessageResponse(BaseModel):
    session_id: str
    message: str
    role: str = "assistant"
    created_at: str


class AIChatStreamChunk(BaseModel):
    chunk: str
    done: bool = False


class NovelParseRequest(BaseModel):
    user_input: str = Field(..., description="用户输入的自然语言描述")


class NovelParseResponse(BaseModel):
    title: str = Field(..., description="小说标题建议")
    genre: str = Field(..., description="小说类型")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    synopsis: str = Field(..., description="简介/大纲")


class CrawlerParseRequest(BaseModel):
    user_input: str = Field(..., description="用户输入的自然语言描述")


class CrawlerParseResponse(BaseModel):
    crawl_type: str = Field(..., description="爬取类型")
    ranking_type: str = Field(default="yuepiao", description="排行榜类型")
    max_pages: int = Field(default=3, description="最大页数")
    book_ids: str = Field(default="", description="书籍ID列表，逗号分隔")
