export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  age: number;
  gender: 'male' | 'female' | 'other';
  height: number;
  weight: number;
  activityLevel: 'sedentary' | 'lightly_active' | 'moderately_active' | 'very_active' | 'extra_active';
  healthGoals: string[];
}

export interface NutritionGoal {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  water: number;
}

export interface MealItem {
  id: string;
  name: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

export interface MealLog {
  id: string;
  timestamp: string;
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack';
  image?: string;
  items: MealItem[];
  totalCalories: number;
  totalProtein: number;
  totalCarbs: number;
  totalFat: number;
}

export interface DailyRecommendation {
  id: string;
  date: string;
  breakfast: string;
  lunch: string;
  dinner: string;
  snacks: string[];
  tips: string[];
}

export interface WorkoutItem {
  id: string;
  name: string;
  sets: number;
  reps: number;
  duration?: string;
  caloriesBurned?: number;
}

export interface WorkoutPlan {
  id: string;
  day: string;
  type: string;
  items: WorkoutItem[];
  totalEstimatedCalories: number;
}

export interface ProgressLog {
  date: string;
  weight: number;
  caloriesIn: number;
  caloriesOut: number;
}
