/**
 * Auth service.
 * Maps to FastAPI endpoints under /api/v1/auth/
 */

import { apiClient, TOKEN_KEY } from "@/lib/api-client";
import type { UserCreate, Token, UserResponse } from "@/lib/types/api";

// ─── Auth Service ────────────────────────────────────────────────────────────

export const REFRESH_TOKEN_KEY = "smartmeal_refresh_token";

export const authService = {
  /**
   * POST /api/v1/auth/login
   * Backend expects OAuth2 form-data: username (email) + password
   */
  async login(email: string, password: string): Promise<Token & { refresh_token?: string }> {
    const params = new URLSearchParams();
    params.set("username", email);
    params.set("password", password);
    const response = await apiClient.post<Token & { refresh_token?: string }>(
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
   * Store both tokens in localStorage
   */
  setTokens(accessToken: string, refreshToken?: string): void {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, accessToken);
      if (refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
      }
    }
  },

  /**
   * Store token in localStorage
   */
  setToken(token: string): void {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, token);
    }
  },

  /**
   * Get refresh token
   */
  getRefreshToken(): string | null {
    if (typeof window !== "undefined") {
      return localStorage.getItem(REFRESH_TOKEN_KEY);
    }
    return null;
  },

  /**
   * Clear all tokens from localStorage
   */
  logout(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
    }
  },
};
