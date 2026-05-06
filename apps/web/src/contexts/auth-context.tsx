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
import { TOKEN_KEY, ApiError } from "@/lib/api-client";

// ─── Types ───────────────────────────────────────────────────────────────────

interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
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

  // On mount: check if token exists and fetch user
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setIsLoading(false);
      return;
    }
    refreshUser()
      .catch(() => {
        // Token exists but /me fails → clear invalid token
        authService.logout();
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
      authService.setTokens(result.access_token, result.refresh_token);
      // Set cookie for middleware auth check
      if (typeof window !== "undefined") {
        document.cookie = `access_token=${result.access_token}; path=/; max-age=${result.expires_in ?? 86400}; SameSite=Lax`;
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
    authService.logout();
    if (typeof window !== "undefined") {
      document.cookie = "access_token=; path=/; max-age=0";
    }
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated,
      login,
      logout,
      refreshUser,
      register,
    }),
    [user, isLoading, isAuthenticated, login, logout, refreshUser, register]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
