/**
 * Analytics / Dashboard service.
 * Maps to FastAPI endpoints under /api/v1/dashboard/
 */

import { api } from "@/lib/api-client";
import type {
  DailyDashboardResponse,
  WeeklyDashboardResponse,
} from "@/lib/types/api";

// ─── Endpoints ────────────────────────────────────────────────────────────────

const BASE = "/api/v1/dashboard";

export const analyticsService = {
  /**
   * GET /api/v1/dashboard/today — today's nutrition dashboard for current user
   */
  async getDailyDashboard(date?: string): Promise<DailyDashboardResponse> {
    const qs = date ? `?target_date=${date}` : "";
    return api.get<DailyDashboardResponse>(`${BASE}/today${qs}`);
  },

  /**
   * GET /api/v1/dashboard/weekly — this week's nutrition dashboard
   */
  async getWeeklyDashboard(params?: {
    start_date?: string;
    end_date?: string;
  }): Promise<WeeklyDashboardResponse> {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set("start_date", params.start_date);
    if (params?.end_date) searchParams.set("end_date", params.end_date);
    const qs = searchParams.toString();
    return api.get<WeeklyDashboardResponse>(`${BASE}/weekly${qs ? `?${qs}` : ""}`);
  },

  /**
   * GET /api/v1/dashboard/user/{user_id}/today
   */
  async getDailyDashboardByUser(
    userId: string,
    date?: string
  ): Promise<DailyDashboardResponse> {
    const qs = date ? `?target_date=${date}` : "";
    return api.get<DailyDashboardResponse>(
      `${BASE}/user/${userId}/today${qs}`
    );
  },

  /**
   * GET /api/v1/dashboard/user/{user_id}/weekly
   */
  async getWeeklyDashboardByUser(
    userId: string,
    params?: { start_date?: string; end_date?: string }
  ): Promise<WeeklyDashboardResponse> {
    const searchParams = new URLSearchParams();
    if (params?.start_date) searchParams.set("start_date", params.start_date);
    if (params?.end_date) searchParams.set("end_date", params.end_date);
    const qs = searchParams.toString();
    return api.get<WeeklyDashboardResponse>(
      `${BASE}/user/${userId}/weekly${qs ? `?${qs}` : ""}`
    );
  },
};
