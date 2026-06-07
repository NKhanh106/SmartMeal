"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter, usePathname } from "next/navigation";

import { authService } from "@/services/auth.service";
import type { UserResponse } from "@/lib/types/api";
import { ApiError, setAccessToken, clearAccessToken } from "@/lib/api-client";

// ─── Types ───────────────────────────────────────────────────────────────────

interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  updateUser: (data: { full_name?: string }) => Promise<void>;
}

interface AuthProviderProps {
  children: React.ReactNode;
}

// ─── Context ────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}

// ─── AuthProvider ────────────────────────────────────────────────────────────

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = user !== null;

  // Refresh user info from /auth/me
  const refreshUser = useCallback(async () => {
    try {
      const me = await authService.getCurrentUser();
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  // On mount: check if access token cookie exists and sync to memory
  useEffect(() => {
    // Read from cookie (set by the API response interceptor after refresh)
    const cookieToken = document.cookie
      .split("; ")
      .find((row) => row.startsWith("access_token="))
      ?.split("=")[1];
    if (!cookieToken) {
      setIsLoading(false);
      return;
    }
    setAccessToken(decodeURIComponent(cookieToken));
    refreshUser()
      .catch(() => {
        clearAccessToken();
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, [refreshUser]);

  // Redirect unauthenticated users away from protected routes
  useEffect(() => {
    if (isLoading) return;

    const publicPaths = ["/login", "/register", "/"];
    const isPublic = publicPaths.some(
      (p) => pathname === p || pathname.startsWith(p + "/")
    );

    if (!isPublic && !isAuthenticated) {
      router.replace("/login");
      return;
    }

    // Redirect authenticated users away from auth pages
    const authOnlyPages = ["/login", "/register"];
    const isAuthPage = authOnlyPages.some((p) => pathname === p);
    if (isAuthPage && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  // Login
  const login = useCallback(
    async (email: string, password: string) => {
      const result = await authService.login(email, password);
      // Access token: memory (api-client) + cookie (middleware)
      setAccessToken(result.access_token);
      if (typeof document !== "undefined") {
        document.cookie = `access_token=${result.access_token}; path=/; max-age=${result.expires_in}; SameSite=Lax`;
      }
      await refreshUser();
      router.replace("/dashboard");
    },
    [refreshUser, router]
  );

  // Register
  const register = useCallback(
    async (email: string, password: string, fullName?: string) => {
      await authService.register({ email, password, full_name: fullName });
      // Auto-login after registration
      await login(email, password);
    },
    [login]
  );

  // Logout
  const logout = useCallback(() => {
    clearAccessToken();
    if (typeof document !== "undefined") {
      document.cookie = "access_token=; path=/; max-age=0";
      document.cookie = "smartmeal_refresh_token=; path=/api/auth/refresh; max-age=0";
    }
    authService.logout().catch(() => {
      // Logout endpoint failure is non-fatal — clear local state anyway
    });
    setUser(null);
    router.replace("/login");
  }, [router]);

  // Update user (e.g. full_name)
  const updateUser = useCallback(
    async (data: { full_name?: string }) => {
      const updated = await authService.updateUser(data);
      setUser(updated);
    },
    []
  );

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated,
      login,
      logout,
      refreshUser,
      register,
      updateUser,
    }),
    [user, isLoading, isAuthenticated, login, logout, refreshUser, register, updateUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
