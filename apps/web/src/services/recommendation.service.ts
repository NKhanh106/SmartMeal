/**
 * Daily recommendation service.
 * Maps to FastAPI endpoints under /api/v1/ai/daily-planner/
 */

import { api } from "@/lib/api-client";
import type {
  DailyRecommendationResponse,
  GenerateDailyPlannerResponse,
} from "@/lib/types/api";

// ─── Endpoints ────────────────────────────────────────────────────────────────

const BASE = "/api/v1/ai/daily-planner";

export const recommendationService = {
  /**
   * POST /api/v1/ai/daily-planner/generate
   * Generate AI-powered daily meal + workout recommendation for current user.
   * Requires the user to have a UserProfile and an active NutritionGoal.
   * @param targetDate  YYYY-MM-DD — defaults to tomorrow if not provided
   */
  async generateRecommendation(targetDate?: string): Promise<GenerateDailyPlannerResponse> {
    const qs = targetDate ? `?target_date=${targetDate}` : "";
    return api.post<GenerateDailyPlannerResponse>(`${BASE}/generate${qs}`);
  },

  /**
   * POST /api/v1/ai/daily-planner/generate/{user_id}
   * Generate recommendation for a specific user (admin only or self).
   */
  async generateRecommendationForUser(
    userId: string,
    targetDate?: string
  ): Promise<GenerateDailyPlannerResponse> {
    const qs = targetDate ? `?target_date=${targetDate}` : "";
    return api.post<GenerateDailyPlannerResponse>(`${BASE}/generate/${userId}${qs}`);
  },

  /**
   * GET /api/v1/ai/daily-planner/date/{recommendation_date}
   * Retrieve existing recommendation for a specific date.
   */
  async getRecommendationByDate(date: string): Promise<DailyRecommendationResponse> {
    return api.get<DailyRecommendationResponse>(`${BASE}/date/${date}`);
  },

  /**
   * GET /api/v1/ai/daily-planner/{user_id}/date/{recommendation_date}
   * Retrieve user's recommendation for a specific date.
   */
  async getUserRecommendationByDate(
    userId: string,
    date: string
  ): Promise<DailyRecommendationResponse> {
    return api.get<DailyRecommendationResponse>(`${BASE}/${userId}/date/${date}`);
  },
};
