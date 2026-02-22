import apiClient from './client';
import type { GenerationTask, GenerationTaskCreate, PaginatedResponse } from './types';

export async function createGenerationTask(
  payload: GenerationTaskCreate,
): Promise<GenerationTask> {
  const { data } = await apiClient.post('/generation/tasks', payload);
  return data;
}

export async function getGenerationTasks(
  novelId?: string,
  status?: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedResponse<GenerationTask>> {
  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (novelId) params.novel_id = novelId;
  if (status) params.status = status;
  const { data } = await apiClient.get('/generation/tasks', { params });
  return data;
}

export async function getGenerationTask(taskId: string): Promise<GenerationTask> {
  const { data } = await apiClient.get(`/generation/tasks/${taskId}`);
  return data;
}

export async function cancelGenerationTask(
  taskId: string,
): Promise<{ message: string; task_id: string }> {
  const { data } = await apiClient.post(`/generation/tasks/${taskId}/cancel`);
  return data;
}
