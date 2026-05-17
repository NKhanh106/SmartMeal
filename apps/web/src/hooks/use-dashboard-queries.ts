/**
 * Dashboard query hooks — centralized React Query wrappers for dashboard data.
 *
 * All queries share the same QueryClient configuration (staleTime, retry, etc.)
 * set in src/providers/query-provider.tsx.
 *
 * These hooks replace manual useEffect + useState patterns in dashboard/page.tsx.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { analyticsService } from "@/services/analytics.service";
import { nutritionGoalService } from "@/services/nutrition-goal.service";
import type { DailyDashboardResponse, WeeklyDashboardResponse, NutritionGoalResponse } from "@/lib/types/api";

// ─── Query Keys ─────────────────────────────────────────────────────────────────

export const DASHBOARD_QUERY_KEYS = {
  daily: (date: string) => ["dashboard", "daily", date] as const,
  weekly: (endDate: string) => ["dashboard", "weekly", endDate] as const,
  activeGoal: () => ["nutrition-goal", "active"] as const,
} as const;

// ─── Daily Dashboard ─────────────────────────────────────────────────────────────

/**
 * Fetch daily nutrition dashboard for a given date.
 * Stale after 2 minutes — dashboard data changes frequently.
 */
export function useDailyDashboard(targetDate?: string) {
  return useQuery<DailyDashboardResponse>({
    queryKey: DASHBOARD_QUERY_KEYS.daily(targetDate ?? "today"),
    queryFn: () => analyticsService.getDailyDashboard(targetDate),
    staleTime: 1000 * 60 * 2, // 2 minutes
  });
}

// ─── Weekly Dashboard ─────────────────────────────────────────────────────────────

/**
 * Fetch weekly nutrition dashboard (7-day summary).
 * Stale after 10 minutes — weekly data changes less frequently.
 */
export function useWeeklyDashboard(endDate?: string) {
  return useQuery<WeeklyDashboardResponse>({
    queryKey: DASHBOARD_QUERY_KEYS.weekly(endDate ?? "today"),
    queryFn: () => analyticsService.getWeeklyDashboard(endDate),
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
}

// ─── Active Nutrition Goal ─────────────────────────────────────────────────────────

/**
 * Fetch the user's currently active nutrition goal.
 * Stale after 30 minutes — goals change infrequently.
 */
export function useActiveGoal() {
  return useQuery<NutritionGoalResponse>({
    queryKey: DASHBOARD_QUERY_KEYS.activeGoal(),
    queryFn: () => nutritionGoalService.getActiveGoal(),
    staleTime: 1000 * 60 * 30, // 30 minutes
    retry: false, // No active goal is OK — don't retry
  });
}

// ─── Parallel dashboard loader ────────────────────────────────────────────────────

/**
 * Fetch daily + weekly + goal in parallel.
 * Uses Promise.allSettled so one failure doesn't block the others.
 * Returns separate loading/error states for each.
 */
export function useDashboardData() {
  const daily = useDailyDashboard();
  const weekly = useWeeklyDashboard();
  const goal = useActiveGoal();

  return {
    daily,
    weekly,
    goal,
    isLoading: daily.isLoading || weekly.isLoading || goal.isLoading,
  };
}
