import apiClient from './client';
import type { WorldSetting, PlotOutline, BatchAIAssistRequest, BatchAIAssistResponse } from './types';

export async function getWorldSetting(novelId: string): Promise<WorldSetting | null> {
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

export async function getPlotOutline(novelId: string): Promise<PlotOutline | null> {
  const { data } = await apiClient.get(`/novels/${novelId}/outline`);
  return data;
}

export async function updatePlotOutline(
  novelId: string,
  payload: Partial<PlotOutline> & {
    volumes?: Array<{
      number: number;
      title: string;
      summary?: string;
      chapters: number[];
      core_conflict?: string;
      main_events?: any[];
      key_turning_points?: any[];
      tension_cycles?: any[];
      emotional_arc?: string;
      character_arcs?: any[];
      side_plots?: any[];
      foreshadowing?: any[];
      themes?: string[];
      word_count_range?: number[];
    }>;
  },
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

export async function enhanceOutlinePreview(
  novelId: string,
  options: {
    max_iterations?: number;
    quality_threshold?: number;
    preserve_user_edits?: boolean;
    update_database?: boolean;
  }
): Promise<{
  original_outline: Record<string, unknown>;
  enhanced_outline: Record<string, unknown>;
  quality_comparison: {
    original_score: number;
    enhanced_score: number;
    improvement: number;
  };
  improvements_made: string[];
}> {
  const { data } = await apiClient.post(`/novels/${novelId}/outline/enhance-preview`, options);
  return data;
}

export async function aiAssistOutline(
  novelId: string,
  request: {
    field_name: string;
    current_context?: Record<string, unknown>;
    additional_hints?: string;
  }
): Promise<{
  field_name: string;
  suggestion: string;
  confidence?: number;
  alternatives?: string[];
  reasoning?: string;
}> {
  const { data } = await apiClient.post(`/novels/${novelId}/outline/ai-assist`, request);
  return data;
}

export async function batchAiAssistOutline(
  novelId: string,
  request: BatchAIAssistRequest,
): Promise<BatchAIAssistResponse> {
  const { data } = await apiClient.post(
    `/novels/${novelId}/outline/batch-ai-assist`,
    request,
  );
  return data;
}
