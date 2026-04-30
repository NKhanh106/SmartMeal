# lib/ — Core Utilities & Client Config

Thư mục chứa các utilities cốt lõi và cấu hình phía client.

## Cấu trúc

```
lib/
├── api-client.ts     # Axios HTTP client + JWT interceptors
├── utils.ts          # Helpers chung (cn(), date formatting...)
├── profile-utils.ts  # Helpers chuyển đổi UI ↔ API format cho profile/goal
└── types/
    └── api.ts        # Shared TypeScript types đồng bộ với backend Pydantic schemas
```

## api-client.ts

Axios HTTP client — **điểm giao tiếp duy nhất** giữa frontend và backend.

### Cấu hình

```typescript
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});
```

### Interceptors

**Request interceptor** — tự động gắn JWT token:
```typescript
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY); // "smartmeal_access_token"
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

**Response interceptor** — xử lý 401 và chuẩn hóa lỗi:
```typescript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY); // Clear token on 401
    }
    return Promise.reject(ApiError.fromAxiosError(error));
  }
);
```

### Exports

| Export | Mô tả |
|--------|--------|
| `apiClient` | Axios instance — dùng khi cần custom config |
| `api` | Typed helpers: `get`, `post`, `put`, `patch`, `delete`, `uploadFile` |
| `TOKEN_KEY` | Key `"smartmeal_access_token"` dùng trong localStorage |
| `ApiError` | Custom error class — wrap AxiosError với statusCode + normalized data |
| `ApiErrorResponse` | Interface cho error response body |

### Typed helpers (`api`)

```typescript
export const api = {
  async get<T>(url: string, config?: RequestConfig): Promise<T> { ... },
  async post<T>(url: string, data?: unknown, config?: RequestConfig): Promise<T> { ... },
  async put<T>(url: string, data?: unknown, config?: RequestConfig): Promise<T> { ... },
  async patch<T>(url: string, data?: unknown, config?: RequestConfig): Promise<T> { ... },
  async delete<T>(url: string, config?: RequestConfig): Promise<T> { ... },
  async uploadFile<T>(url: string, formData: FormData, config?: RequestConfig): Promise<T> { ... },
};
```

> **Quan trọng**: `uploadFile` không set `Content-Type` thủ công. Axios phải tự compute `boundary` cho `multipart/form-data`.

## utils.ts

Hàm utility chung.

| Hàm | Mô tả |
|------|--------|
| `cn(...)` | Wrapper `clsx` + `tailwind-merge` — gộp class names có điều kiện |

```typescript
import { cn } from "@/lib/utils";

<div className={cn("base-class", isActive && "active-class", className)} />
```

## profile-utils.ts

Hàm chuyển đổi format giữa **UI form** và **API payload**.

### Vấn đề cần giải quyết

Backend dùng enum tiếng Việt và `date_of_birth`, frontend dùng `age` và `gender` dạng English:

| Trường | Backend (API) | Frontend (UI Form) |
|---------|--------------|---------------------|
| Giới tính | `"nam"` / `"nu"` / `"khac"` / `"khong_muon_noi"` | `"male"` / `"female"` / `"other"` |
| Hoạt động | `"it_van_dong"` / `"van_dong_nhe"` ... | `"sedentary"` / `"lightly_active"` ... |
| Ngày sinh | `"YYYY-MM-DD"` (VD `"1990-01-01"`) | `age: number` (VD `35`) |

### Các hàm chính

```typescript
// API → UI
apiProfileToForm(api: UserProfileResponse): ProfileFormData
apiGoalToForm(api: NutritionGoalResponse): GoalFormData
apiCalculationToForm(calc: NutritionGoalCalculateResponse, goalType, water?): GoalFormData

// UI → API
formDataToProfileCreate(form: ProfileFormData, dateOfBirth?): UserProfileCreate
formDataToProfileUpdate(form: ProfileFormData): UserProfileUpdate
formDataToGoalCreate(form: GoalFormData): NutritionGoalCreate
presetGoalTypeToApi(preset: string): NutritionGoalType  // "Weight Loss" → "giam_can"

// Helpers
calculateAge(birthDateStr: string): number
calculateBirthDate(age: number): string  // Trả về "YYYY-01-01"
```

## types/api.ts

Shared TypeScript types đồng bộ với backend Pydantic schemas. Mỗi interface tương ứng với một request/response schema ở backend.

### Các nhóm types

| Nhóm | Interfaces |
|------|-----------|
| Auth | `UserCreate`, `Token`, `UserResponse` |
| Profile | `UserProfileCreate`, `UserProfileUpdate`, `UserProfileResponse` |
| Nutrition Goal | `NutritionGoalCalculateRequest/Response`, `NutritionGoalCreate/Update/Response` |
| Meal | `MealLogCreate/Response`, `MealItemCreate/Response`, `MealUpdatePreview/Confirm*` |
| Dashboard | `DailyDashboardResponse`, `WeeklyDashboardResponse`, `MacroProgress` |
| Workout | `WorkoutPlanCreate/Update/Response`, `WorkoutItemCreate/Update/Response` |
| Progress | `ProgressLogCreate/Update/Response` |
| AI | `MealUpdatePreviewResponse`, `DailyRecommendationResponse`, `GenerateDailyPlannerResponse` |
| Enums | `Gender`, `ActivityLevel`, `DietType`, `NutritionGoalType`, `MealType`, `WorkoutDifficulty` |
