/**
 * Workout plan service.
 * Maps to FastAPI endpoints under /api/v1/workout-plans/
 */

import { api } from "@/lib/api-client";
import type {
  WorkoutItemCreate,
  WorkoutItemResponse,
  WorkoutItemUpdate,
  WorkoutPlanCreate,
  WorkoutPlanDetailResponse,
  WorkoutPlanResponse,
  WorkoutPlanUpdate,
  WorkoutPlanWithItemsCreate,
} from "@/lib/types/api";

// ─── Endpoints ────────────────────────────────────────────────────────────────

const BASE = "/api/v1/workout-plans";

export const workoutService = {
  // ── Workout Plans ──────────────────────────────────────────────────────────

  /**
   * POST /api/v1/workout-plans/ — create an empty workout plan
   */
  async createPlan(data: WorkoutPlanCreate): Promise<WorkoutPlanResponse> {
    return api.post<WorkoutPlanResponse>(`${BASE}/`, data);
  },

  /**
   * POST /api/v1/workout-plans/with-items — create plan with items in one call
   */
  async createPlanWithItems(
    data: WorkoutPlanWithItemsCreate
  ): Promise<WorkoutPlanDetailResponse> {
    return api.post<WorkoutPlanDetailResponse>(`${BASE}/with-items`, data);
  },

  /**
   * GET /api/v1/workout-plans/user — list own workout plans
   */
  async getMyPlans(params?: {
    skip?: number;
    limit?: number;
  }): Promise<WorkoutPlanResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api.get<WorkoutPlanResponse[]>(
      `${BASE}/user${qs ? `?${qs}` : ""}`
    );
  },

  /**
   * GET /api/v1/workout-plans/user/{user_id} — list user's plans
   */
  async getPlansByUser(
    userId: string,
    params?: { skip?: number; limit?: number }
  ): Promise<WorkoutPlanResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api.get<WorkoutPlanResponse[]>(
      `${BASE}/user/${userId}${qs ? `?${qs}` : ""}`
    );
  },

  /**
   * GET /api/v1/workout-plans/user/{user_id}/active — get active plan
   */
  async getActivePlan(userId: string): Promise<WorkoutPlanDetailResponse> {
    return api.get<WorkoutPlanDetailResponse>(
      `${BASE}/user/${userId}/active`
    );
  },

  /**
   * POST /api/v1/workout-plans/generate — auto-generate a workout plan from the user's nutrition goal
   */
  async generatePlan(): Promise<WorkoutPlanDetailResponse> {
    return api.post<WorkoutPlanDetailResponse>(`${BASE}/generate`, {});
  },

  /**
   * GET /api/v1/workout-plans/{plan_id} — get plan detail with items
   */
  async getPlanById(planId: string): Promise<WorkoutPlanDetailResponse> {
    return api.get<WorkoutPlanDetailResponse>(`${BASE}/${planId}`);
  },

  /**
   * PUT /api/v1/workout-plans/{plan_id} — update a plan
   */
  async updatePlan(
    planId: string,
    data: WorkoutPlanUpdate
  ): Promise<WorkoutPlanResponse> {
    return api.put<WorkoutPlanResponse>(`${BASE}/${planId}`, data);
  },

  /**
   * DELETE /api/v1/workout-plans/{plan_id}
   */
  async deletePlan(planId: string): Promise<void> {
    return api.delete<void>(`${BASE}/${planId}`);
  },

  // ── Workout Items ──────────────────────────────────────────────────────────

  /**
   * POST /api/v1/workout-plans/{plan_id}/items — add item to plan
   */
  async addItem(
    planId: string,
    data: WorkoutItemCreate
  ): Promise<WorkoutItemResponse> {
    return api.post<WorkoutItemResponse>(`${BASE}/${planId}/items`, data);
  },

  /**
   * PUT /api/v1/workout-plans/items/{item_id} — update a workout item
   */
  async updateItem(
    itemId: string,
    data: WorkoutItemUpdate
  ): Promise<WorkoutItemResponse> {
    return api.put<WorkoutItemResponse>(`${BASE}/items/${itemId}`, data);
  },

  /**
   * DELETE /api/v1/workout-plans/items/{item_id}
   */
  async deleteItem(itemId: string): Promise<void> {
    return api.delete<void>(`${BASE}/items/${itemId}`);
  },
};
