/**
 * Nutrition goal service.
 * Maps to FastAPI endpoints under /api/v1/nutrition-goals/
 */

import { api } from "@/lib/api-client";
import type {
  NutritionGoalCalculateRequest,
  NutritionGoalCalculateResponse,
  NutritionGoalCreate,
  NutritionGoalResponse,
  NutritionGoalUpdate,
} from "@/lib/types/api";

// ─── Endpoints ────────────────────────────────────────────────────────────────

const BASE = "/api/v1/nutrition-goals";

export const nutritionGoalService = {
  /**
   * POST /api/v1/nutrition-goals/calculate — preview calculated targets
   * NOTE: Requires profile. Returns BMI/BMR/TDEE and daily macro targets.
   */
  async calculateTargets(
    data: NutritionGoalCalculateRequest
  ): Promise<NutritionGoalCalculateResponse> {
    return api.post<NutritionGoalCalculateResponse>(
      `${BASE}/calculate`,
      data
    );
  },

  /**
   * POST /api/v1/nutrition-goals/ — create a nutrition goal (activates it)
   */
  async createGoal(data: NutritionGoalCreate): Promise<NutritionGoalResponse> {
    return api.post<NutritionGoalResponse>(`${BASE}/`, data);
  },

  /**
   * GET /api/v1/nutrition-goals/active — get own active nutrition goal
   */
  async getActiveGoal(): Promise<NutritionGoalResponse> {
    return api.get<NutritionGoalResponse>(`${BASE}/active`);
  },

  /**
   * GET /api/v1/nutrition-goals/{user_id}/active — get user's active goal
   */
  async getActiveGoalByUserId(
    userId: string
  ): Promise<NutritionGoalResponse> {
    return api.get<NutritionGoalResponse>(`${BASE}/${userId}/active`);
  },

  /**
   * PUT /api/v1/nutrition-goals/{goal_id} — update a goal
   * NOTE: Backend does NOT expose this endpoint.
   * The goals page uses POST / (create new, deactivate old) instead.
   */
  async updateGoal(
    goalId: string,
    data: NutritionGoalUpdate
  ): Promise<NutritionGoalResponse> {
    return api.put<NutritionGoalResponse>(`${BASE}/${goalId}`, data);
  },

  /**
   * DELETE /api/v1/nutrition-goals/{goal_id} — deactivate/delete a goal
   * NOTE: Backend does NOT expose this endpoint.
   */
  async deleteGoal(goalId: string): Promise<void> {
    return api.delete<void>(`${BASE}/${goalId}`);
  },
};
