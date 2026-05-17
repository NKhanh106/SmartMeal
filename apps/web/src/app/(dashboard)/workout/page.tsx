"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Loader2, Dumbbell, Target, Play, CheckCircle2, Clock } from "lucide-react";
import { workoutService } from "@/services/workout.service";
import { useAuth } from "@/contexts/auth-context";
import { useToast } from "@/hooks/use-toast";
import type {
  WorkoutPlanDetailResponse,
  WorkoutItemResponse,
} from "@/lib/types/api";
import { cn } from "@/lib/utils";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const DAY_NAMES: Record<number, string> = {
  1: "Monday",
  2: "Tuesday",
  3: "Wednesday",
  4: "Thursday",
  5: "Friday",
  6: "Saturday",
  7: "Sunday",
};

const DIFFICULTY_LABEL: Record<string, string> = {
  nguoi_moi: "Beginner",
  trung_binh: "Intermediate",
  nang_cao: "Advanced",
};

const DIFFICULTY_COLOR: Record<string, string> = {
  nguoi_moi: "bg-green-100 text-green-700",
  trung_binh: "bg-yellow-100 text-yellow-700",
  nang_cao: "bg-red-100 text-red-700",
};

interface DayGroup {
  dayOfWeek: number;
  dayName: string;
  items: WorkoutItemResponse[];
}

function groupItemsByDay(items: WorkoutItemResponse[]): DayGroup[] {
  const groups: Map<number, WorkoutItemResponse[]> = new Map();
  for (const item of items) {
    let day: number;
    if (item.day_of_week != null) {
      day = item.day_of_week;
    } else if (item.workout_date) {
      const jsDay = new Date(item.workout_date).getDay(); // 0=Sun, 6=Sat
      day = jsDay === 0 ? 7 : jsDay; // convert to 1=Mon … 7=Sun
    } else {
      day = 1;
    }
    if (!groups.has(day)) groups.set(day, []);
    groups.get(day)!.push(item);
  }
  return Array.from(groups.entries())
    .sort(([a], [b]) => a - b)
    .map(([day, dayItems]) => ({
      dayOfWeek: day,
      dayName: DAY_NAMES[day] ?? `Day ${day}`,
      items: dayItems.sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0)),
    }));
}

function WorkoutItemRow({ item }: { item: WorkoutItemResponse }) {
  const completed = item.is_completed;

  return (
    <div
      className={cn(
        "flex items-center justify-between p-4 transition-colors",
        completed
          ? "bg-emerald-50/50 opacity-70"
          : "hover:bg-accent/10"
      )}
    >
      <div className="flex items-center gap-4">
        <div
          className={cn(
            "h-10 w-10 rounded-xl flex items-center justify-center shrink-0",
            completed ? "bg-emerald-100" : "bg-accent/50"
          )}
        >
          {completed ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
          ) : (
            <Dumbbell className="h-5 w-5 text-primary" />
          )}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h4 className={cn("font-bold", completed && "line-through text-slate-400")}>
              {item.exercise_name}
            </h4>
            {item.muscle_group && (
              <Badge variant="secondary" className="text-xs">
                {item.muscle_group}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3 mt-1">
            {item.sets != null && item.reps != null && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground font-medium">
                <Target className="h-3 w-3" />
                {item.sets} × {item.reps}
              </span>
            )}
            {item.duration_minutes != null && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground font-medium">
                <Clock className="h-3 w-3" />
                {item.duration_minutes} min
              </span>
            )}
            {item.weight_kg != null && (
              <span className="text-xs text-muted-foreground font-medium">
                {item.weight_kg} kg
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function WorkoutPage() {
  return (
    <ErrorBoundary>
      <WorkoutPageInner />
    </ErrorBoundary>
  );
}

function WorkoutPageInner() {
  const { user } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const [activePlan, setActivePlan] = useState<WorkoutPlanDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPlan = useCallback(async () => {
    if (!user?.id) return;
    setLoading(true);
    setError(null);
    try {
      const plan = await workoutService.getActivePlan(user.id);
      setActivePlan(plan);
    } catch (e) {
      // No active plan — not an error, just no plan yet
      setActivePlan(null);
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    if (user) {
      fetchPlan();
    }
  }, [user, fetchPlan]);

  const dayGroups = activePlan ? groupItemsByDay(activePlan.items) : [];

  const totalItems = activePlan?.items.length ?? 0;
  const completedItems = activePlan?.items.filter((i) => i.is_completed).length ?? 0;
  const progressPercent = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
        <h1 className="text-3xl font-bold">Workout Plan</h1>
        <p className="text-muted-foreground">Your personalized training routine.</p>
      </div>
        {activePlan && (
          <div className="flex items-center gap-2">
            <Badge className={DIFFICULTY_COLOR[activePlan.difficulty] ?? "bg-slate-100 text-slate-700"}>
              {DIFFICULTY_LABEL[activePlan.difficulty] ?? activePlan.difficulty}
            </Badge>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm flex-1">{error}</p>
          <Button size="sm" variant="ghost" onClick={fetchPlan}>Retry</Button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full rounded-2xl" />
          <Skeleton className="h-32 w-full rounded-2xl" />
        </div>
      )}

      {/* No plan yet */}
      {!loading && !activePlan && !error && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 py-16 text-center">
          <Dumbbell className="mb-3 h-10 w-10 text-slate-300" />
          <h3 className="font-semibold text-slate-600">No active workout plan</h3>
          <p className="mt-1 text-sm text-slate-400">
            Generate a personalized workout plan based on your nutrition goal
          </p>
          <div className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => router.push("/profile")}>
              Set Profile
            </Button>
            <Button
              onClick={async () => {
                try {
                  const plan = await workoutService.generatePlan();
                  setActivePlan(plan);
                } catch (e) {
                  const err = e as { response?: { status?: number }; message?: string };
                  if (err.response?.status === 404) {
                    toast({ title: "No nutrition goal found.", description: "Please set your goal in the Profile page first.", variant: "destructive" });
                  } else {
                    toast({ title: "Failed to generate plan.", description: err.message ?? "Please try again.", variant: "destructive" });
                  }
                }
              }}
            >
              Generate Plan
            </Button>
          </div>
        </div>
      )}

      {/* Workout plan content */}
      {!loading && activePlan && (
        <>
          {/* Plan meta */}
          {activePlan.start_date && (
            <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-100 bg-slate-50 px-6 py-3">
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <span className="font-semibold">From:</span>
                <span>{new Date(activePlan.start_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
              </div>
              {activePlan.end_date && (
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <span className="font-semibold">To:</span>
                  <span>{new Date(activePlan.end_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
                </div>
              )}
              {activePlan.goal_type && (
                <Badge variant="secondary" className="text-xs">
                  {activePlan.goal_type}
                </Badge>
              )}
              {activePlan.note && (
                <p className="text-sm text-slate-500 italic ml-auto">{activePlan.note}</p>
              )}
            </div>
          )}

          {/* Weekly progress */}
          <Card className="border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Play className="h-5 w-5" />
                Weekly Progress
              </CardTitle>
              <CardDescription>
                {completedItems} of {totalItems} exercises completed this week
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Progress value={progressPercent} className="h-2" />
                <div className="flex justify-between text-xs text-muted-foreground font-semibold">
                  <span>
                    {progressPercent}% complete
                  </span>
                  <span>
                    {totalItems - completedItems} remaining
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Workout days */}
          <div className="grid gap-6">
            {dayGroups.map((group) => (
              <Card key={group.dayOfWeek} className="overflow-hidden">
                <div className="bg-primary/5 px-6 py-4 border-b flex items-center justify-between">
                  <div>
                    <h3 className="text-xl font-bold text-primary">{group.dayName}</h3>
                    <p className="text-sm font-medium text-primary/70">
                      {group.items.length} exercise{group.items.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {group.items.filter((i) => i.is_completed).length}/{group.items.length} done
                    </span>
                  </div>
                </div>
                <CardContent className="p-0 divide-y">
                  {group.items.map((item) => (
                    <WorkoutItemRow key={item.id} item={item} />
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>

          {/* No exercises yet */}
          {activePlan && activePlan.items.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <Dumbbell className="mb-3 h-8 w-8 text-slate-300" />
                <p className="font-semibold text-slate-600">No exercises in this plan yet</p>
                <p className="mt-1 text-sm text-slate-400">
                  Contact your trainer or admin to add exercises to your plan
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
