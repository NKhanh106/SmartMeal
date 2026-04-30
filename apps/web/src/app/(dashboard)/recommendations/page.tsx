"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Loader2, RefreshCw, Lightbulb, Utensils, Target, Sparkles } from "lucide-react";
import { recommendationService } from "@/services/recommendation.service";
import { nutritionGoalService } from "@/services/nutrition-goal.service";
import { profileService } from "@/services/profile.service";
import type { DailyRecommendationResponse } from "@/lib/types/api";
import { cn } from "@/lib/utils";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatDate(date: Date) {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function getTomorrowDate() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().split("T")[0];
}

function getTodayDate() {
  return new Date().toISOString().split("T")[0];
}

/** Parse meal suggestion text into breakfast/lunch/dinner sections */
function parseMealSuggestion(text: string | null | undefined): {
  breakfast: string | null;
  lunch: string | null;
  dinner: string | null;
  snacks: string[];
} {
  if (!text) return { breakfast: null, lunch: null, dinner: null, snacks: [] };

  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const snacks: string[] = [];

  // Simple keyword-based sectioning
  const breakfastKw = ["breakfast", "bữa sáng", "sáng", "bua_sang", "morning"];
  const lunchKw = ["lunch", "bữa trưa", "trưa", "bua_trua", "midday", "afternoon"];
  const dinnerKw = ["dinner", "bữa tối", "tối", "bua_toi", "evening"];
  const snackKw = ["snack", "ăn vặt", "an_vat", "phụ", "dessert"];

  let breakfast: string[] = [];
  let lunch: string[] = [];
  let dinner: string[] = [];

  let currentSection: "breakfast" | "lunch" | "dinner" | "snack" | "other" = "other";

  for (const line of lines) {
    const lower = line.toLowerCase();
    if (breakfastKw.some((k) => lower.includes(k))) {
      currentSection = "breakfast";
      continue;
    }
    if (lunchKw.some((k) => lower.includes(k))) {
      currentSection = "lunch";
      continue;
    }
    if (dinnerKw.some((k) => lower.includes(k))) {
      currentSection = "dinner";
      continue;
    }
    if (snackKw.some((k) => lower.includes(k))) {
      currentSection = "snack";
      continue;
    }

    // Skip section headers / bullet markers
    if (/^[-*•]|^bữa\s|^meal\s|^[a-z]+\s*:$/i.test(line)) continue;

    if (currentSection === "breakfast") breakfast.push(line);
    else if (currentSection === "lunch") lunch.push(line);
    else if (currentSection === "dinner") dinner.push(line);
    else if (currentSection === "snack") snacks.push(line);
  }

  // If nothing was sectioned, fall back to splitting by line count
  if (!breakfast.length && !lunch.length && !dinner.length && lines.length > 0) {
    const third = Math.ceil(lines.length / 3);
    breakfast = lines.slice(0, third);
    lunch = lines.slice(third, third * 2);
    dinner = lines.slice(third * 2);
  }

  return {
    breakfast: breakfast.length ? breakfast.join(" ") : null,
    lunch: lunch.length ? lunch.join(" ") : null,
    dinner: dinner.length ? dinner.join(" ") : null,
    snacks,
  };
}

interface PrerequisiteError {
  type: "no_profile" | "no_goal" | "generate_failed";
  message: string;
}

export default function RecommendationsPage() {
  const router = useRouter();

  const [recommendation, setRecommendation] = useState<DailyRecommendationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prerequisiteError, setPrerequisiteError] = useState<PrerequisiteError | null>(null);

  const todayDate = getTodayDate();
  const tomorrowDate = getTomorrowDate();

  const checkPrerequisites = useCallback(async (): Promise<boolean> => {
    // 1. Check profile exists
    try {
      await profileService.getMyProfile();
    } catch {
      setPrerequisiteError({
        type: "no_profile",
        message: "You need to complete your health profile before getting personalized recommendations.",
      });
      return false;
    }

    // 2. Check active nutrition goal exists
    try {
      await nutritionGoalService.getActiveGoal();
    } catch {
      setPrerequisiteError({
        type: "no_goal",
        message: "Set a nutrition goal to receive personalized meal recommendations.",
      });
      return false;
    }

    setPrerequisiteError(null);
    return true;
  }, []);

  const loadRecommendation = useCallback(async () => {
    setLoading(true);
    setError(null);

    const ok = await checkPrerequisites();
    if (!ok) {
      setLoading(false);
      return;
    }

    // Try to fetch today's recommendation first
    try {
      const rec = await recommendationService.getRecommendationByDate(todayDate);
      setRecommendation(rec);
    } catch {
      // No recommendation for today yet — user needs to generate one
      setRecommendation(null);
    } finally {
      setLoading(false);
    }
  }, [checkPrerequisites, todayDate]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    setRecommendation(null);

    try {
      const ok = await checkPrerequisites();
      if (!ok) {
        setGenerating(false);
        return;
      }

      const response = await recommendationService.generateRecommendation(tomorrowDate);
      setRecommendation(response.recommendation);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to generate recommendation";
      setError(msg);
      setPrerequisiteError({
        type: "generate_failed",
        message: msg,
      });
    } finally {
      setGenerating(false);
    }
  }, [checkPrerequisites, tomorrowDate]);

  useEffect(() => {
    loadRecommendation();
  }, [loadRecommendation]);

  const parsed = recommendation ? parseMealSuggestion(recommendation.meal_suggestion) : null;

  const macroCards = recommendation ? [
    {
      label: "Calories",
      value: recommendation.calories_target ? `${Math.round(recommendation.calories_target)} kcal` : "—",
      color: "text-orange-500",
      bg: "bg-orange-50",
    },
    {
      label: "Protein",
      value: recommendation.protein_target_g ? `${Math.round(recommendation.protein_target_g)}g` : "—",
      color: "text-blue-500",
      bg: "bg-blue-50",
    },
    {
      label: "Carbs",
      value: recommendation.carb_target_g ? `${Math.round(recommendation.carb_target_g)}g` : "—",
      color: "text-emerald-500",
      bg: "bg-emerald-50",
    },
    {
      label: "Fat",
      value: recommendation.fat_target_g ? `${Math.round(recommendation.fat_target_g)}g` : "—",
      color: "text-amber-500",
      bg: "bg-amber-50",
    },
  ] : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
      <div>
        <h1 className="text-3xl font-bold">Daily Recommendations</h1>
        <p className="text-muted-foreground">AI-generated meal plans and health tips.</p>
      </div>
        <Button
          variant="outline"
          className="gap-2"
          disabled={generating || loading}
          onClick={handleGenerate}
        >
          {generating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {recommendation ? "Regenerate" : "Generate Plan"}
        </Button>
      </div>

      {/* Prerequisite errors */}
      {prerequisiteError && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 p-4">
            <AlertCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold text-amber-800">{prerequisiteError.type === "no_profile" ? "Profile Required" : prerequisiteError.type === "no_goal" ? "Goal Required" : "Generation Failed"}</p>
              <p className="mt-1 text-sm text-amber-700">{prerequisiteError.message}</p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="shrink-0 border-amber-300 text-amber-700 hover:bg-amber-100"
              onClick={() => {
                if (prerequisiteError.type === "no_profile") router.push("/profile");
                else router.push("/goals");
              }}
            >
              {prerequisiteError.type === "no_profile" ? "Set Profile" : "Set Goal"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* API error */}
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm flex-1">{error}</p>
          <Button size="sm" variant="ghost" onClick={handleGenerate}>Retry</Button>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-24 mb-2" />
                <Skeleton className="h-7 w-full" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* No recommendation yet */}
      {!loading && !recommendation && !prerequisiteError && !error && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 py-16 text-center">
          <Sparkles className="mb-3 h-10 w-10 text-slate-300" />
          <h3 className="font-semibold text-slate-600">No recommendation yet</h3>
          <p className="mt-1 text-sm text-slate-400">
            Click &quot;Generate Plan&quot; to get your personalized AI meal recommendation
          </p>
        </div>
      )}

      {/* Recommendation content */}
      {!loading && recommendation && (
        <>
          {/* Macro targets */}
          {macroCards.length > 0 && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {macroCards.map((card) => (
                <Card key={card.label} className={cn("border-0", card.bg)}>
                  <CardContent className="flex flex-col items-center p-4 text-center">
                    <p className={cn("text-xs font-bold uppercase tracking-wider", card.color)}>
                      {card.label}
                    </p>
                    <p className="mt-1 text-2xl font-extrabold">{card.value}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Meal suggestions */}
          {(parsed?.breakfast || parsed?.lunch || parsed?.dinner) ? (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {parsed?.breakfast && (
                <Card className="relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-4 opacity-10">
                    <Utensils className="h-12 w-12" />
                  </div>
                  <CardHeader>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-orange-500 text-lg">&#9746;</span>
                      <Badge variant="outline">Breakfast</Badge>
                    </div>
                    <CardTitle className="text-lg leading-relaxed">
                      {parsed.breakfast}
                    </CardTitle>
                  </CardHeader>
                </Card>
              )}
              {parsed?.lunch && (
                <Card className="relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-4 opacity-10">
                    <Utensils className="h-12 w-12" />
                  </div>
                  <CardHeader>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-yellow-500 text-lg">&#9728;</span>
                      <Badge variant="outline">Lunch</Badge>
                    </div>
                    <CardTitle className="text-lg leading-relaxed">
                      {parsed.lunch}
                    </CardTitle>
                  </CardHeader>
                </Card>
              )}
              {parsed?.dinner && (
                <Card className="relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-4 opacity-10">
                    <Utensils className="h-12 w-12" />
                  </div>
                  <CardHeader>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-indigo-500 text-lg">&#9790;</span>
                      <Badge variant="outline">Dinner</Badge>
                    </div>
                    <CardTitle className="text-lg leading-relaxed">
                      {parsed.dinner}
                    </CardTitle>
                  </CardHeader>
                </Card>
              )}
            </div>
          ) : recommendation.meal_suggestion ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Utensils className="h-5 w-5 text-primary" />
                  Today&apos;s Meal Plan
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {recommendation.meal_suggestion}
                </p>
              </CardContent>
            </Card>
          ) : null}

          {/* Workout suggestion */}
          {recommendation.workout_suggestion && (
            <Card className="border-primary/20">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-primary" />
                  Workout Suggestion
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {recommendation.workout_suggestion}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Lifestyle / AI summary */}
          {(recommendation.lifestyle_suggestion || recommendation.ai_summary) && (
            <Card className="bg-primary text-primary-foreground border-0">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="h-5 w-5" />
                  AI Insights
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {recommendation.ai_summary && (
                  <p className="text-sm leading-relaxed border-l-2 border-primary-foreground/20 pl-4">
                    {recommendation.ai_summary}
                  </p>
                )}
                {recommendation.lifestyle_suggestion && (
                  <p className="text-sm leading-relaxed border-l-2 border-primary-foreground/20 pl-4">
                    {recommendation.lifestyle_suggestion}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Source note */}
          <p className="text-xs text-slate-400 text-center">
            Recommendations are generated by AI based on your profile, active nutrition goal, and meal history.
            Not a medical substitute. Consult a professional for personalized advice.
          </p>
        </>
      )}
    </div>
  );
}
