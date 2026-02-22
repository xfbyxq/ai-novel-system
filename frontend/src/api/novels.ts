import apiClient from './client';
import type { Novel, NovelCreate, NovelUpdate, PaginatedResponse } from './types';

export async function getNovels(
  page = 1,
  pageSize = 10,
  status?: string,
): Promise<PaginatedResponse<Novel>> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (status) params.status = status;
  const { data } = await apiClient.get('/novels', { params });
  return data;
}

export async function getNovel(id: string): Promise<Novel> {
  const { data } = await apiClient.get(`/novels/${id}`);
  return data;
}

export async function createNovel(payload: NovelCreate): Promise<Novel> {
  const { data } = await apiClient.post('/novels', payload);
  return data;
}

export async function updateNovel(id: string, payload: NovelUpdate): Promise<Novel> {
  const { data } = await apiClient.patch(`/novels/${id}`, payload);
  return data;
}

export async function deleteNovel(id: string): Promise<void> {
  await apiClient.delete(`/novels/${id}`);
}
