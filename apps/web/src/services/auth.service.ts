/**
 * Auth service.
 * Maps to FastAPI endpoints under /api/v1/auth/
 */

import { apiClient } from "@/lib/api-client";
import type { UserCreate, UserResponse } from "@/lib/types/api";

export const authService = {
  /**
   * POST /api/v1/auth/login
   * Backend expects OAuth2 form-data: username (email) + password
   * Returns access token; refresh token is set as httpOnly cookie by the backend.
   */
  async login(email: string, password: string): Promise<{ access_token: string; expires_in: number }> {
    const params = new URLSearchParams();
    params.set("username", email);
    params.set("password", password);
    const response = await apiClient.post<{ access_token: string; expires_in: number }>(
      "/api/v1/auth/login",
      params.toString(),
      {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      }
    );
    return response.data;
  },

  /**
   * POST /api/v1/auth/register
   */
  async register(data: UserCreate): Promise<UserResponse> {
    const response = await apiClient.post<UserResponse>("/api/v1/auth/register", data);
    return response.data;
  },

  /**
   * GET /api/v1/auth/me — get current authenticated user
   */
  async getCurrentUser(): Promise<UserResponse> {
    const response = await apiClient.get<UserResponse>("/api/v1/auth/me");
    return response.data;
  },

  /**
   * PATCH /api/v1/auth/me — update current user's full_name
   */
  async updateUser(data: { full_name?: string }): Promise<UserResponse> {
    const response = await apiClient.patch<UserResponse>("/api/v1/auth/me", data);
    return response.data;
  },

  /**
   * POST /api/v1/auth/logout — clear refresh token cookie and revoke it server-side
   */
  async logout(): Promise<void> {
    await apiClient.post("/api/v1/auth/logout");
  },
};
