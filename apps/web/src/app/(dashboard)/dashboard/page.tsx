"use client";

import { useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Loader2, Plus, Flame, Target, Utensils, Clock } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { useAuth } from "@/contexts/auth-context";
import { useDashboardData } from "@/hooks/use-dashboard-queries";
import { cn } from "@/lib/utils";

function MealTypeLabel({ mealType }: { mealType: string }) {
  const labels: Record<string, string> = {
    bua_sang: "Breakfast",
    bua_trua: "Lunch",
    bua_toi: "Dinner",
    an_vat: "Snack",
    khac: "Other",
  };
  return <span>{labels[mealType] ?? mealType}</span>;
}

function StatCard({
  title,
  value,
  unit,
  target,
  targetUnit,
  icon: Icon,
  colorClass,
  trend,
  trendPositive,
}: {
  title: string;
  value: number;
  unit: string;
  target?: number;
  targetUnit?: string;
  icon: React.ElementType;
  colorClass: string;
  trend: string;
  trendPositive?: boolean;
}) {
  const progress = target && target > 0 ? Math.min(Math.round((value / target) * 100), 100) : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <Card className="border-slate-200/60 shadow-sm hover:shadow-md transition-shadow rounded-2xl overflow-hidden">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 rounded-xl bg-slate-50">
              <Icon className={cn("h-5 w-5", colorClass)} />
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              {title}
            </span>
          </div>
          <div className="space-y-1">
            <div className="flex items-baseline gap-1">
              <h3 className="text-2xl font-bold text-slate-900">
                {value.toLocaleString()}
              </h3>
              <p className="text-sm text-slate-400 font-medium">{unit}</p>
            </div>
            {target && targetUnit && (
              <p className="text-sm text-slate-400 font-medium">
                / {target.toLocaleString()} {targetUnit}
              </p>
            )}
            <p
              className={cn(
                "text-xs font-semibold",
                trendPositive === false ? "text-amber-500" : "text-emerald-500"
              )}
            >
              {trend}
            </p>
          </div>
          {progress !== null && (
            <Progress value={progress} className="mt-4 h-1.5 bg-slate-100" />
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function MacroCard({
  title,
  consumed,
  target,
  unit,
  icon: Icon,
  colorClass,
}: {
  title: string;
  consumed: number;
  target?: number;
  unit: string;
  icon: React.ElementType;
  colorClass: string;
}) {
  const progress = target && target > 0 ? Math.min(Math.round((consumed / target) * 100), 100) : null;
  const remaining = target ? target - consumed : null;

  let trend = "";
  let trendPositive: boolean | undefined = undefined;
  if (remaining !== null && target) {
    if (remaining < 0) {
      trend = `${Math.abs(remaining).toFixed(0)}g over`;
      trendPositive = false;
    } else if (remaining < target * 0.1) {
      trend = "Near limit";
      trendPositive = false;
    } else {
      trend = `${remaining.toFixed(0)}g left`;
      trendPositive = true;
    }
  }

  return (
    <StatCard
      title={title}
      value={Math.round(consumed)}
      unit={unit}
      target={target}
      targetUnit={unit}
      icon={Icon}
      colorClass={colorClass}
      trend={trend}
      trendPositive={trendPositive}
    />
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  // React Query — all three fetch in parallel, each with independent loading/error state
  const { daily, weekly, goal } = useDashboardData();

  const isLoading = daily.isLoading || weekly.isLoading || goal.isLoading;
  const error = daily.error || weekly.error ? "Failed to load some dashboard data." : null;

  // Build chart data from weekly — memoized to avoid recalculating on every render
  const chartData = useMemo(
    () =>
      weekly.data?.daily_items.map((item) => {
        const date = new Date(item.date);
        const dayName = date.toLocaleDateString("en-US", { weekday: "short" });
        return {
          day: dayName,
          calories: item.total_calories,
        };
      }) ?? [],
    [weekly.data],
  );

  // Macro pie data — memoized, only recalculates when daily data changes
  const macroPieData = useMemo(
    () =>
      daily.data
        ? [
            { name: "Protein", value: daily.data.total_protein_g, color: "#3b82f6" },
            { name: "Carbs", value: daily.data.total_carb_g, color: "#10b981" },
            { name: "Fat", value: daily.data.total_fat_g, color: "#f59e0b" },
          ]
        : [],
    [daily.data],
  );

  // Targets from active goal or daily response — memoized
  const { calorieTarget, proteinTarget, carbTarget, fatTarget } = useMemo(
    () => ({
      calorieTarget: goal.data?.daily_calorie_target ?? daily.data?.active_goal?.daily_calorie_target,
      proteinTarget: goal.data?.protein_target_g ?? daily.data?.active_goal?.protein_target_g,
      carbTarget: goal.data?.carb_target_g ?? daily.data?.active_goal?.carb_target_g,
      fatTarget: goal.data?.fat_target_g ?? daily.data?.active_goal?.fat_target_g,
    }),
    [goal.data, daily.data],
  );

  const calorieProgress = daily.data?.calories_progress;
  const greetingName = user?.full_name ?? "User";

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Today&apos;s Overview</h1>
          {daily.isLoading ? (
            <Skeleton className="mt-1 h-4 w-64" />
          ) : calorieProgress ? (
            <p className="text-muted-foreground">
              {calorieProgress.remaining !== undefined && calorieProgress.remaining > 0
                ? `${calorieProgress.remaining.toLocaleString()} kcal remaining today`
                : calorieProgress.remaining !== undefined && calorieProgress.remaining < 0
                ? `${Math.abs(calorieProgress.remaining).toLocaleString()} kcal over target`
                : "You&apos;re on track!"}
            </p>
          ) : (
            <p className="text-muted-foreground">
              No data for today yet
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" className="gap-2" onClick={() => router.push("/upload")}>
            <Plus className="h-4 w-4" />
            Add Meal
          </Button>
          <Button size="sm" variant="outline" className="gap-2" onClick={() => router.push("/history")}>
            <Clock className="h-4 w-4" />
            History
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm">{error}</p>
          <Button size="sm" variant="ghost" className="ml-auto" onClick={() => queryClient.invalidateQueries({ queryKey: ["dashboard"] })}>
            Retry
          </Button>
        </div>
      )}

      {/* Stat cards */}
      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Card key={i} className="rounded-2xl overflow-hidden">
              <CardContent className="p-6 space-y-4">
                <div className="flex justify-between">
                  <Skeleton className="h-10 w-10 rounded-xl" />
                  <Skeleton className="h-4 w-16" />
                </div>
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-1.5 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : !daily.data ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 py-16 text-center">
          <Utensils className="mb-3 h-10 w-10 text-slate-300" />
          <h3 className="font-semibold text-slate-600">No meal data for today</h3>
          <p className="mt-1 text-sm text-slate-400">
            Start logging meals to see your nutrition summary
          </p>
          <Button className="mt-4 gap-2" onClick={() => router.push("/upload")}>
            <Plus className="h-4 w-4" />
            Log your first meal
          </Button>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Calories"
            value={Math.round(daily.data.total_calories)}
            unit="kcal"
            target={calorieTarget}
            targetUnit="kcal"
            icon={Flame}
            colorClass="text-orange-500"
            trend={
              calorieProgress
                ? calorieProgress.remaining !== undefined
                  ? calorieProgress.remaining > 0
                    ? `${calorieProgress.remaining.toLocaleString()} kcal left`
                    : `${Math.abs(calorieProgress.remaining).toLocaleString()} kcal over`
                  : `${calorieProgress.percent ?? 0}% of goal`
                : `${daily.data.meal_count} meals logged`
            }
            trendPositive={
              calorieProgress?.remaining !== undefined
                ? calorieProgress.remaining > 0
                : undefined
            }
          />
          <MacroCard
            title="Protein"
            consumed={daily.data.total_protein_g}
            target={proteinTarget}
            unit="g"
            icon={Target}
            colorClass="text-blue-500"
          />
          <MacroCard
            title="Carbs"
            consumed={daily.data.total_carb_g}
            target={carbTarget}
            unit="g"
            icon={Utensils}
            colorClass="text-emerald-500"
          />
          <MacroCard
            title="Fat"
            consumed={daily.data.total_fat_g}
            target={fatTarget}
            unit="g"
            icon={Utensils}
            colorClass="text-amber-500"
          />
        </div>
      )}

      {/* Charts */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-7">
        {/* Weekly calorie bar chart */}
        <Card className="lg:col-span-4 border-slate-200/60 shadow-sm rounded-2xl">
          <CardContent className="p-8">
            <div className="flex items-center justify-between mb-8">
              <h3 className="text-lg font-bold text-slate-900">Weekly Calorie Intake</h3>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                Last 7 Days
              </span>
            </div>
            {weekly.isLoading ? (
              <div className="h-[300px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-[300px] flex items-center justify-center">
                <p className="text-sm text-slate-400">No weekly data available</p>
              </div>
            ) : (
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                    <XAxis
                      dataKey="day"
                      axisLine={false}
                      tickLine={false}
                      fontSize={12}
                      tick={{ fill: "#94A3B8", fontWeight: 600 }}
                      dy={10}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      fontSize={12}
                      tick={{ fill: "#94A3B8", fontWeight: 600 }}
                    />
                    <Tooltip
                      cursor={{ fill: "#F8FAFC", radius: 8 }}
                      contentStyle={{
                        borderRadius: "12px",
                        border: "none",
                        boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1)",
                      }}
                      formatter={(value: number) => [`${value} kcal`, "Calories"]}
                    />
                    <Bar
                      dataKey="calories"
                      fill="#10B981"
                      radius={[6, 6, 0, 0]}
                      barSize={36}
                      opacity={0.9}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Macro pie chart */}
        <Card className="lg:col-span-3 border-slate-200/60 shadow-sm rounded-2xl">
          <CardContent className="p-8">
            <h3 className="text-lg font-bold text-slate-900 mb-8">Macro Distribution</h3>
            {daily.isLoading ? (
              <div className="h-[260px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-slate-300" />
              </div>
            ) : !daily.data || (macroPieData.every((m) => m.value === 0)) ? (
              <div className="h-[260px] flex items-center justify-center">
                <p className="text-sm text-slate-400">No macro data</p>
              </div>
            ) : (
              <>
                <div className="h-[260px] w-full relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={macroPieData}
                        innerRadius={70}
                        outerRadius={90}
                        paddingAngle={8}
                        dataKey="value"
                        stroke="none"
                      >
                        {macroPieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value: number) => [`${value}g`, "Grams"]} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-[10px] uppercase font-bold tracking-widest text-slate-400">
                      Total
                    </span>
                    <span className="text-3xl font-extrabold text-slate-900">
                      {Math.round(daily.data.total_calories).toLocaleString()}
                    </span>
                    <span className="text-[10px] font-bold text-emerald-500">kcal</span>
                  </div>
                </div>
                <div className="mt-8 space-y-3">
                  {macroPieData.map((macro) => (
                    <div
                      key={macro.name}
                      className="flex items-center justify-between p-3 rounded-xl bg-slate-50/50"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: macro.color }}
                        />
                        <span className="text-sm font-bold text-slate-600">{macro.name}</span>
                      </div>
                      <span className="text-sm font-extrabold text-slate-900">
                        {Math.round(macro.value)}g
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Today's meals list */}
      {daily.data && daily.data.meals && daily.data.meals.length > 0 && (
        <Card className="border-slate-200/60 shadow-sm rounded-2xl">
          <CardContent className="p-8">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-bold text-slate-900">Today&apos;s Meals</h3>
              {/* Auto-detected meals notice */}
              {daily.data.auto_detected_count !== undefined && daily.data.auto_detected_count > 0 && (
                <span className="text-xs px-2 py-1 bg-amber-50 text-amber-700 rounded-full">
                  {daily.data.auto_detected_count} meal(s) auto-detected from chat
                </span>
              )}
            </div>
            <div className="space-y-4">
              {daily.data.meals.map((meal) => {
                const isFromChat = meal.source === "chat_extraction" || meal.source === "chat_command";
                return (
                  <div
                    key={meal.id}
                    className="flex items-center justify-between rounded-xl border border-slate-100 p-4 hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50">
                        <Utensils className="h-4 w-4 text-emerald-600" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-slate-900">
                            <MealTypeLabel mealType={meal.meal_type} />
                          </p>
                          {isFromChat && (
                            <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded font-medium">
                              AI Chat
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400">
                          {new Date(meal.meal_time).toLocaleTimeString("en-US", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-right">
                      <div>
                        <p className="text-sm font-bold text-slate-900">
                          {Math.round(meal.total_calories)} kcal
                        </p>
                        <p className="text-xs text-slate-400">
                          P: {Math.round(meal.total_protein_g)}g · C: {Math.round(meal.total_carb_g)}g · F: {Math.round(meal.total_fat_g)}g
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DashboardPageWrapper() {
  return (
    <ErrorBoundary>
      <DashboardPage />
    </ErrorBoundary>
  );
}

export default DashboardPageWrapper;
