import apiClient from './client';
import type {
  PlatformAccount,
  PlatformAccountCreate,
  PlatformAccountUpdate,
  PublishTask,
  PublishTaskCreate,
  ChapterPublish,
  PublishPreview,
  PaginatedResponse,
} from './types';

// ============================================================
// 平台账号 API
// ============================================================

export async function createPlatformAccount(
  payload: PlatformAccountCreate,
): Promise<PlatformAccount> {
  const { data } = await apiClient.post('/publishing/accounts', payload);
  return data;
}

export async function getPlatformAccounts(params?: {
  platform?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<PlatformAccount>> {
  const { data } = await apiClient.get('/publishing/accounts', { params });
  return data;
}

export async function getPlatformAccount(accountId: string): Promise<PlatformAccount> {
  const { data } = await apiClient.get(`/publishing/accounts/${accountId}`);
  return data;
}

export async function updatePlatformAccount(
  accountId: string,
  payload: PlatformAccountUpdate,
): Promise<PlatformAccount> {
  const { data } = await apiClient.patch(`/publishing/accounts/${accountId}`, payload);
  return data;
}

export async function deletePlatformAccount(
  accountId: string,
): Promise<{ message: string; account_id: string }> {
  const { data } = await apiClient.delete(`/publishing/accounts/${accountId}`);
  return data;
}

export async function verifyPlatformAccount(
  accountId: string,
): Promise<{ success: boolean; message: string }> {
  const { data } = await apiClient.post(`/publishing/accounts/${accountId}/verify`);
  return data;
}

// ============================================================
// 发布任务 API
// ============================================================

export async function createPublishTask(
  payload: PublishTaskCreate,
): Promise<PublishTask> {
  const { data } = await apiClient.post('/publishing/tasks', payload);
  return data;
}

export async function getPublishTasks(params?: {
  novel_id?: string;
  account_id?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<PublishTask>> {
  const { data } = await apiClient.get('/publishing/tasks', { params });
  return data;
}

export async function getPublishTask(taskId: string): Promise<PublishTask> {
  const { data } = await apiClient.get(`/publishing/tasks/${taskId}`);
  return data;
}

export async function cancelPublishTask(
  taskId: string,
): Promise<{ message: string; task_id: string }> {
  const { data } = await apiClient.post(`/publishing/tasks/${taskId}/cancel`);
  return data;
}

export async function getTaskChapterPublishes(
  taskId: string,
  params?: {
    status?: string;
    page?: number;
    page_size?: number;
  },
): Promise<PaginatedResponse<ChapterPublish>> {
  const { data } = await apiClient.get(`/publishing/tasks/${taskId}/chapters`, { params });
  return data;
}

// ============================================================
// 发布预览 API
// ============================================================

export async function getPublishPreview(params: {
  novel_id: string;
  from_chapter?: number;
  to_chapter?: number;
}): Promise<PublishPreview> {
  const { data } = await apiClient.post('/publishing/preview', params);
  return data;
}
