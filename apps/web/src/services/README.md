# services/ — Frontend API Services

Thư mục chứa các service functions — nơi duy nhất trong frontend gọi API endpoints của backend.

## Quy tắc

1. **Mỗi service = một domain** — không gộp chung nhiều domain vào 1 file.
2. **Tất cả API calls phải qua `api`** (từ `@/lib/api-client`) — không dùng `fetch` trực tiếp.
3. **Không hardcode base URL** — dùng `NEXT_PUBLIC_API_BASE_URL` từ `api-client.ts`.
4. **Dùng TypeScript types** từ `@/lib/types/api` — không `any`.
5. **Không gọi Gemini/OpenAI từ frontend** — chỉ gọi backend endpoints.

## Các services

| Service | File | Backend prefix | Mô tả |
|---------|------|---------------|--------|
| `auth` | `auth.service.ts` | `/api/v1/auth` | Login, register, logout, get current user |
| `profile` | `profile.service.ts` | `/api/v1/user-profiles` | CRUD health profile |
| `nutrition-goal` | `nutrition-goal.service.ts` | `/api/v1/nutrition-goals` | Calculate BMR/TDEE, create/view active goal |
| `meal` | `meal.service.ts` | `/api/v1/meal-logs` + `/api/v1/ai/meal-update` | CRUD meal logs, upload ảnh AI preview/confirm |
| `analytics` | `analytics.service.ts` | `/api/v1/dashboard` | Daily/weekly nutrition stats |
| `workout` | `workout.service.ts` | `/api/v1/workout-plans` | CRUD workout plans, workout items |
| `progress-log` | `progress-log.service.ts` | `/api/v1/progress-logs` | CRUD body measurement logs |
| `recommendation` | `recommendation.service.ts` | `/api/v1/ai/daily-planner` | Generate/view AI daily recommendations |
| `chatbot` | `chatbot.service.ts` | — | **Mock only** — chưa có backend endpoint |
| `health` | `health-service.ts` | `/health` | Backend health check |
| `mock` | `mockService.ts` | — | Mock data cho development |

## Cách gọi API đúng

### Dùng `api` (typed helpers — khuyên dùng)

```typescript
import { api } from "@/lib/api-client";
import type { MealLogResponse } from "@/lib/types/api";

// GET request
const meal: MealLogResponse = await api.get<MealLogResponse>(`/api/v1/meal-logs/${id}`);

// POST request
const created: MealLogResponse = await api.post<MealLogResponse>("/api/v1/meal-logs/", data);

// DELETE request
await api.delete<void>(`/api/v1/meal-logs/${id}`);
```

### Dùng `apiClient` (axios instance — khi cần custom config)

```typescript
import { apiClient } from "@/lib/api-client";

// Dùng khi cần custom timeout, headers...
const res = await apiClient.get("/some-endpoint", { timeout: 5000 });
```

### Upload file (dùng `api.uploadFile`)

```typescript
import { api } from "@/lib/api-client";

const formData = new FormData();
formData.append("image", file);
formData.append("meal_type", "bua_sang");

const result = await api.uploadFile<MealUpdatePreviewResponse>(
  "/api/v1/ai/meal-update/preview",
  formData
);
```

> **Lưu ý**: Không set `Content-Type: multipart/form-data` thủ công khi upload file. Axios tự compute `boundary`. Đã có trong `api.uploadFile`.

## API Client Flow

```
Service function
    ↓
api.get() / api.post() / api.uploadFile() ...
    ↓
handleRequest() (unwrap axios response)
    ↓
apiClient (axios instance)
    ↓
Request Interceptor → gắn JWT token từ localStorage
    ↓
Backend
    ↓
Response Interceptor → nếu 401 → xóa token, throw ApiError
```

## Error Handling

```typescript
import { api } from "@/lib/api-client";
import { ApiError } from "@/lib/api-client";

try {
  const result = await api.post<MealLogResponse>("/api/v1/meal-logs/", data);
} catch (err) {
  if (err instanceof ApiError) {
    console.error(`HTTP ${err.statusCode}: ${err.getUserMessage()}`);
    if (err.statusCode === 401) {
      // Redirect to login
    }
  }
}
```

## Auth Token

Token được lưu trong `localStorage` key `smartmeal_access_token`. JWT interceptor tự động gắn vào mọi request. Khi backend trả 401, interceptor tự động xóa token.

```typescript
// apps/web/src/lib/api-client.ts
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```
