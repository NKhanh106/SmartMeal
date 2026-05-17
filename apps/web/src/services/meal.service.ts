/**
 * Meal log service.
 * Maps to FastAPI endpoints under /api/v1/meal-logs/ and /api/v1/ai/meal-update/
 */

import { api, type ApiError } from "@/lib/api-client";
import type {
  MealLogCreate,
  MealLogResponse,
  MealLogSummaryResponse,
  MealUpdateConfirmRequest,
  MealUpdateConfirmResponse,
  MealUpdatePreviewResponse,
} from "@/lib/types/api";

// ─── Service ──────────────────────────────────────────────────────────────────

const MEAL_BASE = "/api/v1/meal-logs";
const AI_MEAL_BASE = "/api/v1/ai/meal-update";

export const mealService = {
  // ── Meal Logs ──────────────────────────────────────────────────────────────

  /**
   * POST /api/v1/meal-logs/ — create a meal log with items
   */
  async createMealLog(data: MealLogCreate): Promise<MealLogResponse> {
    return api.post<MealLogResponse>(`${MEAL_BASE}/`, data);
  },

  /**
   * GET /api/v1/meal-logs/user — list own meal logs (paginated)
   */
  async getMyMealLogs(params?: {
    skip?: number;
    limit?: number;
  }): Promise<MealLogSummaryResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api
      .get<MealLogSummaryResponse[]>(`${MEAL_BASE}/user${qs ? `?${qs}` : ""}`);
  },

  /**
   * GET /api/v1/meal-logs/extracted-today — get meals extracted from chat today
   */
  async getExtractedMealsToday(): Promise<MealLogSummaryResponse[]> {
    return api.get<MealLogSummaryResponse[]>(`${MEAL_BASE}/extracted-today`);
  },

  /**
   * GET /api/v1/meal-logs/user/{user_id}
   */
  async getMealLogsByUser(
    userId: string,
    params?: { skip?: number; limit?: number }
  ): Promise<MealLogSummaryResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api
      .get<MealLogSummaryResponse[]>(`${MEAL_BASE}/user/${userId}${qs ? `?${qs}` : ""}`);
  },

  /**
   * GET /api/v1/meal-logs/{meal_log_id}
   */
  async getMealLogById(mealLogId: string): Promise<MealLogResponse> {
    return api.get<MealLogResponse>(`${MEAL_BASE}/${mealLogId}`);
  },

  /**
   * DELETE /api/v1/meal-logs/{meal_log_id}
   */
  async deleteMealLog(mealLogId: string): Promise<void> {
    await api.delete<void>(`${MEAL_BASE}/${mealLogId}`);
  },

  // ── AI Meal Image Analysis ──────────────────────────────────────────────────

  /**
   * POST /api/v1/ai/meal-update/preview
   *
   * Backend expects multipart/form-data with:
   *   - image: UploadFile (binary)
   *   - meal_type: str (Form field)
   *
   * Valid meal_type values: bua_sang | bua_trua | bua_toi | an_vat | khac
   *
   * Returns a preview of AI-detected foods with nutrition estimates.
   */
  async analyzeMealImage(
    file: File,
    mealType: string
  ): Promise<MealUpdatePreviewResponse> {
    const formData = new FormData();
    formData.append("image", file);
    formData.append("meal_type", mealType);
    // Use /recognize-image endpoint which includes Redis caching for duplicate images
    return api.uploadFile<MealUpdatePreviewResponse>(
      `${AI_MEAL_BASE}/recognize-image`,
      formData
    );
  },

  /**
   * POST /api/v1/ai/meal-update/confirm
   *
   * Confirm AI-detected items and save as a meal log.
   * Returns the created meal_log_id.
   */
  async confirmMeal(
    data: MealUpdateConfirmRequest
  ): Promise<MealUpdateConfirmResponse> {
    return api.post<MealUpdateConfirmResponse>(`${AI_MEAL_BASE}/confirm`, data);
  },
};

export type { ApiError };
