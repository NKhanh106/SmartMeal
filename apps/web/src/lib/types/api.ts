/**
 * Shared API types that mirror FastAPI backend schemas.
 * Naming convention matches backend Pydantic schema field names.
 */

// ─── Enums (mirrored from backend) ────────────────────────────────────────────

export type Gender = "nam" | "nu" | "khac" | "khong_muon_noi";
export type ActivityLevel = "it_van_dong" | "van_dong_nhe" | "van_dong_vua" | "van_dong_nhieu" | "van_dong_rat_nhieu";
export type DietType = "binh_thuong" | "an_chay" | "thuan_chay" | "keto" | "it_tinh_bot" | "nhieu_dam" | "khac";
export type NutritionGoalType = "giam_can" | "giu_can" | "tang_co";
export type MealType = "bua_sang" | "bua_trua" | "bua_toi" | "an_vat" | "khac";
export type WorkoutDifficulty = "nguoi_moi" | "trung_binh" | "nang_cao";

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  username: string; // backend expects "username" (email) per OAuth2 spec
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name?: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

// ─── User Profile ──────────────────────────────────────────────────────────────

export interface UserProfileCreate {
  gender: Gender;
  date_of_birth: string; // YYYY-MM-DD
  height_cm: number;
  current_weight_kg: number;
  current_body_fat_percent?: number;
  current_waist_cm?: number;
  current_neck_cm?: number;
  current_hip_cm?: number;
  current_chest_cm?: number;
  activity_level?: ActivityLevel;
  diet_type?: DietType;
  allergies?: string;
  disliked_foods?: string;
  preferred_foods?: string;
  health_note?: string;
}

export type UserProfileUpdate = Partial<UserProfileCreate>;

export interface UserProfileResponse {
  id: string;
  user_id: string;
  gender: Gender;
  date_of_birth: string;
  height_cm: number;
  current_weight_kg: number;
  current_body_fat_percent?: number;
  current_waist_cm?: number;
  current_neck_cm?: number;
  current_hip_cm?: number;
  current_chest_cm?: number;
  activity_level: ActivityLevel;
  diet_type: DietType;
  allergies?: string;
  disliked_foods?: string;
  preferred_foods?: string;
  health_note?: string;
  created_at: string;
  updated_at: string;
}

// ─── Nutrition Goal ────────────────────────────────────────────────────────────

export interface NutritionGoalCalculateRequest {
  goal_type: NutritionGoalType;
  target_weight_kg?: number;
  start_date?: string;
  end_date?: string;
}

export interface NutritionGoalCalculateResponse {
  bmi: number;
  bmr_kcal: number;
  tdee_kcal: number;
  daily_calorie_target: number;
  protein_target_g: number;
  carb_target_g: number;
  fat_target_g: number;
}

export interface NutritionGoalCreate {
  goal_type: NutritionGoalType;
  target_weight_kg?: number;
  start_date?: string;
  end_date?: string;
  note?: string;
}

export type NutritionGoalUpdate = Partial<NutritionGoalCreate>;

export interface NutritionGoalResponse {
  id: string;
  user_id: string;
  goal_type: NutritionGoalType;
  target_weight_kg?: number;
  start_date: string;
  end_date?: string;
  bmi?: number;
  bmr_kcal?: number;
  tdee_kcal?: number;
  daily_calorie_target: number;
  protein_target_g: number;
  carb_target_g: number;
  fat_target_g: number;
  note?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// ─── Meal Log ─────────────────────────────────────────────────────────────────

export interface MealItemCreate {
  food_nutrition_id?: string;
  detected_food_name?: string;
  display_food_name?: string;
  estimated_weight_g: number;
  source?: string;
  confidence?: number;
}

export interface MealLogCreate {
  nutrition_goal_id?: string;
  meal_type: MealType;
  meal_time?: string;
  image_url?: string;
  image_storage_path?: string;
  note?: string;
  items: MealItemCreate[];
}

export interface MealItemResponse {
  id: string;
  meal_log_id: string;
  food_nutrition_id?: string;
  detected_food_name: string;
  display_food_name?: string;
  estimated_weight_g?: number;
  calories: number;
  protein_g: number;
  carb_g: number;
  fat_g: number;
  confidence?: number;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface MealLogResponse {
  id: string;
  user_id: string;
  nutrition_goal_id?: string;
  meal_type: MealType;
  meal_time: string;
  image_url?: string;
  image_storage_path?: string;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  note?: string;
  created_at: string;
  updated_at: string;
  items: MealItemResponse[];
}

export type MealLogSummaryResponse = Omit<MealLogResponse, "items">;

// ─── AI Meal Update ────────────────────────────────────────────────────────────

export interface MealUpdatePreviewItem {
  detected_food_name: string;
  matched_food_id?: string;
  match_status: "matched" | "partial" | "not_found";
  estimated_weight_g: number;
  confidence: number;
  calories?: number;
  protein_g?: number;
  carb_g?: number;
  fat_g?: number;
}

export interface MealUpdatePreviewResponse {
  items: MealUpdatePreviewItem[];
  overall_confidence: number;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  meal_type: string;
  ai_model?: string;
}

export interface MealUpdateConfirmItem {
  food_nutrition_id?: string;
  detected_food_name: string;
  display_food_name?: string;
  estimated_weight_g: number;
  confidence?: number;
}

export interface MealUpdateConfirmRequest {
  meal_type: string;
  meal_time?: string;
  items: MealUpdateConfirmItem[];
}

export interface MealUpdateConfirmResponse {
  meal_log_id: string;
  message: string;
}

// ─── Dashboard / Analytics ──────────────────────────────────────────────────────

export interface MacroProgress {
  consumed: number;
  target?: number;
  remaining?: number;
  percent?: number;
}

export interface NutritionGoalSummary {
  id: string;
  goal_type: string;
  daily_calorie_target?: number;
  protein_target_g?: number;
  carb_target_g?: number;
  fat_target_g?: number;
}

export interface DailyMealSummary {
  id: string;
  meal_type: MealType;
  meal_time: string;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  note?: string;
}

export interface DailyDashboardResponse {
  user_id: string;
  target_date: string;
  active_goal?: NutritionGoalSummary;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  calories_progress: MacroProgress;
  protein_progress: MacroProgress;
  carb_progress: MacroProgress;
  fat_progress: MacroProgress;
  meal_count: number;
  meals: DailyMealSummary[];
}

export interface WeeklyDailyItem {
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  meal_count: number;
}

export interface WeeklyDashboardResponse {
  user_id: string;
  start_date: string;
  end_date: string;
  active_goal?: NutritionGoalSummary;
  total_calories: number;
  avg_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  daily_items: WeeklyDailyItem[];
}

// ─── Progress Log ──────────────────────────────────────────────────────────────

export interface ProgressLogCreate {
  log_date: string;
  weight_kg?: number;
  body_fat_percent?: number;
  waist_cm?: number;
  neck_cm?: number;
  chest_cm?: number;
  hip_cm?: number;
  progress_photo_url?: string;
  note?: string;
}

export type ProgressLogUpdate = Partial<Omit<ProgressLogCreate, "log_date">>;

export interface ProgressLogResponse {
  id: string;
  user_id: string;
  log_date: string;
  weight_kg?: number;
  body_fat_percent?: number;
  waist_cm?: number;
  neck_cm?: number;
  chest_cm?: number;
  hip_cm?: number;
  progress_photo_url?: string;
  note?: string;
  created_at: string;
  updated_at: string;
}

// ─── Workout ──────────────────────────────────────────────────────────────────

export interface WorkoutItemCreate {
  workout_date?: string;
  day_of_week?: number;
  muscle_group?: string;
  exercise_name: string;
  weight_kg?: number;
  sets?: number;
  reps?: number;
  duration_minutes?: number;
  rest_seconds?: number;
  order_index?: number;
  note?: string;
}

export type WorkoutItemUpdate = Partial<WorkoutItemCreate>;

export interface WorkoutItemResponse {
  id: string;
  workout_plan_id: string;
  workout_date?: string;
  day_of_week?: number;
  muscle_group?: string;
  exercise_name: string;
  weight_kg?: number;
  sets?: number;
  reps?: number;
  duration_minutes?: number;
  rest_seconds?: number;
  order_index: number;
  is_completed: boolean;
  completed_at?: string;
  note?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkoutPlanCreate {
  plan_name: string;
  goal_type?: NutritionGoalType;
  difficulty?: WorkoutDifficulty;
  start_date?: string;
  end_date?: string;
  note?: string;
  is_active?: boolean;
}

export type WorkoutPlanUpdate = Partial<WorkoutPlanCreate>;

export interface WorkoutPlanResponse {
  id: string;
  user_id: string;
  plan_name: string;
  goal_type?: string;
  difficulty: string;
  start_date: string;
  end_date?: string;
  is_active: boolean;
  note?: string;
  created_at: string;
  updated_at: string;
}

export interface WorkoutPlanDetailResponse extends WorkoutPlanResponse {
  items: WorkoutItemResponse[];
}

export interface WorkoutPlanWithItemsCreate extends WorkoutPlanCreate {
  items: WorkoutItemCreate[];
}

// ─── Daily Recommendation ──────────────────────────────────────────────────────

export interface DailyRecommendationResponse {
  id: string;
  user_id: string;
  recommendation_date: string;
  calories_target?: number;
  protein_target_g?: number;
  carb_target_g?: number;
  fat_target_g?: number;
  meal_suggestion?: string;
  workout_suggestion?: string;
  lifestyle_suggestion?: string;
  ai_summary?: string;
  ai_analysis_log_id?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GenerateDailyPlannerResponse {
  recommendation: DailyRecommendationResponse;
}

// ─── Food Nutrition ────────────────────────────────────────────────────────────

export interface FoodNutritionResponse {
  id: string;
  food_name: string;
  food_name_vi?: string;
  food_name_en?: string;
  category?: string;
  serving_size_g?: number;
  calories_per_100g?: number;
  protein_per_100g?: number;
  carb_per_100g?: number;
  fat_per_100g?: number;
  fiber_per_100g?: number;
  sugar_per_100g?: number;
  sodium_mg_per_100g?: number;
  source?: string;
  is_verified?: boolean;
  created_by_user_id?: string;
  created_at: string;
  updated_at: string;
}
