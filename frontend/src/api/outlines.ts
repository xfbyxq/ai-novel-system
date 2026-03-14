import apiClient from './client';
import type { WorldSetting, PlotOutline } from './types';

export async function getWorldSetting(novelId: string): Promise<WorldSetting> {
  const { data } = await apiClient.get(`/novels/${novelId}/world-setting`);
  return data;
}

export async function updateWorldSetting(
  novelId: string,
  payload: Partial<WorldSetting>,
): Promise<WorldSetting> {
  const { data } = await apiClient.patch(`/novels/${novelId}/world-setting`, payload);
  return data;
}

export async function getPlotOutline(novelId: string): Promise<PlotOutline> {
  const { data } = await apiClient.get(`/novels/${novelId}/outline`);
  return data;
}

export async function updatePlotOutline(
  novelId: string,
  payload: Partial<PlotOutline>,
): Promise<PlotOutline> {
  const { data } = await apiClient.patch(`/novels/${novelId}/outline`, payload);
  return data;
}

export async function generateCompleteOutline(novelId: string): Promise<{ task_id: string }> {
  const { data } = await apiClient.post(`/novels/${novelId}/outline/generate`);
  return data;
}

export async function decomposeOutline(
  novelId: string,
  config: {
    total_volumes?: number;
    total_chapters?: number;
    volumes?: Array<{
      volume_num: number;
      title: string;
      summary: string;
      chapter_range: [number, number];
      main_events?: string[];
      side_plots?: string[];
      tension_cycle?: string;
      foreshadowing?: string[];
    }>;
  },
): Promise<{ task_id: string }> {
  const { data } = await apiClient.post(`/novels/${novelId}/outline/decompose`, config);
  return data;
}

export async function getChapterOutlineTask(
  novelId: string,
  chapterNumber: number,
): Promise<{
  chapter_number: number;
  title?: string;
  mandatory_events?: string[];
  optional_events?: string[];
  foreshadowing_tasks?: string[];
  emotional_tone?: string;
  tension_position?: string;
  word_count_target?: number;
}> {
  const { data } = await apiClient.get(
    `/novels/${novelId}/chapters/${chapterNumber}/outline-task`,
  );
  return data;
}

export async function validateChapterOutline(
  novelId: string,
  chapterNumber: number,
  chapterPlan: {
    title?: string;
    content_plan?: string;
    key_events?: string[];
    word_count?: number;
  },
): Promise<{
  valid: boolean;
  suggestions?: string[];
  missing_events?: string[];
  feedback?: string;
}> {
  const { data } = await apiClient.post(
    `/novels/${novelId}/chapters/${chapterNumber}/outline/validate`,
    chapterPlan,
  );
  return data;
}

export async function getOutlineVersions(novelId: string): Promise<
  Array<{
    version_id: string;
    version_number: number;
    created_at: string;
    created_by?: string;
    change_summary?: string;
    main_plot?: Record<string, unknown>;
    volumes?: unknown[];
  }>
> {
  const { data } = await apiClient.get(`/novels/${novelId}/outline/versions`);
  return data;
}
