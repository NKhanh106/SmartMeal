# Thư mục api/v1/ - API Endpoints

## Mục đích

Chứa **tất cả các API endpoints** của ứng dụng SmartMeal. Đây là nơi định nghĩa các route HTTP (GET, POST, PUT, DELETE) mà frontend sẽ gọi để tương tác với backend.

## Tại sao có v1/?

Việc sử dụng version prefix `/api/v1/` giúp:
- **Tương thích ngược**: Khi API thay đổi lớn, có thể giữ v1 và tạo v2 mới
- **Dễ dàng deprecate**: Đánh dấu phiên bản cũ để migrate
- **API versioning**: Quản lý nhiều phiên bản API song song

## Các file endpoints

### Authentication
- **auth.py** - Đăng ký tài khoản, đăng nhập, refresh token, logout

### User Management
- **user_profiles.py** - CRUD thông tin cá nhân người dùng (age, gender, height, weight, activity_level...)

### Nutrition
- **food_nutrition.py** - Tra cứu thông tin dinh dưỡng thực phẩm
- **meal_logs.py** - Ghi nhật ký bữa ăn (breakfast, lunch, dinner, snacks)
- **nutrition_goals.py** - Thiết lập mục tiêu dinh dưỡng hàng ngày (calories, protein, carbs, fat)

### Fitness
- **workout_plans.py** - Quản lý kế hoạch tập luyện
- **workout_sessions.py** - Ghi nhận buổi tập cụ thể

### Progress Tracking
- **progress_logs.py** - Theo dõi cân nặng, số đo, tiến độ theo thời gian

### Dashboard & Analytics
- **dashboard.py** - Dữ liệu tổng quan, thống kê, biểu đồ

### AI Features
- **ai_recommendations.py** - Đề xuất thực phẩm, bữa ăn thông minh
- **ai_meal_update.py** - AI phân tích và cập nhật bữa ăn
- **ai_chatbot.py** - Chatbot trả lời câu hỏi dinh dưỡng
- **ai_meal_plan.py** - AI tạo kế hoạch ăn uống cá nhân hóa

## Cấu trúc Endpoint

Mỗi endpoint thường có cấu trúc:

```python
@router.post("/endpoint", response_model=ResponseSchema)
async def create_item(
    item: RequestSchema,        # Pydantic schema validation
    db: Session = Depends(get_db),  # Database session
    current_user: User = Depends(get_current_user)  # Auth
):
    # Gọi service layer
    result = service.create_item(item, current_user.id)
    return result
```

## Authentication

Tất cả endpoints (trừ auth) đều yêu cầu JWT token:
- Header: `Authorization: Bearer <token>`
- Token chứa user_id và role
- Middleware `get_current_user` xác thực và inject user vào request

## Response Format

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful"
}
```

## HTTP Status Codes

| Code | Ý nghĩa |
|------|---------|
| 200 | Thành công |
| 201 | Đã tạo mới |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (chưa đăng nhập) |
| 403 | Forbidden (không có quyền) |
| 404 | Not Found |
| 500 | Internal Server Error |
