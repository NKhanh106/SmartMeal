"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Loader2, TrendingDown, TrendingUp, Scale } from "lucide-react";
import { analyticsService } from "@/services/analytics.service";
import { progressLogService } from "@/services/progress-log.service";
import type { WeeklyDashboardResponse, ProgressLogResponse } from "@/lib/types/api";
import { cn } from "@/lib/utils";

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b"];

function ChartCard({
  title,
  children,
  loading,
}: {
  title: string;
  children: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="h-[300px]">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
          </div>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const [weekly, setWeekly] = useState<WeeklyDashboardResponse | null>(null);
  const [progressLogs, setProgressLogs] = useState<ProgressLogResponse[]>([]);

  const [loadingWeekly, setLoadingWeekly] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setError(null);

    // Weekly nutrition data
    setLoadingWeekly(true);
    try {
      const w = await analyticsService.getWeeklyDashboard();
      setWeekly(w);
    } catch (e) {
      console.error("Failed to fetch weekly dashboard:", e);
    } finally {
      setLoadingWeekly(false);
    }

    // Weight/progress logs
    setLoadingProgress(true);
    try {
      const logs = await progressLogService.getMyLogs({ limit: 30 });
      setProgressLogs(logs);
    } catch (e) {
      console.error("Failed to fetch progress logs:", e);
    } finally {
      setLoadingProgress(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Build weekly calorie chart data
  const weeklyChartData = weekly?.daily_items.map((item) => {
    const date = new Date(item.date);
    const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    return {
      date: label,
      calories: item.total_calories,
    };
  }) ?? [];

  // Build weight progress chart data (sorted oldest→newest)
  const weightChartData = [...progressLogs]
    .filter((log) => log.weight_kg != null)
    .sort((a, b) => new Date(a.log_date).getTime() - new Date(b.log_date).getTime())
    .map((log) => {
      const date = new Date(log.log_date);
      const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      return {
        date: label,
        weight: log.weight_kg,
      };
    });

  // Macro ratio from weekly totals
  const macroData = weekly
    ? [
        { name: "Protein", value: weekly.total_protein_g, color: "#3b82f6" },
        { name: "Carbs", value: weekly.total_carb_g, color: "#10b981" },
        { name: "Fat", value: weekly.total_fat_g, color: "#f59e0b" },
      ]
    : [];

  // Compute weekly summary stats
  const daysWithData = weekly?.daily_items.filter((d) => d.total_calories > 0) ?? [];
  const avgCalories = daysWithData.length > 0
    ? Math.round(daysWithData.reduce((s, d) => s + d.total_calories, 0) / daysWithData.length)
    : null;
  const avgProtein = daysWithData.length > 0
    ? Math.round(daysWithData.reduce((s, d) => s + d.total_protein_g, 0) / daysWithData.length)
    : null;
  const avgCarbs = daysWithData.length > 0
    ? Math.round(daysWithData.reduce((s, d) => s + d.total_carb_g, 0) / daysWithData.length)
    : null;
  const avgFat = daysWithData.length > 0
    ? Math.round(daysWithData.reduce((s, d) => s + d.total_fat_g, 0) / daysWithData.length)
    : null;

  // Weight change
  let weightChange: number | null = null;
  if (weightChartData.length >= 2) {
    const first = weightChartData[0].weight!;
    const last = weightChartData[weightChartData.length - 1].weight!;
    weightChange = Math.round((last - first) * 10) / 10;
  }

  const calorieTarget = weekly?.active_goal?.daily_calorie_target;
  const daysOnTarget = daysWithData.filter((d) => {
    if (!calorieTarget) return false;
    return d.total_calories > 0 && d.total_calories <= calorieTarget * 1.1;
  }).length;
  const goalAdherence = daysWithData.length > 0 && calorieTarget
    ? Math.round((daysOnTarget / daysWithData.length) * 100)
    : null;

  const hasWeeklyData = weeklyChartData.length > 0;
  const hasWeightData = weightChartData.length > 0;
  const isLoading = loadingWeekly || loadingProgress;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
        <h1 className="text-3xl font-bold">Nutrition Analytics</h1>
        <p className="text-muted-foreground">Track your nutrition trends over time.</p>
      </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm">{error}</p>
          <button className="ml-auto text-sm underline" onClick={fetchData}>
            Retry
          </button>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Weight Progress */}
        <ChartCard title="Weight Progress" loading={loadingProgress}>
          {!loadingProgress && !hasWeightData ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <Scale className="h-8 w-8 text-slate-300" />
              <p className="text-sm text-slate-400">
                Log your weight in Progress to see progress
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={weightChartData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" fontSize={12} />
                <YAxis
                  domain={["dataMin - 1", "dataMax + 1"]}
                  fontSize={12}
                  unit=" kg"
                />
                <Tooltip formatter={(value: number) => [`${value} kg`, "Weight"]} />
                <Line
                  type="monotone"
                  dataKey="weight"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Weekly Calories */}
        <ChartCard title="Weekly Calories" loading={loadingWeekly}>
          {!loadingWeekly && !hasWeeklyData ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <TrendingUp className="h-8 w-8 text-slate-300" />
              <p className="text-sm text-slate-400">
                Log meals to see your weekly calorie intake
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={weeklyChartData}>
                <defs>
                  <linearGradient id="colorCal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" fontSize={12} />
                <YAxis fontSize={12} />
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <Tooltip formatter={(value: number) => [`${value} kcal`, "Calories"]} />
                <Area
                  type="monotone"
                  dataKey="calories"
                  stroke="#10B981"
                  fillOpacity={1}
                  fill="url(#colorCal)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Macro Ratio Pie */}
      <Card>
        <CardHeader>
          <CardTitle>Weekly Macro Distribution</CardTitle>
        </CardHeader>
        <CardContent className="h-[300px]">
          {loadingWeekly ? (
            <div className="flex h-full items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
            </div>
          ) : !weekly || macroData.every((m) => m.value === 0) ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <p className="text-sm text-slate-400">No macro data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={macroData}
                  innerRadius={70}
                  outerRadius={110}
                  paddingAngle={8}
                  dataKey="value"
                  stroke="none"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {macroData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number) => [`${value}g`, "Grams"]} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Weekly Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Weekly Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-20 rounded-lg" />
              ))}
            </div>
          ) : !weekly && progressLogs.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <p className="text-sm text-slate-400">
                No analytics data available yet
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="text-xs text-blue-600 font-bold uppercase">Avg Calories</p>
                <p className="text-2xl font-bold">
                  {avgCalories != null ? avgCalories.toLocaleString() : "—"}
                </p>
              </div>
              <div className="p-4 bg-emerald-50 rounded-lg">
                <p className="text-xs text-emerald-600 font-bold uppercase">Avg Protein</p>
                <p className="text-2xl font-bold">
                  {avgProtein != null ? `${avgProtein}g` : "—"}
                </p>
              </div>
              <div className="p-4 bg-orange-50 rounded-lg">
                <div className="flex items-center gap-1">
                  <Scale className="h-3 w-3 text-orange-600" />
                  <p className="text-xs text-orange-600 font-bold uppercase">Weight Change</p>
                </div>
                <p className="text-2xl font-bold flex items-center gap-1">
                  {weightChange != null ? (
                    <>
                      {weightChange < 0 ? (
                        <TrendingDown className="h-5 w-5 text-red-500" />
                      ) : weightChange > 0 ? (
                        <TrendingUp className="h-5 w-5 text-blue-500" />
                      ) : null}
                      {Math.abs(weightChange)} kg
                    </>
                  ) : (
                    "—"
                  )}
                </p>
              </div>
              <div className="p-4 bg-purple-50 rounded-lg">
                <p className="text-xs text-purple-600 font-bold uppercase">Goal Adherence</p>
                <p className="text-2xl font-bold">
                  {goalAdherence != null ? `${goalAdherence}%` : "—"}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Note about data source */}
      {!loadingWeekly && !loadingProgress && (
        <p className="text-xs text-slate-400 text-center">
          {hasWeeklyData
            ? "Weekly calorie data is aggregated from your meal logs by the backend."
            : "No meal log data for the past 7 days."}
          {hasWeightData
            ? " Weight data is sourced from your progress logs."
            : ""}
          {!hasWeeklyData && !hasWeightData
            ? " Start logging meals and weight to see your analytics."
            : ""}
        </p>
      )}
    </div>
  );
}
