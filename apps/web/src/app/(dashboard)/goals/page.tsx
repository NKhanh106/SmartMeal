"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { nutritionGoalService } from "@/services/nutrition-goal.service";
import { profileService } from "@/services/profile.service";
import type {
  NutritionGoalResponse,
  NutritionGoalCalculateResponse,
  NutritionGoalType,
} from "@/lib/types/api";
import {
  apiGoalToForm,
  formDataToGoalCreate,
  apiCalculationToForm,
  presetGoalTypeToApi,
  type GoalFormData,
} from "@/lib/profile-utils";
import { Flame, Droplet, Utensils } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";

// Hydration goal is now persisted via the backend hydration_goal_ml field.

const GOAL_TYPE_OPTIONS: { value: NutritionGoalType; label: string }[] = [
  { value: "giam_can", label: "Weight Loss (Giảm cân)" },
  { value: "giu_can", label: "Maintenance (Giữ cân)" },
  { value: "tang_co", label: "Muscle Gain (Tăng cơ)" },
];

export default function GoalsPage() {
  return (
    <ErrorBoundary>
      <GoalsPageInner />
    </ErrorBoundary>
  );
}

function GoalsPageInner() {
  const { toast } = useToast();

  // ── State ──────────────────────────────────────────────────────────────────
  const [existingGoal, setExistingGoal] = useState<NutritionGoalResponse | null>(null);
  const [formData, setFormData] = useState<GoalFormData>({
    calories: 2000,
    protein: 150,
    carbs: 200,
    fat: 70,
    water: 2.5,
    goalType: "giu_can",
  });

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<NutritionGoalCalculateResponse | null>(null);
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);

  // ── Fetch active goal ──────────────────────────────────────────────────────
  const fetchActiveGoal = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const goal = await nutritionGoalService.getActiveGoal();
      setExistingGoal(goal);
      setFormData(apiGoalToForm(goal));
    } catch (err) {
      const axiosErr = err as { statusCode?: number; response?: { status?: number }; message?: string };
      const statusCode = axiosErr.statusCode ?? axiosErr.response?.status ?? 0;
      if (statusCode === 404) {
        setExistingGoal(null);
      } else {
        setFetchError(axiosErr.message ?? "Failed to load nutrition goals.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Check if profile exists ────────────────────────────────────────────────
  const checkProfile = useCallback(async () => {
    try {
      await profileService.getMyProfile();
      setHasProfile(true);
    } catch (err) {
      const axiosErr = err as { statusCode?: number; response?: { status?: number }; message?: string };
      const statusCode = axiosErr.statusCode ?? axiosErr.response?.status ?? 0;
      if (statusCode === 404) {
        setHasProfile(false);
      } else {
        setHasProfile(false);
      }
    }
  }, []);

  useEffect(() => {
    Promise.all([fetchActiveGoal(), checkProfile()]);
  }, [fetchActiveGoal, checkProfile]);

  // ── Calculate preview (POST /calculate) ──────────────────────────────────
  const handleCalculate = async () => {
    setCalculating(true);
    setFetchError(null);
    try {
      const result = await nutritionGoalService.calculateTargets({
        goal_type: formData.goalType,
        target_weight_kg: undefined,
      });
      setPreviewData(result);
      setFormData((prev) => apiCalculationToForm(result, prev.goalType, prev.water));
      toast({ title: "Preview calculated successfully." });
    } catch (err) {
      const axiosErr = err as { statusCode?: number; response?: { status?: number }; message?: string };
      const statusCode = axiosErr.statusCode ?? axiosErr.response?.status ?? 0;
      if (statusCode === 404) {
        toast({
          title: "Profile required.",
          description: "Please complete your health profile before calculating goals.",
          variant: "destructive",
        });
      } else {
        toast({
          title: "Calculation failed.",
          description: axiosErr.message ?? "Please try again.",
          variant: "destructive",
        });
      }
    } finally {
      setCalculating(false);
    }
  };

  // ── Save goal (PUT if existing active goal, POST to create if new) ────────────────
  const handleSave = async () => {
    setSubmitting(true);
    setFetchError(null);
    try {
      if (existingGoal) {
        // Partial update preserves existing goal and updates in place
        const updated = await nutritionGoalService.updateGoal(existingGoal.id, {
          hydration_goal_ml: Math.round(formData.water * 1000),
        });
        setExistingGoal(updated);
        setFormData(apiGoalToForm(updated));
        toast({ title: "Nutrition goals updated successfully." });
      } else {
        // Create new goal (deactivates any prior active goal)
        const created = await nutritionGoalService.createGoal(
          formDataToGoalCreate(formData)
        );
        setExistingGoal(created);
        setFormData(apiGoalToForm(created));
        setPreviewData(null);
        toast({ title: "Nutrition goals saved successfully." });
      }
    } catch (err) {
      toast({
        title: "Failed to save goals.",
        description: (err as { message?: string }).message ?? "Please try again.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // ── Preset button (Weight Loss / Maintenance / Muscle Gain) ───────────────
  const handlePreset = async (preset: string) => {
    const goalType = presetGoalTypeToApi(preset);
    setFormData((prev) => ({ ...prev, goalType }));
    setCalculating(true);
    setFetchError(null);
    try {
      const result = await nutritionGoalService.calculateTargets({ goal_type: goalType });
      setPreviewData(result);
      setFormData((prev) => apiCalculationToForm(result, goalType, prev.water));
    } catch (err) {
      const axiosErr = err as { statusCode?: number; response?: { status?: number }; message?: string };
      const statusCode = axiosErr.statusCode ?? axiosErr.response?.status ?? 0;
      if (statusCode === 404) {
        toast({
          title: "Profile required.",
          description: "Please complete your health profile before using presets.",
          variant: "destructive",
        });
      } else {
        toast({
          title: "Calculation failed.",
          description: axiosErr.message ?? "Please try again.",
          variant: "destructive",
        });
      }
    } finally {
      setCalculating(false);
    }
  };

  // ── Form change handlers ───────────────────────────────────────────────────
  const handleChange = (field: keyof GoalFormData, value: string | number) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setPreviewData(null);
  };

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-9 w-32" />
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          {[...Array(2)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6 space-y-4">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-10 w-full" />
              </CardContent>
            </Card>
          ))}
          <Card className="md:col-span-2">
            <CardContent className="p-6 space-y-4">
              <Skeleton className="h-6 w-40" />
              <div className="grid grid-cols-3 gap-4">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // ── No profile → prompt to create profile ─────────────────────────────────
  if (hasProfile === false) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Nutrition Goals</h1>
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="p-6 text-center space-y-3">
            <p className="text-orange-700 font-medium">
              Health profile required.
            </p>
            <p className="text-sm text-orange-600">
              Please complete your{" "}
              <a href="/profile" className="underline font-medium">
                Health Profile
              </a>{" "}
              first so we can calculate your nutritional needs.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Fetch error ────────────────────────────────────────────────────────────
  if (fetchError && !existingGoal) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Nutrition Goals</h1>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6 text-center space-y-3">
            <p className="text-red-600 font-medium">Failed to load nutrition goals.</p>
            <p className="text-sm text-red-500">{fetchError}</p>
            <Button onClick={fetchActiveGoal} variant="outline" size="sm">
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  const proteinKcal = formData.protein * 4;
  const carbsKcal = formData.carbs * 4;
  const fatKcal = formData.fat * 9;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Nutrition Goals</h1>
          <p className="text-muted-foreground">Set your daily caloric and macronutrient targets.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleCalculate}
          disabled={calculating}
        >
          {calculating ? "Calculating..." : "Calculate Preview"}
        </Button>
      </div>

      {/* BMR / TDEE info banner (from preview or existing goal) */}
      {(previewData || existingGoal) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <InfoCard label="BMI" value={previewData ? previewData.bmi.toFixed(1) : (existingGoal?.bmi?.toFixed(1) ?? "—")} />
          <InfoCard label="BMR (kcal)" value={String(previewData?.bmr_kcal ?? existingGoal?.bmr_kcal ?? "—")} />
          <InfoCard label="TDEE (kcal)" value={String(previewData?.tdee_kcal ?? existingGoal?.tdee_kcal ?? "—")} />
          <InfoCard label="Daily Target (kcal)" value={String(previewData?.daily_calorie_target ?? existingGoal?.daily_calorie_target ?? "—")} highlight />
        </div>
      )}

      {/* No active goal yet — show info banner */}
      {!existingGoal && !previewData && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="p-4 text-sm text-blue-700 flex items-start gap-3">
            <svg className="h-5 w-5 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
            </svg>
            <span>
              You haven&apos;t set a nutrition goal yet. Fill in the form below and click <strong>&quot;Save Goals&quot;</strong> to get started, or use <strong>&quot;Calculate Preview&quot;</strong> to estimate targets based on your health profile.
            </span>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Daily Caloric Target */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Flame className="h-5 w-5 text-orange-500" />
              Daily Caloric Target
            </CardTitle>
            <CardDescription>
              Adjust your daily energy intake based on your goals.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="calories">Energy (kcal)</Label>
              <Input
                id="calories"
                type="number"
                min={500}
                max={10000}
                value={formData.calories}
                onChange={(e) => handleChange("calories", Number(e.target.value))}
              />
            </div>

            <div className="space-y-2">
              <Label>Goal Type</Label>
              <select
                className="w-full p-2 rounded-md border bg-background"
                value={formData.goalType}
                onChange={(e) => handleChange("goalType", e.target.value as NutritionGoalType)}
              >
                {GOAL_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex gap-2 flex-wrap">
              <Button
                size="sm"
                variant="ghost"
                className="text-xs border text-muted-foreground uppercase tracking-widest font-semibold"
                onClick={() => handlePreset("Weight Loss")}
                disabled={calculating}
              >
                Weight Loss
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-xs border text-muted-foreground uppercase tracking-widest font-semibold"
                onClick={() => handlePreset("Maintenance")}
                disabled={calculating}
              >
                Maintenance
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-xs border text-muted-foreground uppercase tracking-widest font-semibold"
                onClick={() => handlePreset("Muscle Gain")}
                disabled={calculating}
              >
                Muscle Gain
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Hydration Goal */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Droplet className="h-5 w-5 text-blue-500" />
              Hydration Goal
            </CardTitle>
            <CardDescription>
              Minimum daily water intake target.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="water">Water (Liters)</Label>
              <Input
                id="water"
                type="number"
                step="0.1"
                min={0}
                max={10}
                value={formData.water}
                onChange={(e) => handleChange("water", Number(e.target.value))}
              />
            </div>
          </CardContent>
        </Card>

        {/* Macronutrient Targets */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Utensils className="h-5 w-5 text-primary" />
              Macronutrient Targets
            </CardTitle>
            <CardDescription>
              Customize the ratio of Protein, Carbs, and Fats.
              {previewData && (
                <span className="block mt-1 text-green-600 font-medium">
                  Preview calculated from your profile.
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="protein">Protein (g)</Label>
                <Input
                  id="protein"
                  type="number"
                  min={0}
                  max={1000}
                  value={formData.protein}
                  onChange={(e) => handleChange("protein", Number(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  About {proteinKcal} kcal
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="carbs">Carbohydrates (g)</Label>
                <Input
                  id="carbs"
                  type="number"
                  min={0}
                  max={2000}
                  value={formData.carbs}
                  onChange={(e) => handleChange("carbs", Number(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  About {carbsKcal} kcal
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="fat">Fats (g)</Label>
                <Input
                  id="fat"
                  type="number"
                  min={0}
                  max={1000}
                  value={formData.fat}
                  onChange={(e) => handleChange("fat", Number(e.target.value))}
                />
                <p className="text-xs text-muted-foreground">
                  About {fatKcal} kcal
                </p>
              </div>
            </div>
            <div className="mt-8">
              <Button
                className="w-full"
                onClick={handleSave}
                disabled={submitting}
              >
                {submitting ? "Saving..." : existingGoal ? "Update Goals" : "Save Goals"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function InfoCard({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <Card className={highlight ? "border-primary/40 bg-primary/5" : undefined}>
      <CardContent className="p-4 text-center">
        <p className="text-xs text-muted-foreground mb-1">{label}</p>
        <p className={`text-lg font-bold ${highlight ? "text-primary" : "text-foreground"}`}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
