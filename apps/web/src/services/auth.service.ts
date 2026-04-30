/**
 * Auth service.
 * Maps to FastAPI endpoints under /api/v1/auth/
 */

import { apiClient, TOKEN_KEY } from "@/lib/api-client";
import type { UserCreate, Token, UserResponse } from "@/lib/types/api";

// ─── Auth Service ────────────────────────────────────────────────────────────

export const authService = {
  /**
   * POST /api/v1/auth/login
   * Backend expects OAuth2 form-data: username (email) + password
   */
  async login(email: string, password: string): Promise<Token> {
    const params = new URLSearchParams();
    params.set("username", email);
    params.set("password", password);
    const response = await apiClient.post<Token>(
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
   * Store token in localStorage
   */
  setToken(token: string): void {
    if (typeof window !== "undefined") {
      localStorage.setItem(TOKEN_KEY, token);
    }
  },

  /**
   * Clear token from localStorage
   */
  logout(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem(TOKEN_KEY);
    }
  },
};
