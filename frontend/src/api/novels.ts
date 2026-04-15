import apiClient from './client';
import type { Novel, NovelCreate, NovelUpdate, PaginatedResponse } from './types';

export async function getNovels(
  page = 1,
  pageSize = 10,
  status?: string,
  keyword?: string,
): Promise<PaginatedResponse<Novel>> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (status) params.status = status;
  if (keyword) params.keyword = keyword;
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

// 世界观相关
export async function updateWorldSetting(novelId: string, payload: any): Promise<any> {
  const { data } = await apiClient.patch(`/novels/${novelId}/world-setting`, payload);
  return data;
}

// 大纲相关
export async function updatePlotOutline(novelId: string, payload: any): Promise<any> {
  const { data } = await apiClient.patch(`/novels/${novelId}/outline`, payload);
  return data;
}

// 角色相关
export async function updateCharacter(novelId: string, characterId: string, payload: any): Promise<any> {
  const { data } = await apiClient.patch(`/novels/${novelId}/characters/${characterId}`, payload);
  return data;
}

// 章节相关
export async function updateChapter(novelId: string, chapterNumber: number, payload: any): Promise<any> {
  const { data } = await apiClient.patch(`/novels/${novelId}/chapters/${chapterNumber}`, payload);
  return data;
}
