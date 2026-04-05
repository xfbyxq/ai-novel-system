"""AI Chat API Schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class AIChatSessionCreate(BaseModel):
    """创建AI对话会话的请求模型."""

    scene: str = Field(
        ...,
        description="对话场景：novel_creation(小说创建)、crawler_task(爬虫任务)、novel_revision(小说修订)、novel_analysis(小说分析)",
    )
    context: Optional[dict] = Field(
        None, description="可选的上下文信息，如 {novel_id: '...', chapter_number: 1}"
    )


class AIChatSessionResponse(BaseModel):
    """AI对话会话响应模型."""

    session_id: str = Field(..., description="会话唯一标识符，用于后续消息交互")
    scene: str = Field(..., description="对话场景")
    welcome_message: str = Field(..., description="AI的欢迎消息或系统初始提示")
    created_at: str = Field(..., description="会话创建时间（ISO 8601格式）")


class AIChatMessageCreate(BaseModel):
    """发送消息的请求模型."""

    message: str = Field(..., description="用户输入的消息内容")


class AIChatMessageResponse(BaseModel):
    """AI消息响应模型."""

    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="AI回复的消息内容")
    role: str = Field(default="assistant", description="消息角色，固定为assistant")
    created_at: str = Field(..., description="消息创建时间（ISO 8601格式）")


class AIChatStreamChunk(BaseModel):
    """WebSocket流式响应块."""

    chunk: str = Field(..., description="响应文本片段")
    done: bool = Field(default=False, description="是否为最后一个响应块")


class NovelParseRequest(BaseModel):
    """小说意图解析请求."""

    user_input: str = Field(..., description="用户输入的自然语言描述")


class NovelParseResponse(BaseModel):
    """小说意图解析响应（将自然语言转换为结构化数据）."""

    title: str = Field(..., description="AI建议的小说标题")
    genre: str = Field(..., description="识别的小说类型")
    tags: list[str] = Field(default_factory=list, description="提取的标签列表")
    synopsis: str = Field(..., description="生成的简介/大纲")


class CrawlerParseRequest(BaseModel):
    """爬虫任务意图解析请求."""

    user_input: str = Field(
        ..., description="用户输入的自然语言描述，如'爬取起点月票榜前10本书'"
    )


class CrawlerParseResponse(BaseModel):
    """爬虫任务意图解析响应."""

    crawl_type: str = Field(
        ..., description="爬取类型：ranking(排行榜)、book_detail(书籍详情)等"
    )
    ranking_type: str = Field(
        default="yuepiao", description="排行榜类型：yuepiao/recommend等"
    )
    max_pages: int = Field(default=3, description="最大爬取页数")
    book_ids: str = Field(default="", description="指定的书籍ID列表，多个用逗号分隔")


# 新增：结构化建议相关Schema
class RevisionSuggestion(BaseModel):
    """单个修订建议."""

    type: str = Field(
        ...,
        description="建议类型：novel(小说基本信息)、world_setting(世界观)、character(角色)、outline(大纲)、chapter(章节)",
    )
    target_id: Optional[str] = Field(
        None, description="目标对象ID（对于character/chapter类型必须有值）"
    )
    target_name: Optional[str] = Field(
        None, description="目标对象名称（如角色名、章节标题）"
    )
    field: Optional[str] = Field(
        None, description="要修改的字段名，如name、personality、content等"
    )
    suggested_value: Optional[str] = Field(
        None, description="建议的新值（复杂对象会序列化为JSON字符串）"
    )
    description: str = Field(default="", description="修改原因和描述（给用户的解释）")
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="建议的置信度（0.0-1.0）"
    )


class ExtractSuggestionsRequest(BaseModel):
    """提取建议请求."""

    novel_id: str = Field(..., description="小说ID")
    ai_response: str = Field(..., description="AI响应文本")
    revision_type: str = Field(default="general", description="修订类型")


class ExtractSuggestionsResponse(BaseModel):
    """提取建议响应."""

    suggestions: List[RevisionSuggestion] = Field(
        default_factory=list, description="提取的建议列表"
    )


class ApplySuggestionRequest(BaseModel):
    """应用单个建议请求."""

    novel_id: str = Field(..., description="小说ID")
    suggestion: RevisionSuggestion = Field(..., description="要应用的建议")


class ApplySuggestionsRequest(BaseModel):
    """批量应用建议请求."""

    novel_id: str = Field(..., description="小说ID")
    suggestions: List[RevisionSuggestion] = Field(..., description="要应用的建议列表")


class ApplySuggestionResult(BaseModel):
    """应用建议结果."""

    success: bool = Field(..., description="是否成功")
    type: Optional[str] = Field(None, description="建议类型")
    field: Optional[str] = Field(None, description="修改的字段")
    character_name: Optional[str] = Field(
        None, description="角色名称（如果是角色修改）"
    )
    chapter_number: Optional[int] = Field(None, description="章节号（如果是章节修改）")
    error: Optional[str] = Field(None, description="错误信息")


class ApplySuggestionsResponse(BaseModel):
    """批量应用建议响应."""

    total: int = Field(..., description="总建议数")
    success_count: int = Field(..., description="成功数")
    failed_count: int = Field(..., description="失败数")
    details: List[ApplySuggestionResult] = Field(
        default_factory=list, description="详细结果"
    )


class CharacterListItem(BaseModel):
    """角色列表项."""

    id: str = Field(..., description="角色ID")
    name: str = Field(..., description="角色名称")
    role_type: Optional[str] = Field(None, description="角色类型")
    personality: Optional[str] = Field(None, description="性格")
    background: Optional[str] = Field(None, description="背景")


class ChapterListItem(BaseModel):
    """章节列表项."""

    id: str = Field(..., description="章节ID")
    chapter_number: int = Field(..., description="章节号")
    title: Optional[str] = Field(None, description="章节标题")
    word_count: int = Field(default=0, description="字数")
    status: Optional[str] = Field(None, description="状态")


class NovelCharactersResponse(BaseModel):
    """角色列表响应."""

    characters: List[CharacterListItem] = Field(
        default_factory=list, description="角色列表"
    )


class NovelChaptersResponse(BaseModel):
    """章节列表响应."""

    chapters: List[ChapterListItem] = Field(
        default_factory=list, description="章节列表"
    )


# 新增：会话管理相关Schema
class SessionListItem(BaseModel):
    """会话列表项."""

    session_id: str = Field(..., description="会话ID")
    scene: str = Field(..., description="对话场景")
    novel_id: Optional[str] = Field(None, description="关联的小说ID")
    created_at: str = Field(..., description="创建时间")
    message_count: Optional[int] = Field(None, description="消息数量")


class SessionListResponse(BaseModel):
    """会话列表响应."""

    sessions: List[SessionListItem] = Field(
        default_factory=list, description="会话列表"
    )


class SessionMessage(BaseModel):
    """会话消息."""

    role: str = Field(..., description="消息角色：user/assistant/system")
    content: str = Field(..., description="消息内容")
    created_at: Optional[str] = Field(None, description="消息时间")


class SessionDetailResponse(BaseModel):
    """会话详情响应."""

    session_id: str = Field(..., description="会话ID")
    scene: str = Field(..., description="对话场景")
    context: Optional[dict] = Field(None, description="会话上下文")
    messages: List[SessionMessage] = Field(default_factory=list, description="消息列表")


class MessageResponse(BaseModel):
    """通用消息响应."""

    message: str = Field(..., description="操作结果消息")


# 自然语言修订相关Schema
class NaturalRevisionRequest(BaseModel):
    """自然语言修订请求."""

    novel_id: str = Field(..., description="小说ID")
    instruction: str = Field(..., description="用户的自然语言指令，如「把主角年龄改成25岁」")


class RevisionPreview(BaseModel):
    """修订预览."""

    preview_id: str = Field(..., description="预览ID，用于确认执行")
    action: str = Field(..., description="操作类型：update/update_field/add/delete")
    target_type: str = Field(
        ..., description="目标类型：character/world_setting/outline/novel/chapter"
    )
    target_name: Optional[str] = Field(None, description="目标名称")
    target_id: Optional[str] = Field(None, description="目标ID")
    field: Optional[str] = Field(None, description="要修改的字段")
    old_value: Optional[str] = Field(None, description="旧值")
    new_value: Optional[str] = Field(None, description="新值")
    description: str = Field(..., description="操作描述")


class NaturalRevisionResponse(BaseModel):
    """自然语言修订响应."""

    preview: Optional[RevisionPreview] = Field(None, description="修订预览")
    message: str = Field(..., description="AI的说明消息")
    needs_confirmation: bool = Field(default=True, description="是否需要用户确认")
    error: Optional[str] = Field(None, description="错误信息")


class ExecuteRevisionRequest(BaseModel):
    """确认执行修订请求."""

    novel_id: str = Field(..., description="小说ID")
    preview_id: str = Field(..., description="预览ID")


class ExecuteRevisionResponse(BaseModel):
    """执行修订响应."""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="执行结果消息")
    action: Optional[str] = Field(None, description="执行的操作类型")
    field: Optional[str] = Field(None, description="修改的字段")
    target_name: Optional[str] = Field(None, description="目标名称")
    error: Optional[str] = Field(None, description="错误信息")
