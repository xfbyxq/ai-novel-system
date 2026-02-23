import apiClient from './client';
import type {
  CrawlerTask,
  CrawlerTaskCreate,
  CrawlResult,
  MarketDataItem,
  ReaderPreference,
  PaginatedResponse,
} from './types';

// ============================================================
// 爬虫任务 API
// ============================================================

export async function createCrawlerTask(
  payload: CrawlerTaskCreate,
): Promise<CrawlerTask> {
  const { data } = await apiClient.post('/crawler/tasks', payload);
  return data;
}

export async function getCrawlerTasks(params?: {
  platform?: string;
  status?: string;
  crawl_type?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<CrawlerTask>> {
  const { data } = await apiClient.get('/crawler/tasks', { params });
  return data;
}

export async function getCrawlerTask(taskId: string): Promise<CrawlerTask> {
  const { data } = await apiClient.get(`/crawler/tasks/${taskId}`);
  return data;
}

export async function cancelCrawlerTask(
  taskId: string,
): Promise<{ message: string; task_id: string }> {
  const { data } = await apiClient.post(`/crawler/tasks/${taskId}/cancel`);
  return data;
}

export async function getCrawlerTaskResults(
  taskId: string,
  params?: {
    data_type?: string;
    page?: number;
    page_size?: number;
  },
): Promise<PaginatedResponse<CrawlResult>> {
  const { data } = await apiClient.get(`/crawler/tasks/${taskId}/results`, { params });
  return data;
}

// ============================================================
// 市场数据 API
// ============================================================

export async function getMarketData(params?: {
  platform?: string;
  genre?: string;
  min_word_count?: number;
  max_word_count?: number;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<MarketDataItem>> {
  const { data } = await apiClient.get('/crawler/market-data', { params });
  return data;
}

// ============================================================
// 读者偏好 API
// ============================================================

export async function getReaderPreferences(params?: {
  source?: string;
  genre?: string;
  crawler_task_id?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<ReaderPreference>> {
  const { data } = await apiClient.get('/crawler/preferences', { params });
  return data;
}
