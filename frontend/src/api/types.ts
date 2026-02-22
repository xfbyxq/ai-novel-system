// ============================================================
// 所有 API 数据类型定义，与后端 Pydantic schemas 对应
// ============================================================

// --- Novel ---
export interface Novel {
  id: string;
  title: string;
  author: string;
  genre: string;
  tags: string[];
  status: 'planning' | 'writing' | 'completed' | 'published';
  word_count: number;
  chapter_count: number;
  cover_url: string | null;
  synopsis: string | null;
  target_platform: string;
  estimated_revenue: number;
  actual_revenue: number;
  token_cost: number;
  created_at: string;
  updated_at: string;
}

export interface NovelCreate {
  title: string;
  genre: string;
  tags?: string[];
  synopsis?: string;
  target_platform?: string;
}

export interface NovelUpdate {
  title?: string;
  genre?: string;
  tags?: string[];
  synopsis?: string;
  status?: string;
  cover_url?: string;
  target_platform?: string;
}

// --- Character ---
export interface Character {
  id: string;
  novel_id: string;
  name: string;
  role_type: 'protagonist' | 'supporting' | 'antagonist' | 'minor' | null;
  gender: 'male' | 'female' | 'other' | null;
  age: number | null;
  appearance: string | null;
  personality: string | null;
  background: string | null;
  goals: string | null;
  abilities: Record<string, unknown> | null;
  relationships: Record<string, unknown> | null;
  growth_arc: Record<string, unknown> | null;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface CharacterCreate {
  name: string;
  role_type?: string;
  gender?: string;
  age?: number;
  appearance?: string;
  personality?: string;
  background?: string;
  goals?: string;
  abilities?: Record<string, unknown>;
  relationships?: Record<string, unknown>;
}

export interface CharacterNode {
  id: string;
  name: string;
  role_type: string | null;
}

export interface CharacterEdge {
  source: string;
  target: string;
  label: string;
}

export interface CharacterRelationships {
  nodes: CharacterNode[];
  edges: CharacterEdge[];
}

// --- Chapter ---
export interface Chapter {
  id: string;
  novel_id: string;
  chapter_number: number;
  volume_number: number;
  title: string | null;
  content: string | null;
  word_count: number;
  status: 'draft' | 'reviewing' | 'published';
  quality_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface ChapterUpdate {
  title?: string;
  content?: string;
  status?: string;
}

// --- WorldSetting ---
export interface WorldSetting {
  id: string;
  novel_id: string;
  world_name: string | null;
  world_type: string | null;
  power_system: Record<string, unknown> | null;
  geography: Record<string, unknown> | null;
  factions: unknown[] | null;
  rules: unknown[] | null;
  timeline: unknown[] | null;
  special_elements: unknown[] | null;
  created_at: string;
  updated_at: string;
}

// --- PlotOutline ---
export interface PlotOutline {
  id: string;
  novel_id: string;
  structure_type: string | null;
  volumes: unknown[] | null;
  main_plot: Record<string, unknown> | null;
  sub_plots: unknown[] | null;
  key_turning_points: unknown[] | null;
  climax_chapter: number | null;
  created_at: string;
  updated_at: string;
}

// --- GenerationTask ---
export interface GenerationTask {
  id: string;
  novel_id: string;
  task_type: 'planning' | 'writing' | 'editing' | 'batch_writing';
  phase: string | null;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  token_usage: number;
  cost: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface GenerationTaskCreate {
  novel_id: string;
  task_type: 'planning' | 'writing' | 'batch_writing';
  phase?: string;
  input_data?: Record<string, unknown>;
  // 批量写作专用字段
  from_chapter?: number;
  to_chapter?: number;
  volume_number?: number;
}

// --- Paginated Response ---
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}
