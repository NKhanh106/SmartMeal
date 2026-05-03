# Thư mục services/ - API Services

## Mục đích

Chứa các **API service modules** - nơi định nghĩa tất cả các function để gọi API backend. Mỗi service tập trung vào một domain (auth, meals, profile, etc.) giúp code có tổ chức và dễ bảo trì.

## Tại sao tách riêng services?

- **Separation of Concerns**: API calls tách biệt khỏi UI components
- **Reusability**: Nhiều components có thể dùng chung service
- **Type Safety**: TypeScript interfaces cho request/response
- **Error Handling**: Tập trung xử lý lỗi ở một chỗ
- **Testing**: Dễ dàng mock services cho unit tests

## Cấu trúc

```
services/
├── auth.service.ts           # Authentication
├── meal.service.ts           # Meal management
├── profile.service.ts        # User profile
├── nutrition-goal.service.ts  # Nutrition goals
├── workout.service.ts        # Workout plans
├── analytics.service.ts      # Dashboard analytics
├── chatbot.service.ts        # AI Chatbot
├── recommendation.service.ts  # AI Recommendations
├── progress-log.service.ts  # Progress tracking
├── health-service.ts        # Health check
└── mockService.ts           # Mock data for dev
```

## API Client Setup

Base axios instance với interceptors:

```typescript
// lib/api-client.ts
import axios from "axios";

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor - add auth token
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Response interceptor - handle errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired - redirect to login
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

## Các Services

### auth.service.ts
```typescript
export const authService = {
  // POST /api/v1/auth/register
  register: (data: RegisterDTO) => 
    apiClient.post("/api/v1/auth/register", data),
  
  // POST /api/v1/auth/login
  login: (data: LoginDTO) => 
    apiClient.post("/api/v1/auth/login", data),
  
  // POST /api/v1/auth/refresh
  refreshToken: (token: string) => 
    apiClient.post("/api/v1/auth/refresh", { refresh_token: token }),
  
  // POST /api/v1/auth/logout
  logout: () => 
    apiClient.post("/api/v1/auth/logout"),
};
```

### meal.service.ts
```typescript
export const mealService = {
  // GET /api/v1/meal-logs?date=YYYY-MM-DD
  getMeals: (date: string) => 
    apiClient.get("/api/v1/meal-logs", { params: { date } }),
  
  // POST /api/v1/meal-logs
  createMeal: (data: CreateMealDTO) => 
    apiClient.post("/api/v1/meal-logs", data),
  
  // PUT /api/v1/meal-logs/{id}
  updateMeal: (id: string, data: UpdateMealDTO) => 
    apiClient.put(`/api/v1/meal-logs/${id}`, data),
  
  // DELETE /api/v1/meal-logs/{id}
  deleteMeal: (id: string) => 
    apiClient.delete(`/api/v1/meal-logs/${id}`),
};
```

### profile.service.ts
```typescript
export const profileService = {
  // GET /api/v1/user-profiles/me
  getProfile: () => 
    apiClient.get("/api/v1/user-profiles/me"),
  
  // PUT /api/v1/user-profiles/me
  updateProfile: (data: UpdateProfileDTO) => 
    apiClient.put("/api/v1/user-profiles/me", data),
};
```

### nutrition-goal.service.ts
```typescript
export const nutritionGoalService = {
  // GET /api/v1/nutrition-goals
  getGoals: () => 
    apiClient.get("/api/v1/nutrition-goals"),
  
  // POST /api/v1/nutrition-goals
  createGoal: (data: CreateGoalDTO) => 
    apiClient.post("/api/v1/nutrition-goals", data),
  
  // PUT /api/v1/nutrition-goals/{id}
  updateGoal: (id: string, data: UpdateGoalDTO) => 
    apiClient.put(`/api/v1/nutrition-goals/${id}`, data),
};
```

### workout.service.ts
```typescript
export const workoutService = {
  // GET /api/v1/workout-plans
  getWorkoutPlans: () => 
    apiClient.get("/api/v1/workout-plans"),
  
  // POST /api/v1/workout-plans
  createPlan: (data: CreateWorkoutPlanDTO) => 
    apiClient.post("/api/v1/workout-plans", data),
  
  // GET /api/v1/workout-sessions
  getSessions: (params?: WorkoutSessionParams) => 
    apiClient.get("/api/v1/workout-sessions", { params }),
  
  // POST /api/v1/workout-sessions
  logSession: (data: LogSessionDTO) => 
    apiClient.post("/api/v1/workout-sessions", data),
};
```

### chatbot.service.ts
```typescript
export const chatbotService = {
  // GET /api/v1/chat/sessions
  getSessions: () => 
    apiClient.get("/api/v1/chat/sessions"),
  
  // POST /api/v1/chat/sessions
  createSession: () => 
    apiClient.post("/api/v1/chat/sessions"),
  
  // GET /api/v1/chat/sessions/{id}/messages
  getMessages: (sessionId: string) => 
    apiClient.get(`/api/v1/chat/sessions/${sessionId}/messages`),
  
  // POST /api/v1/chat/sessions/{id}/messages
  sendMessage: (sessionId: string, content: string) => 
    apiClient.post(`/api/v1/chat/sessions/${sessionId}/messages`, { content }),
};
```

### analytics.service.ts
```typescript
export const analyticsService = {
  // GET /api/v1/dashboard/summary
  getSummary: () => 
    apiClient.get("/api/v1/dashboard/summary"),
  
  // GET /api/v1/dashboard/weekly
  getWeeklyStats: () => 
    apiClient.get("/api/v1/dashboard/weekly"),
  
  // GET /api/v1/dashboard/monthly
  getMonthlyStats: () => 
    apiClient.get("/api/v1/dashboard/monthly"),
};
```

### mockService.ts
```typescript
// Mock data for development when API is not available
export const mockService = {
  getMockMeals: () => Promise.resolve(mockMealsData),
  getMockProfile: () => Promise.resolve(mockProfileData),
  getMockDashboard: () => Promise.resolve(mockDashboardData),
};
```

## Sử dụng với TanStack Query

```typescript
// Trong component
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { mealService } from "@/services/meal.service";

// Query - GET data
function MealList({ date }: { date: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["meals", date],
    queryFn: () => mealService.getMeals(date),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
  
  if (isLoading) return <Skeleton />;
  if (error) return <ErrorMessage />;
  
  return <MealListComponent meals={data} />;
}

// Mutation - POST/PUT/DELETE
function AddMealButton() {
  const queryClient = useQueryClient();
  
  const mutation = useMutation({
    mutationFn: mealService.createMeal,
    onSuccess: () => {
      // Invalidate queries to refetch
      queryClient.invalidateQueries({ queryKey: ["meals"] });
      toast.success("Meal added!");
    },
    onError: () => {
      toast.error("Failed to add meal");
    },
  });
  
  return (
    <Button 
      onClick={() => mutation.mutate(data)}
      disabled={mutation.isPending}
    >
      {mutation.isPending ? "Adding..." : "Add Meal"}
    </Button>
  );
}
```

## TypeScript Types

```typescript
// lib/types/api.ts
export interface LoginDTO {
  email: string;
  password: string;
}

export interface RegisterDTO extends LoginDTO {
  full_name: string;
}

export interface MealLogDTO {
  id: string;
  date: string;
  meal_type: "breakfast" | "lunch" | "dinner" | "snack";
  items: MealItemDTO[];
  total_calories: number;
  total_protein: number;
  total_carbs: number;
  total_fat: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}
```

## Error Handling

```typescript
async function handleApiCall() {
  try {
    const response = await apiClient.post("/endpoint", data);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response) {
        // Server responded with error
        const message = error.response.data?.message || "Server error";
        throw new Error(message);
      } else if (error.request) {
        // No response received
        throw new Error("Network error. Please check your connection.");
      }
    }
    throw new Error("An unexpected error occurred.");
  }
}
```

## Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```
