/**
 * User profile service.
 * Maps to FastAPI endpoints under /api/v1/user-profiles/
 */

import { api } from "@/lib/api-client";
import type {
  UserProfileCreate,
  UserProfileResponse,
  UserProfileUpdate,
} from "@/lib/types/api";

// ─── Endpoints ────────────────────────────────────────────────────────────────

const BASE = "/api/v1/user-profiles";

export const profileService = {
  /**
   * POST /api/v1/user-profiles/ — create profile for current user
   */
  async createProfile(data: UserProfileCreate): Promise<UserProfileResponse> {
    return api.post<UserProfileResponse>(`${BASE}/`, data);
  },

  /**
   * GET /api/v1/user-profiles/me — get own profile
   */
  async getMyProfile(): Promise<UserProfileResponse> {
    return api.get<UserProfileResponse>(`${BASE}/me`);
  },

  /**
   * PUT /api/v1/user-profiles/me — update own profile
   */
  async updateMyProfile(
    data: UserProfileUpdate
  ): Promise<UserProfileResponse> {
    return api.put<UserProfileResponse>(`${BASE}/me`, data);
  },

  /**
   * GET /api/v1/user-profiles/{user_id}
   */
  async getProfileById(userId: string): Promise<UserProfileResponse> {
    return api.get<UserProfileResponse>(`${BASE}/${userId}`);
  },

  /**
   * PUT /api/v1/user-profiles/{user_id}
   */
  async updateProfileById(
    userId: string,
    data: UserProfileUpdate
  ): Promise<UserProfileResponse> {
    return api.put<UserProfileResponse>(`${BASE}/${userId}`, data);
  },
};
