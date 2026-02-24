import apiClient from './client';

export interface AIChatSessionCreate {
  scene: 'novel_creation' | 'crawler_task' | 'novel_revision';
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

export const listSessions = async (scene?: string): Promise<{ sessions: any[] }> => {
  const params = scene ? { scene } : {};
  const response = await apiClient.get<{ sessions: any[] }>('/ai-chat/sessions', { params });
  return response.data;
};

export const getSession = async (sessionId: string): Promise<any> => {
  const response = await apiClient.get<any>(`/ai-chat/sessions/${sessionId}`);
  return response.data;
};

export const deleteSession = async (sessionId: string): Promise<{ message: string }> => {
  const response = await apiClient.delete<{ message: string }>(`/ai-chat/sessions/${sessionId}`);
  return response.data;
};
