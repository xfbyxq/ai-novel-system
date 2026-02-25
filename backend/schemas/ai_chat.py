"""AI Chat API Schemas"""

from typing import Optional, List, Any
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


# 新增：结构化建议相关Schema
class RevisionSuggestion(BaseModel):
    """单个修订建议"""
    type: str = Field(..., description="建议类型: world_setting/character/outline/chapter")
    target_id: Optional[str] = Field(None, description="目标对象ID")
    target_name: Optional[str] = Field(None, description="目标对象名称")
    field: Optional[str] = Field(None, description="要修改的字段")
    suggested_value: Optional[str] = Field(None, description="建议的新值")
    description: str = Field(default="", description="修改描述")
    confidence: float = Field(default=0.8, description="置信度")


class ExtractSuggestionsRequest(BaseModel):
    """提取建议请求"""
    novel_id: str = Field(..., description="小说ID")
    ai_response: str = Field(..., description="AI响应文本")
    revision_type: str = Field(default="general", description="修订类型")


class ExtractSuggestionsResponse(BaseModel):
    """提取建议响应"""
    suggestions: List[RevisionSuggestion] = Field(default_factory=list, description="提取的建议列表")


class ApplySuggestionRequest(BaseModel):
    """应用单个建议请求"""
    novel_id: str = Field(..., description="小说ID")
    suggestion: RevisionSuggestion = Field(..., description="要应用的建议")


class ApplySuggestionsRequest(BaseModel):
    """批量应用建议请求"""
    novel_id: str = Field(..., description="小说ID")
    suggestions: List[RevisionSuggestion] = Field(..., description="要应用的建议列表")


class ApplySuggestionResult(BaseModel):
    """应用建议结果"""
    success: bool = Field(..., description="是否成功")
    type: Optional[str] = Field(None, description="建议类型")
    field: Optional[str] = Field(None, description="修改的字段")
    character_name: Optional[str] = Field(None, description="角色名称（如果是角色修改）")
    chapter_number: Optional[int] = Field(None, description="章节号（如果是章节修改）")
    error: Optional[str] = Field(None, description="错误信息")


class ApplySuggestionsResponse(BaseModel):
    """批量应用建议响应"""
    total: int = Field(..., description="总建议数")
    success_count: int = Field(..., description="成功数")
    failed_count: int = Field(..., description="失败数")
    details: List[ApplySuggestionResult] = Field(default_factory=list, description="详细结果")


class CharacterListItem(BaseModel):
    """角色列表项"""
    id: str = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(None, description="角色类型")
    personality: Optional[str] = Field(None, description="性格")
    background: Optional[str] = Field(None, description="背景")


class ChapterListItem(BaseModel):
    """章节列表项"""
    id: str = Field(..., description="章节ID")
    chapter_number: int = Field(..., description="章节号")
    title: Optional[str] = Field(None, description="章节标题")
    word_count: int = Field(default=0, description="字数")
    status: Optional[str] = Field(None, description="状态")


class NovelCharactersResponse(BaseModel):
    """角色列表响应"""
    characters: List[CharacterListItem] = Field(default_factory=list, description="角色列表")


class NovelChaptersResponse(BaseModel):
    """章节列表响应"""
    chapters: List[ChapterListItem] = Field(default_factory=list, description="章节列表")
