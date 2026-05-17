# Thư mục `api/v1/` — API v1 Endpoints

## Mục đích

Chứa toàn bộ **HTTP API endpoints** của backend SmartMeal. Mỗi file Python tương ứng với một nhóm chức năng riêng biệt. Tất cả các router đều được đăng ký trong `main.py` với prefix `/api/v1`.

## Kiến trúc

```
HTTP Request
    │
    ▼
FastAPI Router (api/v1/*.py)
    │
    ▼
Dependency Injection (deps.py: get_current_user, get_db)
    │
    ▼
Service Layer (services/*.py: business logic)
    │
    ▼
Models (models/*.py: ORM)
    │
    ▼
Database (PostgreSQL)
```

## Danh sách Routers

### Auth & User Management

| File | Prefix | Auth | Mô tả |
|------|--------|------|--------|
| `auth.py` | `/api/v1/auth` | Partial | Đăng ký, đăng nhập, refresh token, thông tin user hiện tại |
| `user_profiles.py` | `/api/v1/user-profiles` | Required | CRUD hồ sơ thể chất (chiều cao, cân nặng, mỡ, vòng đo, mức vận động, chế độ ăn) |

### Nutrition & Food

| File | Prefix | Auth | Mô tả |
|------|--------|------|--------|
| `nutrition_goals.py` | `/api/v1/nutrition-goals` | Required | Tính BMR/TDEE/BMI, tạo & cập nhật mục tiêu dinh dưỡng |
| `food_nutrition.py` | `/api/v1/food-nutrition` | Required | Tra cứu, tìm kiếm, CRUD thực phẩm trong database |
| `meal_logs.py` | `/api/v1/meal-logs` | Required | CRUD meal logs (bữa ăn), xem lịch sử theo ngày |
| `dashboard.py` | `/api/v1/dashboard` | Required | Thống kê dinh dưỡng ngày/tuần (tổng calo, macro, % hoàn thành mục tiêu) |

### Fitness & Progress

| File | Prefix | Auth | Mô tả |
|------|--------|------|--------|
| `workout_plans.py` | `/api/v1/workout-plans` | Required | CRUD kế hoạch tập luyện (1 active plan mỗi user), quản lý bài tập |
| `progress_logs.py` | `/api/v1/progress-logs` | Required | Nhật ký theo dõi cân nặng và số đo cơ thể theo ngày |

### AI Features

| File | Prefix | Auth | Mô tả |
|------|--------|------|--------|
| `ai_meal_update.py` | `/api/v1/ai/meal-update` | Required | Nhận diện món ăn từ ảnh (Gemini Vision), xác nhận & lưu meal |
| `ai_daily_planner.py` | `/api/v1/ai/daily-planner` | Required | AI sinh gợi ý lịch trình ăn uống + tập luyện cho ngày mới |
| `ai_chatbot.py` | `/api/v1/ai/chat` | Required | Chatbot AI: tạo session, gửi nhận tin nhắn, streaming response |

### System

| File | Prefix | Auth | Mô tả |
|------|--------|------|--------|
| `uploads.py` | `/api/v1/uploads` | Required | Upload ảnh (avatar/meal/temporary/progress), xem danh sách, xóa |
| `health.py` | `/` hoặc `/health` | Public | Health check endpoint (không cần auth) |

## Cách đọc một Router file

1. Đọc imports và decorator `@router.post/get/put/delete`
2. Đọc function signature: `current_user`, path params, query params, body params
3. Đọc response model (Pydantic schema)
4. Đọc service layer bên dưới (trong `services/`)

```python
@router.post("/meal-logs", response_model=MealLogResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_meal(
    payload: MealLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ghi nhận một bữa ăn mới."""
    meal = await create_meal_log_with_items(db, payload, current_user.id)
    return meal
```

## Authentication Flow

1. Client gửi request kèm `Authorization: Bearer <JWT_token>`
2. `oauth2_scheme` (FastAPI Security) trích xuất token từ header
3. `deps.get_current_user()` decode JWT, lấy `user_id` từ payload
4. Query database để lấy `User` object
5. Trả về user cho endpoint, hoặc raise `401 Unauthorized` / `403 Forbidden`

## Rate Limiting

Một số endpoint có rate limit:

| Endpoint | Limit | Áp dụng |
|----------|-------|----------|
| `POST /ai/meal-update/preview` | 10/min | Mỗi IP |
| `POST /ai/meal-update/recognize-image` | 10/min | Mỗi IP |
| `POST /ai/chat/sessions/{id}/messages` | 20/min | Mỗi IP |
| `POST /ai/chat/sessions/{id}/messages/stream` | 20/min | Mỗi IP |

Khi vượt rate limit → trả về `429 Too Many Requests`.

## API Documentation

Khi server đang chạy:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Error Handling

Tất cả endpoints trả về error response theo format chuẩn FastAPI:

```json
{
  "detail": "Mô tả lỗi cụ thể"
}
```

Với validation error (422):

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "meal_type"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

## Best Practices

- Luôn đặt `response_model` để Pydantic tự động serialize
- Đặt `status_code` rõ ràng (201 cho create, 204 cho delete không có body)
- Validate business rules trong service layer, không trong route
- Raise HTTPException với mã lỗi chính xác (400, 401, 403, 404, 422, 500, 503)
