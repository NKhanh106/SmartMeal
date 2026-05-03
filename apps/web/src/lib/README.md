# Thư mục lib/ - Utilities & Core Library

## Mục đích

Chứa các **utility functions, configurations, và helpers** được sử dụng xuyên suốt ứng dụng. Đây là nơi đặt code có thể tái sử dụng ở nhiều nơi khác nhau.

## Cấu trúc

```
lib/
├── api-client.ts       # Axios instance với interceptors
├── utils.ts           # Common utility functions
├── profile-utils.ts    # Profile-related utilities
└── types/             # TypeScript type definitions
    └── api.ts         # API-related types
```

## api-client.ts - Axios Configuration

Base HTTP client cho tất cả API calls:

```typescript
import axios from "axios";

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor - attach auth token
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle global errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Token expired - try to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        const response = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/refresh`,
          { refresh_token: refreshToken }
        );

        const { access_token } = response.data.data;
        localStorage.setItem("token", access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;

        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed - redirect to login
        localStorage.removeItem("token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
```

## utils.ts - Common Utilities

### cn() - Class Name Merger
Kết hợp Tailwind classes một cách an toàn:

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### formatDate()
Format ngày tháng:

```typescript
export function formatDate(date: string | Date, format: string = "DD/MM/YYYY"): string {
  const d = typeof date === "string" ? new Date(date) : date;
  
  const day = d.getDate().toString().padStart(2, "0");
  const month = (d.getMonth() + 1).toString().padStart(2, "0");
  const year = d.getFullYear();
  
  return `${day}/${month}/${year}`;
}
```

### formatNumber()
Format số với separator:

```typescript
export function formatNumber(num: number, decimals: number = 1): string {
  return num.toLocaleString("vi-VN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
```

### calculateBMI()
Tính BMI từ cân nặng và chiều cao:

```typescript
export function calculateBMI(weightKg: number, heightCm: number): number {
  const heightM = heightCm / 100;
  return weightKg / (heightM * heightM);
}

export function getBMICategory(bmi: number): string {
  if (bmi < 18.5) return "Underweight";
  if (bmi < 25) return "Normal";
  if (bmi < 30) return "Overweight";
  return "Obese";
}
```

### calculateBMR()
Tính BMR (Basal Metabolic Rate):

```typescript
export function calculateBMR(
  weightKg: number,
  heightCm: number,
  age: number,
  gender: "male" | "female"
): number {
  if (gender === "male") {
    return 88.362 + 13.397 * weightKg + 4.799 * heightCm - 5.677 * age;
  }
  return 447.593 + 9.247 * weightKg + 3.098 * heightCm - 4.33 * age;
}
```

### calculateTDEE()
Tính TDEE (Total Daily Energy Expenditure):

```typescript
export function calculateTDEE(
  bmr: number,
  activityLevel: "sedentary" | "light" | "moderate" | "active" | "very_active"
): number {
  const multipliers = {
    sedentary: 1.2,
    light: 1.375,
    moderate: 1.55,
    active: 1.725,
    very_active: 1.9,
  };
  return bmr * multipliers[activityLevel];
}
```

### debounce()
Debounce function:

```typescript
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}
```

### Local Storage Helpers

```typescript
export const storage = {
  get: <T>(key: string, defaultValue: T): T => {
    if (typeof window === "undefined") return defaultValue;
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  },
  
  set: <T>(key: string, value: T): void => {
    if (typeof window !== "undefined") {
      localStorage.setItem(key, JSON.stringify(value));
    }
  },
  
  remove: (key: string): void => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(key);
    }
  },
};
```

## profile-utils.ts - Profile Utilities

### calculateDailyCalories()
Tính lượng calories cần thiết hàng ngày:

```typescript
export function calculateDailyCalories(
  profile: UserProfile,
  goal: "loss" | "maintain" | "gain"
): number {
  const bmr = calculateBMR(
    profile.weight,
    profile.height,
    profile.age,
    profile.gender
  );
  
  const tdee = calculateTDEE(bmr, profile.activity_level);
  
  if (goal === "loss") return Math.round(tdee * 0.8); // 20% deficit
  if (goal === "gain") return Math.round(tdee * 1.15); // 15% surplus
  return Math.round(tdee);
}
```

### getMacroGoals()
Tính macro goals từ calories:

```typescript
export function getMacroGoals(
  calories: number,
  goal: "balanced" | "low_carb" | "high_protein"
): { protein: number; carbs: number; fat: number } {
  switch (goal) {
    case "high_protein":
      return {
        protein: Math.round(calories * 0.35 / 4), // 35% protein
        carbs: Math.round(calories * 0.35 / 4),    // 35% carbs
        fat: Math.round(calories * 0.30 / 9),       // 30% fat
      };
    case "low_carb":
      return {
        protein: Math.round(calories * 0.30 / 4),
        carbs: Math.round(calories * 0.25 / 4),
        fat: Math.round(calories * 0.45 / 9),
      };
    default:
      return {
        protein: Math.round(calories * 0.25 / 4),
        carbs: Math.round(calories * 0.50 / 4),
        fat: Math.round(calories * 0.25 / 9),
      };
  }
}
```

## types/api.ts - TypeScript Types

```typescript
// Common types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  errors?: string[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

// User types
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "user" | "admin";
  created_at: string;
}

export interface UserProfile {
  id: string;
  user_id: string;
  age: number;
  gender: "male" | "female";
  height: number; // cm
  weight: number; // kg
  activity_level: ActivityLevel;
  health_goals: HealthGoal[];
  avatar_url?: string;
}

// Nutrition types
export interface NutritionGoal {
  daily_calories: number;
  protein_goal: number; // grams
  carbs_goal: number;   // grams
  fat_goal: number;     // grams
}

// Meal types
export type MealType = "breakfast" | "lunch" | "dinner" | "snack";

export interface MealLog {
  id: string;
  user_id: string;
  date: string;
  meal_type: MealType;
  items: MealItem[];
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fat: number;
  notes?: string;
}

export interface MealItem {
  food_nutrition_id: string;
  food_name: string;
  quantity: number;      // grams
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}
```
