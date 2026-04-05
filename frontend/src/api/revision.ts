/** 修订和记忆管理 API 客户端 */

import apiClient from "./client";

/**
 * 修订反馈请求
 */
export interface RevisionFeedbackRequest {
  novel_id: string;
  feedback: string;
}

/**
 * 修订计划响应
 */
export interface RevisionPlanResponse {
  plan_id: string;
  understood_intent: string;
  confidence: number;
  targets: Array<{
    type: string;
    target_id?: string;
    target_name: string;
    field?: string;
    issue?: string;
  }>;
  proposed_changes: Array<{
    target_type: string;
    field: string;
    old_value: string;
    new_value: string;
    reasoning: string;
  }>;
  impact_assessment: {
    affected_chapters: number[];
    affected_characters: string[];
    severity: string;
  };
  display_text: string;
}

/**
 * 修订执行请求
 */
export interface RevisionExecuteRequest {
  plan_id: string;
  confirmed: boolean;
  modifications?: Record<string, string>;
}

/**
 * 执行结果响应
 */
export interface ExecutionResultResponse {
  success: boolean;
  message: string;
  changes: Array<{
    success: boolean;
    target_type: string;
    target_name: string;
    field: string;
    message: string;
  }>;
  affected_chapters: number[];
}

/**
 * 经验响应
 */
export interface LessonResponse {
  lessons: string[];
}

/**
 * 策略建议响应
 */
export interface StrategyResponse {
  recommendations: Array<{
    strategy_name: string;
    strategy_type: string;
    target_dimension: string;
    effectiveness: number;
    application_count: number;
    success_count: number;
    trend: string;
  }>;
}

/**
 * 偏好记录请求
 */
export interface PreferenceRecordRequest {
  user_id: string;
  preference_type: string;
  preference_key: string;
  preference_value: unknown;
  source?: "explicit" | "inferred";
  novel_id?: string;
  confidence?: number;
}

/**
 * 偏好响应
 */
export interface PreferenceResponse {
  id: string;
  preference_key: string;
  preference_type: string;
  confidence: number;
}

/**
 * 修订API
 */
export const revisionApi = {
  /**
   * 理解用户修订反馈，生成修订计划
   */
  async understandFeedback(request: RevisionFeedbackRequest): Promise<RevisionPlanResponse> {
    const response = await apiClient.post<RevisionPlanResponse>("/revision/understand", request);
    return response.data;
  },

  /**
   * 执行修订计划
   */
  async executePlan(request: RevisionExecuteRequest): Promise<ExecutionResultResponse> {
    const response = await apiClient.post<ExecutionResultResponse>("/revision/execute", request);
    return response.data;
  },

  /**
   * 预览修订计划的影响
   */
  async previewPlan(planId: string): Promise<RevisionPlanResponse> {
    const response = await apiClient.get<RevisionPlanResponse>(`/revision/preview/${planId}`);
    return response.data;
  },

  /**
   * 获取小说的修订计划列表
   */
  async listPlans(novelId: string): Promise<{
    plans: Array<{
      id: string;
      feedback_text: string;
      understood_intent: string;
      status: string;
      confidence: number;
      created_at: string;
    }>;
  }> {
    const response = await apiClient.get(`/revision/plans/${novelId}`);
    return response.data;
  },

  /**
   * 获取适用于当前任务的过往经验
   */
  async getLessons(
    novelId: string,
    taskType: string = "writing",
    chapter: number = 0,
    limit: number = 5
  ): Promise<LessonResponse> {
    const response = await apiClient.get<LessonResponse>("/revision/lessons/" + novelId, {
      params: { task_type: taskType, chapter, limit },
    });
    return response.data;
  },

  /**
   * 获取策略建议
   */
  async getStrategies(
    novelId: string,
    dimension?: string,
    limit: number = 5
  ): Promise<StrategyResponse> {
    const response = await apiClient.get<StrategyResponse>("/revision/strategies/" + novelId, {
      params: { dimension, limit },
    });
    return response.data;
  },

  /**
   * 记录策略应用结果
   */
  async recordStrategy(params: {
    novel_id: string;
    strategy_name: string;
    strategy_type: string;
    target_dimension: string;
    effectiveness_score: number;
  }): Promise<{
    strategy_name: string;
    avg_effectiveness: number;
    application_count: number;
    trend: string;
  }> {
    const response = await apiClient.post("/revision/strategies/record", null, { params });
    return response.data;
  },

  /**
   * 执行事后回顾
   */
  async executeReview(params: {
    novel_id: string;
    task_type: string;
    chapter_number?: number;
    initial_goal?: string;
    initial_plan?: Record<string, unknown>;
    actual_result?: string;
    outcome_score?: number;
    applied_strategies?: string[];
  }): Promise<{
    experience_id: string;
    lessons_learned: string[];
    successful_strategies: Array<{ Name: string; effectiveness: number }>;
    failed_strategies: Array<{ Name: string; issue: string }>;
    recurring_pattern?: string;
  }> {
    const response = await apiClient.post("/revision/review", null, { params });
    return response.data;
  },

  /**
   * 记录用户偏好
   */
  async recordPreference(request: PreferenceRecordRequest): Promise<PreferenceResponse> {
    const response = await apiClient.post<PreferenceResponse>("/revision/preferences", request);
    return response.data;
  },

  /**
   * 获取用户偏好列表
   */
  async getPreferences(
    userId: string,
    preferenceTypes?: string,
    minConfidence: number = 0.5
  ): Promise<{
    preferences: Array<{
      id: string;
      preference_type: string;
      preference_key: string;
      preference_value: unknown;
      confidence: number;
      source: string;
    }>;
  }> {
    const response = await apiClient.get("/revision/preferences/" + userId, {
      params: { preference_types: preferenceTypes, min_confidence: minConfidence },
    });
    return response.data;
  },

  /**
   * 获取偏好上下文文本（用于注入到Agent prompt）
   */
  async getPreferenceContext(userId: string): Promise<{ context: string }> {
    const response = await apiClient.get("/revision/preferences/" + userId + "/context");
    return response.data;
  },
};
