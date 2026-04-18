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
  length_type: 'short' | 'medium' | 'long';
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
  length_type?: 'short' | 'medium' | 'long';
}

export interface NovelUpdate {
  title?: string;
  genre?: string;
  tags?: string[];
  synopsis?: string;
  status?: string;
  cover_url?: string;
  target_platform?: string;
  length_type?: 'short' | 'medium' | 'long';
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
// --- VolumeInfo (增强版卷信息) ---
export interface VolumeInfo {
  number: number;
  title: string;
  summary?: string;
  chapters: number[];  // [start, end]
  
  // 核心冲突
  core_conflict?: string;
  
  // 主线事件
  main_events?: Array<{
    chapter: number;
    event: string;
    impact: string;
  }>;
  
  // 关键转折点
  key_turning_points?: Array<{
    chapter: number;
    event: string;
    significance: string;
  }>;
  
  // 张力循环
  tension_cycles?: Array<{
    chapters: number[];  // [start, end]
    suppress_events: string[];
    release_event: string;
    tension_level?: number;  // 0-10
  }>;
  
  // 情感弧线
  emotional_arc?: string;
  
  // 角色发展弧线
  character_arcs?: Array<{
    character_id?: string;
    arc_description: string;
    key_moments: number[];  // 关键章节号
  }>;
  
  // 支线情节
  side_plots?: Array<{
    name: string;
    description: string;
    chapters: number[];  // [start, end]
  }>;
  
  // 伏笔分配
  foreshadowing?: Array<{
    description: string;
    setup_chapter: number;
    payoff_chapter: number;
  }>;
  
  // 主题
  themes?: string[];
  
  // 字数范围
  word_count_range?: number[];  // [min, max]
}

export interface PlotOutline {
  id: string;
  novel_id: string;
  structure_type: string | null;
  volumes: VolumeInfo[] | null;
  main_plot: Record<string, unknown> | null;
  sub_plots: unknown[] | null;
  key_turning_points: unknown[] | null;
  climax_chapter: number | null;
  version: number;
  created_at: string;
  updated_at: string;
}

// --- GenerationTask ---
export interface GenerationTask {
  id: string;
  novel_id: string;
  task_type: 'planning' | 'writing' | 'editing' | 'batch_writing' | 'outline_refinement';
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
  task_type: 'planning' | 'writing' | 'batch_writing' | 'outline_refinement';
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

// ============================================================
// 爬虫系统类型
// ============================================================

// --- CrawlerTask ---
export type CrawlType = 'ranking' | 'trending_tags' | 'book_metadata' | 'genre_list';
export type CrawlTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface CrawlerTask {
  id: string;
  task_name: string;
  platform: string;
  crawl_type: CrawlType;
  config: Record<string, unknown> | null;
  status: CrawlTaskStatus;
  progress: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface CrawlerTaskCreate {
  task_name: string;
  platform?: string;
  crawl_type: CrawlType;
  config?: Record<string, unknown>;
}

// --- CrawlResult ---
export interface CrawlResult {
  id: string;
  crawler_task_id: string;
  platform: string;
  data_type: string;
  raw_data: Record<string, unknown> | null;
  processed_data: Record<string, unknown> | null;
  url: string | null;
  created_at: string;
}

// --- MarketData ---
export interface MarketDataItem {
  book_id: string | null;
  book_title: string | null;
  author_name: string | null;
  genre: string | null;
  tags: string[] | null;
  rating: number | null;
  word_count: number | null;
  trend_score: number | null;
  source: string;
  data_date: string | null;
}

// --- ReaderPreference ---
export interface ReaderPreference {
  id: string;
  source: string;
  genre: string | null;
  tags: string[] | null;
  ranking_data: Record<string, unknown> | null;
  comment_sentiment: Record<string, unknown> | null;
  trend_score: number | null;
  data_date: string | null;
  crawler_task_id: string | null;
  book_id: string | null;
  book_title: string | null;
  author_name: string | null;
  rating: number | null;
  word_count: number | null;
  created_at: string;
}

// ============================================================
// 发布系统类型
// ============================================================

// --- PlatformAccount ---
export type AccountStatus = 'active' | 'inactive' | 'invalid' | 'suspended';

export interface PlatformAccount {
  id: string;
  platform: string;
  account_name: string;
  username: string;
  status: AccountStatus;
  last_login_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface PlatformAccountCreate {
  platform?: string;
  account_name: string;
  username: string;
  password: string;
  extra_credentials?: Record<string, unknown>;
}

export interface PlatformAccountUpdate {
  account_name?: string;
  password?: string;
  extra_credentials?: Record<string, unknown>;
  status?: string;
}

// --- PublishTask ---
export type PublishType = 'create_book' | 'publish_chapter' | 'batch_publish';
export type PublishTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface PublishTask {
  id: string;
  novel_id: string;
  account_id: string;
  publish_type: PublishType;
  config: Record<string, unknown> | null;
  status: PublishTaskStatus;
  progress: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
  platform_book_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface PublishTaskCreate {
  novel_id: string;
  account_id: string;
  publish_type: PublishType;
  config?: Record<string, unknown>;
  from_chapter?: number;
  to_chapter?: number;
}

// --- ChapterPublish ---
export type ChapterPublishStatus = 'pending' | 'publishing' | 'published' | 'failed';

export interface ChapterPublish {
  id: string;
  publish_task_id: string;
  chapter_id: string;
  chapter_number: number;
  status: ChapterPublishStatus;
  platform_chapter_id: string | null;
  error_message: string | null;
  published_at: string | null;
  created_at: string;
}

// --- PublishPreview ---
export interface ChapterPreviewItem {
  chapter_number: number;
  title: string;
  word_count: number;
  status: string;
  is_published: boolean;
  published_at: string | null;
}

export interface PublishPreview {
  novel_id: string;
  novel_title: string;
  total_chapters: number;
  unpublished_count: number;
  chapters: ChapterPreviewItem[];
}

// 智能完善相关接口
export interface EnhancementPreviewResponse {
  original_outline: PlotOutline;
  enhanced_outline: PlotOutline;
  quality_comparison: {
    original_score: number;
    enhanced_score: number;
    improvement: number;
    dimension_improvements: Record<string, number>;
  };
  improvements_made: string[];
  processing_time: number;
  cost_estimate: number;
}

export interface OutlineQualityReport {
  overall_score: number;
  dimension_scores: Record<string, number>;
  strengths: string[];
  weaknesses: string[];
  improvement_suggestions: Array<{
    type: string;
    priority: string;
    description: string;
    details: string[];
  }>;
}

export interface BatchAIAssistRequest {
  fields?: string[];
  current_values: Record<string, string>;
  preserve_user_edits: boolean;
  additional_hints?: string;
}

export interface BatchFieldResult {
  field_name: string;
  suggestion: string;
  original_value: string;
  status: 'success' | 'failed' | 'skipped';
  error_message?: string;
}

export interface BatchAIAssistResponse {
  results: BatchFieldResult[];
  total_fields: number;
  success_count: number;
  skipped_count: number;
  failed_count: number;
  processing_time: number;
}
