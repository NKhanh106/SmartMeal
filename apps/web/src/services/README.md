# Thư mục `services/` — API Service Layer

## Mục đích

Chứa toàn bộ các **typed API service functions** cho frontend SmartMeal. Mỗi service tương ứng với một nhóm chức năng của backend.

## Danh sách Services

| Service | File | Mô tả |
|---------|------|--------|
| `auth.service.ts` | Đăng nhập, đăng ký, refresh token, lấy thông tin user |
| `meal.service.ts` | CRUD meal logs (ghi nhận, xem, xóa bữa ăn) |
| `profile.service.ts` | CRUD user profile (hồ sơ thể chất) |
| `nutrition-goal.service.ts` | CRUD nutrition goals (mục tiêu dinh dưỡng) |
| `workout.service.ts` | CRUD workout plans (kế hoạch tập luyện) |
| `progress-log.service.ts` | CRUD progress logs (nhật ký theo dõi) |
| `analytics.service.ts` | Dashboard analytics (thống kê dinh dưỡng) |
| `chatbot.service.ts` | AI chatbot (sessions, messages, streaming) |
| `recommendation.service.ts` | AI recommendations (gợi ý từ AI) |
| `health-service.ts` | Health check endpoint |

## Cấu trúc Service

```typescript
// services/meal.service.ts
export const mealService = {
  // Lấy meal logs theo ngày
  async getMeals(date: string): Promise<MealLogResponse[]> {
    return api.get(`/api/v1/meal-logs?date=${date}`);
  },

  // Tạo meal log mới
  async createMeal(payload: CreateMealPayload): Promise<MealLogResponse> {
    return api.post("/api/v1/meal-logs", payload);
  },

  // Xóa meal log
  async deleteMeal(id: string): Promise<void> {
    return api.delete(`/api/v1/meal-logs/${id}`);
  },
};
```

## Sử dụng với TanStack Query

```typescript
// Trong React component
const { data, isLoading, error, refetch } = useQuery({
  queryKey: ["meals", date],
  queryFn: () => mealService.getMeals(date),
  enabled: isAuthenticated, // chỉ gọi khi đã đăng nhập
  staleTime: 5 * 60 * 1000, // 5 phút
});
```

## Chatbot Service (`chatbot.service.ts`)

Đặc biệt quan trọng — quản lý chatbot:

```typescript
// Lấy hoặc tạo session
const session = await getOrCreateSession();

// Gửi message và nhận AI reply
const reply = await chatbotService.sendMessage("Hôm nay ăn gì?");

// Khôi phục messages từ session trước
const history = await chatbotService.restoreMessages();

// Bắt đầu cuộc trò chuyện mới
const newSession = await chatbotService.startNewSession();
```

## Upload Service

Dùng chung qua `api.uploadFile`:

```typescript
const formData = new FormData();
formData.append("file", imageFile);
formData.append("image_type", "meal");

const result = await api.uploadFile<UploadedImageResponse>(
  "/api/v1/uploads",
  formData
);
```

## Best Practices

- Mỗi service function phải có **TypeScript types** cho request và response
- Dùng `useQuery` hoặc `useMutation` từ TanStack Query cho tất cả API calls
- Đặt `queryKey` nhất quán: `["resource", id]` hoặc `["resource", { filter }]`
- Handle loading và error states trong component
- Dùng `enabled` option để skip query khi chưa đăng nhập
