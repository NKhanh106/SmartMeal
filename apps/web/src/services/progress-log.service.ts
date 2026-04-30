/**
 * Progress log service.
 * Maps to FastAPI endpoints under /api/v1/progress-logs/
 */

import { api } from "@/lib/api-client";
import type {
  ProgressLogCreate,
  ProgressLogResponse,
  ProgressLogUpdate,
} from "@/lib/types/api";

// ─── Endpoints ────────────────────────────────────────────────────────────────

const BASE = "/api/v1/progress-logs";

export const progressLogService = {
  /**
   * POST /api/v1/progress-logs/ — create (or upsert by log_date)
   */
  async createLog(data: ProgressLogCreate): Promise<ProgressLogResponse> {
    return api.post<ProgressLogResponse>(`${BASE}/`, data);
  },

  /**
   * GET /api/v1/progress-logs/user — list own progress logs
   */
  async getMyLogs(params?: {
    skip?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
  }): Promise<ProgressLogResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.start_date) searchParams.set("start_date", params.start_date);
    if (params?.end_date) searchParams.set("end_date", params.end_date);
    const qs = searchParams.toString();
    return api.get<ProgressLogResponse[]>(
      `${BASE}/user${qs ? `?${qs}` : ""}`
    );
  },

  /**
   * GET /api/v1/progress-logs/user/{user_id} — list user's logs
   */
  async getLogsByUser(
    userId: string,
    params?: { skip?: number; limit?: number }
  ): Promise<ProgressLogResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    const qs = searchParams.toString();
    return api.get<ProgressLogResponse[]>(
      `${BASE}/user/${userId}${qs ? `?${qs}` : ""}`
    );
  },

  /**
   * GET /api/v1/progress-logs/user/{user_id}/latest — get latest log
   */
  async getLatestLog(userId: string): Promise<ProgressLogResponse> {
    return api.get<ProgressLogResponse>(`${BASE}/user/${userId}/latest`);
  },

  /**
   * GET /api/v1/progress-logs/{progress_log_id}
   */
  async getLogById(logId: string): Promise<ProgressLogResponse> {
    return api.get<ProgressLogResponse>(`${BASE}/${logId}`);
  },

  /**
   * PUT /api/v1/progress-logs/{progress_log_id}
   */
  async updateLog(
    logId: string,
    data: ProgressLogUpdate
  ): Promise<ProgressLogResponse> {
    return api.put<ProgressLogResponse>(`${BASE}/${logId}`, data);
  },

  /**
   * DELETE /api/v1/progress-logs/{progress_log_id}
   */
  async deleteLog(logId: string): Promise<void> {
    return api.delete<void>(`${BASE}/${logId}`);
  },
};
