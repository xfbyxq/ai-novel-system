import apiClient from './client';

export interface AIChatSessionCreate {
  scene: 'novel_creation' | 'crawler_task' | 'novel_revision' | 'novel_analysis';
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

export const listSessions = async (scene?: string): Promise<{ sessions: SessionListItem[] }> => {
  const params = scene ? { scene } : {};
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

// 确保类型被正确导出
export type { CharacterListItem, ChapterListItem };
