import apiClient from './client';
import type { Chapter, ChapterUpdate, PaginatedResponse } from './types';

export async function getChapters(
  novelId: string,
  page = 1,
  pageSize = 20,
  status?: string,
): Promise<PaginatedResponse<Chapter>> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (status) params.status = status;
  const { data } = await apiClient.get(`/novels/${novelId}/chapters`, { params });
  return data;
}

export async function getChapter(novelId: string, chapterNumber: number): Promise<Chapter> {
  const { data } = await apiClient.get(`/novels/${novelId}/chapters/${chapterNumber}`);
  return data;
}

export async function updateChapter(
  novelId: string,
  chapterNumber: number,
  payload: ChapterUpdate,
): Promise<Chapter> {
  const { data } = await apiClient.patch(
    `/novels/${novelId}/chapters/${chapterNumber}`,
    payload,
  );
  return data;
}

export async function deleteChapter(
  novelId: string,
  chapterNumber: number,
): Promise<void> {
  await apiClient.delete(`/novels/${novelId}/chapters/${chapterNumber}`);
}

export async function batchDeleteChapters(
  novelId: string,
  chapterNumbers: number[],
): Promise<void> {
  await apiClient.post(`/novels/${novelId}/chapters/batch-delete`, {
    chapter_numbers: chapterNumbers,
  });
}
