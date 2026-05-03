# `api/v1/` — API v1 Routers

Thư mục chứa tất cả các router (endpoint groups) của FastAPI backend.

## Tổng quan

Mỗi file Python tương ứng với một nhóm endpoint riêng biệt. Tất cả đều có prefix `/api/v1`.

## Các router

| File | Prefix | Mô tả |
|------|--------|--------|
| `auth.py` | `/api/v1/auth` | Đăng ký, đăng nhập, lấy thông tin user hiện tại |
| `user_profiles.py` | `/api/v1/user-profiles` | CRUD hồ sơ sức khỏe (chiều cao, cân nặng, mỡ, v.v.) |
| `nutrition_goals.py` | `/api/v1/nutrition-goals` | Tính BMR/TDEE/BMI, tạo/mặc định mục tiêu dinh dưỡng |
| `food_nutrition.py` | `/api/v1/food-nutrition` | Tra cứu database thực phẩm (USDA) |
| `meal_logs.py` | `/api/v1/meal-logs` | Ghi nhật ký bữa ăn, CRUD meal entries |
| `dashboard.py` | `/api/v1/dashboard` | Thống kê dinh dưỡng ngày/tuần |
| `progress_logs.py` | `/api/v1/progress-logs` | Theo dõi cân nặng/đo body theo thời gian |
| `workout_plans.py` | `/api/v1/workout-plans` | Tạo, quản lý kế hoạch tập luyện |
| `ai_daily_planner.py` | `/api/v1/ai/daily-planner` | Gợi ý bữa ăn + workout hàng ngày bằng AI |
| `ai_chatbot.py` | `/api/v1/ai/chat` | Chatbot AI hỗ trợ dinh dưỡng |
| `ai_meal_update.py` | `/api/v1/ai/meal-update` | Nhận diện đồ ăn qua ảnh bằng AI (Gemini Vision) |

## Auth

- **Public endpoints**: `/auth/login`, `/auth/register`
- **Protected endpoints**: Tất cả còn lại — yêu cầu JWT token trong `Authorization: Bearer <token>`

## Router chính (main.py)

```python
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(user_profiles.router, prefix=settings.API_V1_STR)
app.include_router(nutrition_goals.router, prefix=settings.API_V1_STR)
app.include_router(food_nutrition.router, prefix=settings.API_V1_STR)
app.include_router(meal_logs.router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(progress_logs.router, prefix=settings.API_V1_STR)
app.include_router(workout_plans.router, prefix=settings.API_V1_STR)
app.include_router(ai_daily_planner.router, prefix=settings.API_V1_STR)
app.include_router(ai_chatbot.router, prefix=settings.API_V1_STR)
app.include_router(ai_meal_update.router, prefix=settings.API_V1_STR)
```

## Cách đọc một router file

1. Đọc imports và decorator `@router.get/post/...`
2. Đọc function signature — có `current_user`, path params, query params
3. Đọc response model (Pydantic schema)
4. Đọc service layer bên dưới (trong `services/`)
