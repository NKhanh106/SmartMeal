"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import { profileService } from "@/services/profile.service";
import { nutritionGoalService } from "@/services/nutrition-goal.service";
import type { NutritionGoalResponse, NutritionGoalType, UserProfileCreate, UserProfileUpdate } from "@/lib/types/api";
import {
  apiProfileToForm,
  formDataToProfileCreate,
  formDataToProfileUpdate,
  applyGoalToFormData,
  type ProfileFormData,
} from "@/lib/profile-utils";
import { useAuth } from "@/contexts/auth-context";
import { useToast } from "@/hooks/use-toast";

const EMPTY_FORM: ProfileFormData = {
  age: 25,
  gender: "male",
  height: 170,
  weight: 65,
  activityLevel: "moderately_active",
  goalType: undefined,
};

const GOAL_TYPE_OPTIONS: { value: NutritionGoalType; label: string }[] = [
  { value: "giam_can", label: "Weight Loss (Giảm cân)" },
  { value: "giu_can", label: "Maintenance (Giữ cân)" },
  { value: "tang_co", label: "Muscle Gain (Tăng cơ)" },
];

const ACTIVITY_OPTIONS = [
  { value: "sedentary", label: "Sedentary (Little to no exercise)" },
  { value: "lightly_active", label: "Lightly Active (1-3 days/week)" },
  { value: "moderately_active", label: "Moderately Active (3-5 days/week)" },
  { value: "very_active", label: "Very Active (6-7 days/week)" },
  { value: "extra_active", label: "Extra Active (Athlete/Physical job)" },
];

const GENDER_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
];

export default function ProfilePage() {
  const { user } = useAuth();
  const { toast } = useToast();

  const [formData, setFormData] = useState<ProfileFormData>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof ProfileFormData, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [hasProfile, setHasProfile] = useState(false);
  const [existingGoal, setExistingGoal] = useState<NutritionGoalResponse | null>(null);

  const didInit = useRef(false);

  // Load profile + active nutrition goal on mount
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;

    profileService
      .getMyProfile()
      .then(async (data) => {
        setFormData((prev) => apiProfileToForm(data));
        setHasProfile(true);
        // Also fetch active goal and merge goalType into form
        try {
          const goal = await nutritionGoalService.getActiveGoal();
          setFormData((prev) => applyGoalToFormData(apiProfileToForm(data), goal));
          setExistingGoal(goal);
        } catch {
          // no active goal yet — that's fine
        }
      })
      .catch((err: unknown) => {
        setHasProfile(false);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const validate = (data: ProfileFormData): boolean => {
    const errors: Partial<Record<keyof ProfileFormData, string>> = {};
    if (!data.age || data.age < 1 || data.age > 120) {
      errors.age = "Age must be between 1 and 120.";
    }
    if (!data.gender) {
      errors.gender = "Gender is required.";
    }
    if (!data.height || data.height < 50 || data.height > 250) {
      errors.height = "Height must be between 50 and 250 cm.";
    }
    if (!data.weight || data.weight < 20 || data.weight > 300) {
      errors.weight = "Weight must be between 20 and 300 kg.";
    }
    if (!data.activityLevel) {
      errors.activityLevel = "Activity level is required.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSave = async () => {
    if (!validate(formData)) {
      toast({ title: "Please fix the errors before saving.", variant: "destructive" });
      return;
    }

    setSubmitting(true);
    try {
      if (hasProfile) {
        const payload: UserProfileUpdate = formDataToProfileUpdate(formData);
        const updated = await profileService.updateMyProfile(payload);
        setFormData(apiProfileToForm(updated));
        toast({ title: "Profile updated successfully." });
      } else {
        const payload: UserProfileCreate = formDataToProfileCreate(formData);
        const created = await profileService.createProfile(payload);
        setFormData(apiProfileToForm(created));
        setHasProfile(true);
        toast({ title: "Profile created successfully." });
      }

      // Create or update active nutrition goal
      if (formData.goalType) {
        await nutritionGoalService.createGoal({ goal_type: formData.goalType });
        const goal = await nutritionGoalService.getActiveGoal();
        setExistingGoal(goal);
        toast({ title: "Nutrition goal saved." });
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number }; message?: string };
      toast({
        title: "Failed to save profile.",
        description: axiosErr.message ?? "Please try again.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (field: keyof ProfileFormData, value: string | number | undefined) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-48" />
        <div className="grid gap-6 md:grid-cols-3">
          <Card>
            <CardContent className="p-6 flex flex-col items-center text-center">
              <Skeleton className="h-32 w-32 rounded-full mb-4" />
              <Skeleton className="h-6 w-40 mb-2" />
              <Skeleton className="h-4 w-32" />
            </CardContent>
          </Card>
          <Card className="md:col-span-2">
            <CardContent className="p-6 space-y-4">
              <Skeleton className="h-4 w-32" />
              <div className="grid grid-cols-2 gap-4">
                {[...Array(4)].map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Health Profile</h1>
        <p className="text-muted-foreground">Your personal health and fitness information.</p>
      </div>

      {!hasProfile && (
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="p-4 text-center">
            <p className="text-orange-700 font-medium mb-1">No profile found.</p>
            <p className="text-sm text-orange-600">
              Please fill in the form below and click Save to create your health profile.
            </p>
          </CardContent>
        </Card>
      )}

      <ProfileForm
        formData={formData}
        fieldErrors={fieldErrors}
        submitting={submitting}
        onChange={handleChange}
        onSave={handleSave}
        userName={user?.full_name ?? user?.email ?? "User"}
        userEmail={user?.email}
      />
    </div>
  );
}

// ── Form components ────────────────────────────────────────────────────────────

function ProfileFormFields({
  formData,
  fieldErrors,
  onChange,
}: {
  formData: ProfileFormData;
  fieldErrors: Partial<Record<keyof ProfileFormData, string>>;
  onChange: (field: keyof ProfileFormData, value: string | number | undefined) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-2">
        <Label htmlFor="age">Age</Label>
        <Input
          id="age"
          type="number"
          min={1}
          max={120}
          value={formData.age}
          onChange={(e) => onChange("age", Number(e.target.value))}
        />
        {fieldErrors.age && <p className="text-xs text-red-500">{fieldErrors.age}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="gender">Gender</Label>
        <select
          id="gender"
          className="w-full p-2 rounded-md border border-zinc-200 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 transition-colors"
          value={formData.gender}
          onChange={(e) => onChange("gender", e.target.value)}
        >
          {GENDER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {fieldErrors.gender && <p className="text-xs text-red-500">{fieldErrors.gender}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="height">Height (cm)</Label>
        <Input
          id="height"
          type="number"
          min={50}
          max={250}
          value={formData.height}
          onChange={(e) => onChange("height", Number(e.target.value))}
        />
        {fieldErrors.height && <p className="text-xs text-red-500">{fieldErrors.height}</p>}
      </div>

      <div className="space-y-2">
        <Label htmlFor="weight">Weight (kg)</Label>
        <Input
          id="weight"
          type="number"
          min={20}
          max={300}
          value={formData.weight}
          onChange={(e) => onChange("weight", Number(e.target.value))}
        />
        {fieldErrors.weight && <p className="text-xs text-red-500">{fieldErrors.weight}</p>}
      </div>

      <div className="space-y-2">
        <Label>Activity Level</Label>
        <p className="text-xs text-muted-foreground mb-2">
          How much do you move on average?
        </p>
        <select
          className="w-full p-2 rounded-md border border-zinc-200 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 transition-colors"
          value={formData.activityLevel}
          onChange={(e) => onChange("activityLevel", e.target.value)}
        >
          {ACTIVITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {fieldErrors.activityLevel && (
          <p className="text-xs text-red-500">{fieldErrors.activityLevel}</p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="goalType">Goal</Label>
        <p className="text-xs text-muted-foreground mb-2">
          Your primary health goal.
        </p>
        <select
          id="goalType"
          className="w-full p-2 rounded-md border border-zinc-200 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 transition-colors"
          value={formData.goalType ?? ""}
          onChange={(e) =>
            onChange("goalType", (e.target.value || undefined) as NutritionGoalType | undefined)
          }
        >
          <option value="">— Select a goal —</option>
          {GOAL_TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function ProfileForm({
  formData,
  fieldErrors,
  submitting,
  onChange,
  onSave,
  userName,
  userEmail,
}: {
  formData: ProfileFormData;
  fieldErrors: Partial<Record<keyof ProfileFormData, string>>;
  submitting: boolean;
  onChange: (field: keyof ProfileFormData, value: string | number | undefined) => void;
  onSave: () => void;
  userName: string;
  userEmail?: string;
}) {
  return (
    <div className="grid gap-6 md:grid-cols-3">
      <Card className="md:col-span-1">
        <CardContent className="p-6 flex flex-col items-center text-center">
          <Avatar className="h-32 w-32 mb-4 border-4 border-primary/10">
            <AvatarFallback>{userName[0]}</AvatarFallback>
          </Avatar>
          <h2 className="text-xl font-bold">{userName}</h2>
          {userEmail && (
            <p className="text-sm text-muted-foreground">{userEmail}</p>
          )}
          <Button variant="outline" size="sm" className="mt-4">
            Change Avatar
          </Button>
        </CardContent>
      </Card>

      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle>Physical Information</CardTitle>
          <CardDescription>
            Used to calculate basic metabolic rate, caloric needs, and your nutrition goal.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <ProfileFormFields
            formData={formData}
            fieldErrors={fieldErrors}
            onChange={onChange}
          />
          <Button className="w-full md:w-auto" onClick={onSave} disabled={submitting}>
            {submitting ? "Saving..." : "Save Profile"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
