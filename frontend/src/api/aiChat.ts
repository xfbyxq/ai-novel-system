import apiClient from './client';

export interface AIChatSessionCreate {
  scene: 'novel_creation' | 'crawler_task' | 'novel_revision' | 'novel_analysis' | 'chapter_assistant';
  context?: Record<string, unknown>;
}

export interface AIChatSessionResponse {
  session_id: string;
  scene: string;
  welcome_message: string;
  created_at: string;
}

export interface AIChatMessageCreate {
  message: string;
}

export interface AIChatMessageResponse {
  session_id: string;
  message: string;
  role: string;
  created_at: string;
}

// 结构化建议相关类型
export interface RevisionSuggestion {
  type: 'world_setting' | 'character' | 'outline' | 'chapter';
  target_id?: string | null;
  target_name?: string | null;
  field?: string | null;
  suggested_value?: string | null;
  description: string;
  confidence: number;
}

export interface ExtractSuggestionsRequest {
  novel_id: string;
  ai_response: string;
  revision_type?: string;
}

export interface ExtractSuggestionsResponse {
  suggestions: RevisionSuggestion[];
}

export interface ApplySuggestionRequest {
  novel_id: string;
  suggestion: RevisionSuggestion;
}

export interface ApplySuggestionsRequest {
  novel_id: string;
  suggestions: RevisionSuggestion[];
}

export interface ApplySuggestionResult {
  success: boolean;
  type?: string;
  field?: string;
  character_name?: string;
  chapter_number?: number;
  error?: string;
}

export interface ApplySuggestionsResponse {
  total: number;
  success_count: number;
  failed_count: number;
  details: ApplySuggestionResult[];
}

export interface CharacterListItem {
  id: string;
  name: string;
  role_type?: string;
  personality?: string;
  background?: string;
}

export interface ChapterListItem {
  id: string;
  chapter_number: number;
  title?: string;
  word_count: number;
  status?: string;
}

export interface NovelCharactersResponse {
  characters: CharacterListItem[];
}

export interface NovelChaptersResponse {
  chapters: ChapterListItem[];
}

export const createChatSession = async (data: AIChatSessionCreate): Promise<AIChatSessionResponse> => {
  const response = await apiClient.post<AIChatSessionResponse>('/ai-chat/sessions', data);
  return response.data;
};

export const sendChatMessage = async (
  sessionId: string,
  data: AIChatMessageCreate
): Promise<AIChatMessageResponse> => {
  const response = await apiClient.post<AIChatMessageResponse>(
    `/ai-chat/sessions/${sessionId}/messages`,
    data
  );
  return response.data;
};

export const getWebSocketUrl = (sessionId: string): string => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  return `${protocol}//${host}/api/v1/ai-chat/ws/${sessionId}`;
};

export interface NovelParseRequest {
  user_input: string;
}

export interface NovelParseResponse {
  title: string;
  genre: string;
  tags: string[];
  synopsis: string;
}

export interface CrawlerParseRequest {
  user_input: string;
}

export interface CrawlerParseResponse {
  crawl_type: string;
  ranking_type: string;
  max_pages: number;
  book_ids: string;
}

export const parseNovelIntent = async (data: NovelParseRequest): Promise<NovelParseResponse> => {
  const response = await apiClient.post<NovelParseResponse>('/ai-chat/parse-novel', data);
  return response.data;
};

export const parseCrawlerIntent = async (data: CrawlerParseRequest): Promise<CrawlerParseResponse> => {
  const response = await apiClient.post<CrawlerParseResponse>('/ai-chat/parse-crawler', data);
  return response.data;
};

export interface SessionListItem {
  id: string;
  session_id: string;
  scene: string;
  novel_id?: string | null;
  title?: string | null;
  context?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail {
  session_id: string;
  scene: string;
  context?: Record<string, unknown>;
  messages: Array<{ role: string; content: string }>;
}

export const listSessions = async (scene?: string, novelId?: string): Promise<{ sessions: SessionListItem[] }> => {
  const params: Record<string, string> = {};
  if (scene) params.scene = scene;
  if (novelId) params.novel_id = novelId;
  const response = await apiClient.get<{ sessions: SessionListItem[] }>('/ai-chat/sessions', { params });
  return response.data;
};

export const getSession = async (sessionId: string): Promise<SessionDetail> => {
  const response = await apiClient.get<SessionDetail>(`/ai-chat/sessions/${sessionId}`);
  return response.data;
};

export const deleteSession = async (sessionId: string): Promise<{ message: string }> => {
  const response = await apiClient.delete<{ message: string }>(`/ai-chat/sessions/${sessionId}`);
  return response.data;
};

// 新增：结构化建议相关API
export const extractSuggestions = async (data: ExtractSuggestionsRequest): Promise<ExtractSuggestionsResponse> => {
  const response = await apiClient.post<ExtractSuggestionsResponse>('/ai-chat/extract-suggestions', data);
  return response.data;
};

export const applySuggestion = async (data: ApplySuggestionRequest): Promise<ApplySuggestionResult> => {
  const response = await apiClient.post<ApplySuggestionResult>('/ai-chat/apply-suggestion', data);
  return response.data;
};

export const applySuggestions = async (data: ApplySuggestionsRequest): Promise<ApplySuggestionsResponse> => {
  const response = await apiClient.post<ApplySuggestionsResponse>('/ai-chat/apply-suggestions', data);
  return response.data;
};

export const getNovelCharactersForRevision = async (novelId: string): Promise<NovelCharactersResponse> => {
  const response = await apiClient.get<NovelCharactersResponse>(`/ai-chat/novels/${novelId}/characters-list`);
  return response.data;
};

export const getNovelChaptersForRevision = async (novelId: string): Promise<NovelChaptersResponse> => {
  const response = await apiClient.get<NovelChaptersResponse>(`/ai-chat/novels/${novelId}/chapters-list`);
  return response.data;
};

// ==================== 智能章节摘要API ====================

export interface SmartSummaryRequest {
  novel_id: string;
  chapter_numbers: number[];
  force_regenerate?: boolean;
}

export interface ChapterSummaryData {
  chapter_number: number;
  title: string;
  summary: {
    key_events?: string[];
    plot_summary?: string;
    character_interactions?: string[];
    emotional_arc?: string;
    foreshadowing?: string[];
    ending_state?: string;
    word_count?: number;
  };
  source: 'generated' | 'cached' | 'truncated';
}

export interface SmartSummaryResponse {
  novel_id: string;
  novel_title?: string;
  summaries: ChapterSummaryData[];
  total_chapters_requested: number;
  generated_count: number;
  cached_count: number;
}

export interface ChapterSummaryQuery {
  novel_id: string;
  chapter_start?: number;
  chapter_end?: number;
  use_smart_summary?: boolean;
}

/**
 * 生成智能章节摘要
 * 使用AI读取完整章节内容并提炼关键点，生成结构化的章节摘要
 */
export const generateSmartSummary = async (data: SmartSummaryRequest): Promise<SmartSummaryResponse> => {
  const response = await apiClient.post<SmartSummaryResponse>('/ai-chat/smart-summary', data);
  return response.data;
};

/**
 * 获取章节摘要（支持智能摘要模式）
 * @param data 查询参数
 */
export const getChaptersSummary = async (data: ChapterSummaryQuery): Promise<SmartSummaryResponse> => {
  const response = await apiClient.post<SmartSummaryResponse>('/ai-chat/chapters-summary', data);
  return response.data;
};

// ==================== 自然语言修订API ====================

/**
 * 自然语言修订请求
 */
export interface NaturalRevisionRequest {
  novel_id: string;
  instruction: string;
}

/**
 * 修订预览
 */
export interface RevisionPreview {
  preview_id: string;
  action: 'update_field' | 'add' | 'delete';
  target_type: 'character' | 'world_setting' | 'outline' | 'novel' | 'chapter';
  target_name?: string;
  target_id?: string;
  field?: string;
  old_value?: string;
  new_value?: string;
  description: string;
}

/**
 * 自然语言修订响应
 */
export interface NaturalRevisionResponse {
  preview?: RevisionPreview;
  message: string;
  needs_confirmation: boolean;
  error?: string;
}

/**
 * 确认执行修订请求
 */
export interface ExecuteRevisionRequest {
  novel_id: string;
  preview_id: string;
}

/**
 * 执行修订响应
 */
export interface ExecuteRevisionResponse {
  success: boolean;
  message: string;
  action?: string;
  field?: string;
  target_name?: string;
  error?: string;
}

/**
 * 解析自然语言修订指令
 * @param data 请求参数
 * @returns 预览信息和确认消息
 */
export const parseNaturalRevision = async (
  data: NaturalRevisionRequest
): Promise<NaturalRevisionResponse> => {
  const response = await apiClient.post<NaturalRevisionResponse>(
    '/ai-chat/natural-revision',
    data
  );
  return response.data;
};

/**
 * 确认执行修订操作
 * @param data 请求参数
 * @returns 执行结果
 */
export const executeRevision = async (
  data: ExecuteRevisionRequest
): Promise<ExecuteRevisionResponse> => {
  const response = await apiClient.post<ExecuteRevisionResponse>(
    '/ai-chat/execute-revision',
    data
  );
  return response.data;
};

// ==================== 章节修改建议API ====================

/**
 * 章节修改建议
 */
export interface ChapterModification {
  type: 'replace' | 'insert' | 'append';
  position: string;
  old_text?: string;
  new_text: string;
  reason: string;
  confidence: number;
}

/**
 * 提取章节修改建议请求
 */
export interface ExtractChapterSuggestionsRequest {
  novel_id: string;
  chapter_number: number;
  ai_response: string;
}

/**
 * 提取章节修改建议响应
 */
export interface ExtractChapterSuggestionsResponse {
  suggestions: ChapterModification[];
  overall_score?: number;
  pros?: string[];
  cons?: string[];
}

/**
 * 应用章节修改请求
 */
export interface ApplyChapterModificationRequest {
  novel_id: string;
  chapter_number: number;
  modification: ChapterModification;
}

/**
 * 应用章节修改响应
 */
export interface ApplyChapterModificationResponse {
  success: boolean;
  message: string;
  old_word_count?: number;
  new_word_count?: number;
}

/**
 * 从AI响应中提取章节修改建议
 * @param data 请求参数
 * @returns 结构化的修改建议
 */
export const extractChapterSuggestions = async (
  data: ExtractChapterSuggestionsRequest
): Promise<ExtractChapterSuggestionsResponse> => {
  const response = await apiClient.post<ExtractChapterSuggestionsResponse>(
    '/ai-chat/extract-chapter-suggestions',
    data
  );
  return response.data;
};

/**
 * 应用章节修改建议
 * @param data 请求参数
 * @returns 执行结果
 */
export const applyChapterModification = async (
  data: ApplyChapterModificationRequest
): Promise<ApplyChapterModificationResponse> => {
  const response = await apiClient.post<ApplyChapterModificationResponse>(
    '/ai-chat/apply-chapter-modification',
    data
  );
  return response.data;
};
