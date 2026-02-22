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
