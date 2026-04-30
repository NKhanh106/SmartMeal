import {
  UserProfile,
  NutritionGoal,
  MealLog,
  DailyRecommendation,
  WorkoutPlan,
  ProgressLog,
} from "@/types";
import {
  mockUserProfile,
  mockNutritionGoal,
  mockMealLogs,
  mockDailyRecommendation,
  mockWorkoutPlan,
  mockProgressLogs,
} from "@/data/mockData";

const delay = (ms: number) =>
  new Promise((resolve) => setTimeout(resolve, ms));

export const getUserProfile = async (): Promise<UserProfile> => {
  await delay(800);
  return { ...mockUserProfile };
};

export const updateUserProfile = async (
  profile: Partial<UserProfile>
): Promise<UserProfile> => {
  await delay(1000);
  return { ...mockUserProfile, ...profile };
};

export const getNutritionGoals = async (): Promise<NutritionGoal> => {
  await delay(500);
  return { ...mockNutritionGoal };
};

export const updateNutritionGoals = async (
  goals: Partial<NutritionGoal>
): Promise<NutritionGoal> => {
  await delay(1000);
  return { ...mockNutritionGoal, ...goals };
};

export const uploadMealImage = async (file: File): Promise<string> => {
  await delay(1500);
  return URL.createObjectURL(file);
};

export const analyzeMealImage = async (imageUrl: string): Promise<MealLog> => {
  await delay(2000);
  return {
    ...mockMealLogs[0],
    id: Math.random().toString(36).substring(2, 11),
    timestamp: new Date().toISOString(),
    image: imageUrl,
  };
};

export const getMealLogs = async (): Promise<MealLog[]> => {
  await delay(800);
  return [...mockMealLogs];
};

export const getNutritionAnalytics = async (): Promise<ProgressLog[]> => {
  await delay(1000);
  return [...mockProgressLogs];
};

export const getDailyRecommendation = async (): Promise<DailyRecommendation> => {
  await delay(700);
  return { ...mockDailyRecommendation };
};

export const getWorkoutPlan = async (): Promise<WorkoutPlan[]> => {
  await delay(900);
  return [...mockWorkoutPlan];
};
