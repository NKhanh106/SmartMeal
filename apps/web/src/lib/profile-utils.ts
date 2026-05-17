/**
 * Mapping utilities between UI format and FastAPI backend format.
 *
 * UI format (profile page):
 *   age: number, gender: 'male'|'female'|'other', activityLevel: 'sedentary'|...
 *
 * API format (FastAPI):
 *   date_of_birth: 'YYYY-MM-DD', gender: 'nam'|'nu'|'khac'|'khong_muon_noi',
 *   activity_level: 'it_van_dong'|'van_dong_nhe'|...
 */

import type {
  Gender,
  ActivityLevel,
  NutritionGoalType,
  UserProfileResponse,
  UserProfileCreate,
  UserProfileUpdate,
  NutritionGoalResponse,
  NutritionGoalCreate,
  NutritionGoalCalculateResponse,
} from "@/lib/types/api";

// ─── Gender mapping ────────────────────────────────────────────────────────────

const UI_GENDER_TO_API: Record<string, Gender> = {
  male: "nam",
  female: "nu",
  other: "khac",
};

const API_GENDER_TO_UI: Record<Gender, string> = {
  nam: "male",
  nu: "female",
  khac: "other",
  khong_muon_noi: "other",
};

// ─── Activity level mapping ────────────────────────────────────────────────────

const UI_ACTIVITY_TO_API: Record<string, ActivityLevel> = {
  sedentary: "it_van_dong",
  lightly_active: "van_dong_nhe",
  moderately_active: "van_dong_vua",
  very_active: "van_dong_nhieu",
  extra_active: "van_dong_rat_nhieu",
};

const API_ACTIVITY_TO_UI: Record<ActivityLevel, string> = {
  it_van_dong: "sedentary",
  van_dong_nhe: "lightly_active",
  van_dong_vua: "moderately_active",
  van_dong_nhieu: "very_active",
  van_dong_rat_nhieu: "extra_active",
};

// ─── Date-of-birth helpers ────────────────────────────────────────────────────

function calculateAge(birthDateStr: string): number {
  const birth = new Date(birthDateStr);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const monthDiff = today.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
    age--;
  }
  return age;
}

function calculateBirthDate(age: number): string {
  const today = new Date();
  const birthYear = today.getFullYear() - age;
  return `${birthYear}-01-01`;
}

// ─── Profile mapping ───────────────────────────────────────────────────────────

export interface ProfileFormData {
  age: number;
  gender: "male" | "female" | "other";
  height: number;
  weight: number;
  activityLevel: string;
  goalType?: NutritionGoalType;
}

/** Convert API UserProfileResponse → UI ProfileFormData */
export function apiProfileToForm(api: UserProfileResponse): ProfileFormData {
  return {
    age: calculateAge(api.date_of_birth),
    gender: (API_GENDER_TO_UI[api.gender] as "male" | "female" | "other") ?? "other",
    height: Number(api.height_cm),
    weight: Number(api.current_weight_kg),
    activityLevel: API_ACTIVITY_TO_UI[api.activity_level] ?? "sedentary",
  };
}

/** Convert UI ProfileFormData → API UserProfileCreate (for new profile) */
export function formDataToProfileCreate(
  form: ProfileFormData,
  dateOfBirth?: string
): UserProfileCreate {
  return {
    gender: UI_GENDER_TO_API[form.gender] ?? "khong_muon_noi",
    date_of_birth: dateOfBirth ?? calculateBirthDate(form.age),
    height_cm: form.height,
    current_weight_kg: form.weight,
    activity_level: UI_ACTIVITY_TO_API[form.activityLevel] ?? "it_van_dong",
  };
}

/** Convert UI ProfileFormData → API UserProfileUpdate */
export function formDataToProfileUpdate(form: ProfileFormData): UserProfileUpdate {
  return {
    gender: UI_GENDER_TO_API[form.gender] ?? "khong_muon_noi",
    date_of_birth: calculateBirthDate(form.age),
    height_cm: form.height,
    current_weight_kg: form.weight,
    activity_level: UI_ACTIVITY_TO_API[form.activityLevel] ?? "it_van_dong",
  };
}

// ─── Nutrition Goal mapping ────────────────────────────────────────────────────

export interface GoalFormData {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  water: number;
  goalType: NutritionGoalType;
}

/** Convert API NutritionGoalResponse → UI GoalFormData */
export function apiGoalToForm(api: NutritionGoalResponse): GoalFormData {
  return {
    calories: Math.round(api.daily_calorie_target),
    protein: Math.round(api.protein_target_g),
    carbs: Math.round(api.carb_target_g),
    fat: Math.round(api.fat_target_g),
    // Convert ml to liters for the UI (form stores liters, backend stores ml)
    water: api.hydration_goal_ml ? api.hydration_goal_ml / 1000 : 2.5,
    goalType: api.goal_type,
  };
}

/** Convert UI GoalFormData → API NutritionGoalCreate */
export function formDataToGoalCreate(form: GoalFormData): NutritionGoalCreate {
  return {
    goal_type: form.goalType,
    hydration_goal_ml: Math.round(form.water * 1000), // Convert liters to ml
    note: "",
  };
}

/** Merge goal data into ProfileFormData (goal is fetched separately) */
export function applyGoalToFormData(
  form: ProfileFormData,
  goal: NutritionGoalResponse
): ProfileFormData {
  return { ...form, goalType: goal.goal_type };
}
export function presetGoalTypeToApi(preset: string): NutritionGoalType {
  switch (preset) {
    case "Weight Loss":
      return "giam_can";
    case "Maintenance":
      return "giu_can";
    case "Muscle Gain":
      return "tang_co";
    default:
      return "giu_can";
  }
}

/** Map NutritionGoalCalculateResponse (preview) → UI GoalFormData */
export function apiCalculationToForm(
  calc: NutritionGoalCalculateResponse,
  goalType: NutritionGoalType,
  water: number = 2.5
): GoalFormData {
  return {
    calories: Math.round(calc.daily_calorie_target),
    protein: Math.round(calc.protein_target_g),
    carbs: Math.round(calc.carb_target_g),
    fat: Math.round(calc.fat_target_g),
    water,
    goalType,
  };
}
