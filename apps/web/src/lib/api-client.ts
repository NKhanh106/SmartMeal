import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

// ─── Configuration ─────────────────────────────────────────────────────────────

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export const TOKEN_KEY = "smartmeal_access_token";

// ─── API Error ─────────────────────────────────────────────────────────────────

export interface ApiErrorResponse {
  detail?: string;
  msg?: string;
  message?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  constructor(
    public statusCode: number,
    public data: ApiErrorResponse,
    message?: string
  ) {
    super(message ?? extractMessage(data) ?? `HTTP ${statusCode}`);
    this.name = "ApiError";
  }

  /** Human-readable message extracted from any error shape */
  getUserMessage(): string {
    return extractMessage(this.data) ?? `HTTP ${this.statusCode}`;
  }

  static fromAxiosError(error: unknown): ApiError {
    if (error instanceof AxiosError) {
      const statusCode = error.response?.status ?? 0;
      const rawData = error.response?.data;

      // Normalize the data so callers always get a flat object
      const data: ApiErrorResponse = normalizeErrorData(rawData);

      return new ApiError(statusCode, data, error.message);
    }
    if (error instanceof Error) {
      return new ApiError(0, { detail: error.message }, error.message);
    }
    return new ApiError(0, { detail: "Unknown error" }, "Unknown error");
  }
}

/**
 * Extract a readable string from any error shape FastAPI / axios might return.
 * Handles:
 *   - { detail: string }
 *   - { detail: [{ type, msg, loc, input }] }  ← FastAPI 422 Zod errors
 *   - [{ type, msg, loc, input }]               ← axios raw array
 *   - { message: string }
 *   - plain string
 *   - unknown objects
 */
function extractMessage(data: unknown): string | undefined {
  if (!data) return undefined;

  // FastAPI 422: { detail: [...] } or { detail: "string" }
  if (typeof data === "object") {
    const obj = data as Record<string, unknown>;

    // String detail
    if (typeof obj.detail === "string") return obj.detail;

    // Array detail (Zod validation errors)
    if (Array.isArray(obj.detail)) {
      return obj.detail
        .slice(0, 3)
        .map((e) => {
          if (typeof e === "object" && e !== null && "msg" in e) {
            const err = e as { type?: string; msg?: string; loc?: unknown[] };
            const loc = Array.isArray(err.loc) ? err.loc.slice(1).join(".") : "";
            return loc ? `${loc}: ${err.msg}` : (err.msg ?? String(e));
          }
          return String(e);
        })
        .join("; ");
    }

    // Plain { message: "..." }
    if (typeof obj.message === "string") return obj.message;

    // Fallback: try to JSON-stringify the whole object
    try {
      return JSON.stringify(data);
    } catch {
      return undefined;
    }
  }

  if (typeof data === "string") return data;
  return undefined;
}

/** Normalize any raw error response into a flat ApiErrorResponse */
function normalizeErrorData(raw: unknown): ApiErrorResponse {
  if (!raw) return {};
  if (typeof raw === "object") {
    const obj = raw as Record<string, unknown>;

    // Already a flat object with a string detail
    if (typeof obj.detail === "string") return raw as ApiErrorResponse;

    // Array → extract first error message
    if (Array.isArray(obj.detail)) {
      const first = obj.detail[0];
      if (first && typeof first === "object" && "msg" in first) {
        const err = first as { type?: string; msg?: string; loc?: unknown[] };
        const loc = Array.isArray(err.loc) ? err.loc.slice(1).join(".") : "";
        return { detail: loc ? `${loc}: ${err.msg}` : (err.msg ?? String(first)) };
      }
      return { detail: String(first) };
    }

    // { message: "..." }
    if (typeof obj.message === "string") return { message: obj.message };

    return raw as ApiErrorResponse;
  }
  if (typeof raw === "string") return { detail: raw };
  return {};
}

// ─── HTTP Methods ──────────────────────────────────────────────────────────────

type RequestConfig = Partial<InternalAxiosRequestConfig>;

async function handleRequest<T>(promise: Promise<import("axios").AxiosResponse<T>>): Promise<T> {
  try {
    const { data } = await promise;
    return data;
  } catch (error) {
    throw ApiError.fromAxiosError(error);
  }
}

// ─── Axios Client ──────────────────────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach auth token to every request
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Clear token on 401 and attempt refresh; re-throw as ApiError
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorResponse>) => {
    const originalRequest = error.config as (import("axios").InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = typeof window !== "undefined" ? localStorage.getItem("smartmeal_refresh_token") : null;
      if (refreshToken) {
        try {
          const { data } = await apiClient.post<{ access_token: string; expires_in?: number }>(
            "/api/v1/auth/refresh",
            { refresh_token: refreshToken }
          );
          localStorage.setItem(TOKEN_KEY, data.access_token);
          if (typeof window !== "undefined") {
            document.cookie = `access_token=${data.access_token}; path=/; max-age=${data.expires_in ?? 86400}; SameSite=Lax`;
          }
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
          return apiClient(originalRequest);
        } catch {
          // Refresh failed — clear tokens and redirect
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem("smartmeal_refresh_token");
          if (typeof window !== "undefined") {
            document.cookie = "access_token=; path=/; max-age=0";
            if (!window.location.pathname.includes("/login")) {
              window.location.href = "/login?reason=session_expired";
            }
          }
        }
      }
      if (typeof window !== "undefined" && !window.location.pathname.includes("/login")) {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = "/login?reason=session_expired";
      }
    }
    return Promise.reject(ApiError.fromAxiosError(error));
  }
);

// ─── Typed Request Helpers ─────────────────────────────────────────────────────

export const api = {
  async get<T>(url: string, config?: RequestConfig): Promise<T> {
    return handleRequest(apiClient.get<T>(url, config));
  },

  async post<T>(url: string, data?: unknown, config?: RequestConfig): Promise<T> {
    return handleRequest(apiClient.post<T>(url, data, config));
  },

  async put<T>(url: string, data?: unknown, config?: RequestConfig): Promise<T> {
    return handleRequest(apiClient.put<T>(url, data, config));
  },

  async patch<T>(url: string, data?: unknown, config?: RequestConfig): Promise<T> {
    return handleRequest(apiClient.patch<T>(url, data, config));
  },

  async delete<T>(url: string, config?: RequestConfig): Promise<T> {
    return handleRequest(apiClient.delete<T>(url, config));
  },

  async uploadFile<T>(url: string, formData: FormData, config?: RequestConfig): Promise<T> {
    return handleRequest(
      apiClient.post<T>(url, formData, {
        ...config,
        // Do NOT set Content-Type manually for multipart/form-data.
        // Axios must compute the boundary automatically from the FormData object.
        headers: { ...config?.headers },
      })
    );
  },
};

