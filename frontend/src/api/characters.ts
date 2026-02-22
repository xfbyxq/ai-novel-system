import apiClient from './client';
import type { Character, CharacterCreate, CharacterRelationships } from './types';

export async function getCharacters(novelId: string): Promise<Character[]> {
  const { data } = await apiClient.get(`/novels/${novelId}/characters`);
  return data;
}

export async function getCharacter(novelId: string, characterId: string): Promise<Character> {
  const { data } = await apiClient.get(`/novels/${novelId}/characters/${characterId}`);
  return data;
}

export async function createCharacter(
  novelId: string,
  payload: CharacterCreate,
): Promise<Character> {
  const { data } = await apiClient.post(`/novels/${novelId}/characters`, payload);
  return data;
}

export async function updateCharacter(
  novelId: string,
  characterId: string,
  payload: Partial<CharacterCreate>,
): Promise<Character> {
  const { data } = await apiClient.patch(
    `/novels/${novelId}/characters/${characterId}`,
    payload,
  );
  return data;
}

export async function deleteCharacter(novelId: string, characterId: string): Promise<void> {
  await apiClient.delete(`/novels/${novelId}/characters/${characterId}`);
}

export async function getCharacterRelationships(
  novelId: string,
): Promise<CharacterRelationships> {
  const { data } = await apiClient.get(`/novels/${novelId}/characters/relationships`);
  return data;
}
