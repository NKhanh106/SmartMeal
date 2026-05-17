# Thư mục `schemas/` — Pydantic Schemas (Validation & Serialization)

## Mục đích

Chứa toàn bộ **Pydantic schemas** dùng để:
1. **Validate** dữ liệu request từ client
2. **Serialize** response trả về cho client
3. **Tự động sinh** OpenAPI documentation (Swagger/ReDoc)

Đây là lớp trung gian giữa HTTP layer và database/service layer.

## Tại sao cần Schemas?

- **Validation tự động**: Pydantic kiểm tra type, required fields, range, format mà không cần viết code thủ công
- **Serialization**: Tự động chuyển SQLAlchemy model → JSON response nhờ `from_attributes = True`
- **Documentation**: Swagger UI tự động hiển thị schema, examples, validation errors
- **Security**: Ngăn chặn dữ liệu độc hại vào hệ thống ngay từ lớp HTTP

## Danh sách Schemas

### User & Auth Schemas

| Schema | File | Mô tả |
|--------|------|--------|
| `Token`, `TokenPayload` | `user.py` / `token.py` | JWT access & refresh token structures |
| `UserCreate`, `UserResponse` | `user.py` | Đăng ký / phản hồi thông tin user |
| `UserProfileCreate`, `UserProfileResponse` | `user_profile.py` | Tạo & phản hồi hồ sơ thể chất |

### Nutrition Schemas

| Schema | File | Mô tả |
|--------|------|--------|
| `FoodNutritionResponse` | `food_nutrition.py` | Thông tin dinh dưỡng thực phẩm |
| `NutritionGoalCreate`, `NutritionGoalResponse` | `nutrition_goal.py` | Tạo & phản hồi mục tiêu dinh dưỡng |
| `MealLogCreate`, `MealLogResponse`, `MealLogUpdate` | `meal.py` | CRUD meal logs với nested items |
| `MealItemCreate`, `MealItemResponse` | `meal.py` | Item trong bữa ăn |
| `MealUpdatePreviewItem`, `MealUpdatePreviewResponse` | `meal_update.py` | Preview kết quả AI nhận diện món ăn |
| `MealUpdateConfirmRequest`, `MealUpdateConfirmResponse` | `meal_update.py` | Xác nhận & lưu meal từ AI preview |

### Dashboard & Analytics Schemas

| Schema | File | Mô tả |
|--------|------|--------|
| `DailyDashboardResponse` | `dashboard.py` | Tổng hợp dinh dưỡng ngày (tổng calo, macro, so với mục tiêu, bữa ăn) |
| `WeeklyDashboardResponse` | `dashboard.py` | Thống kê 7 ngày, trend, average, best/worst day |

### Workout Schemas

| Schema | File | Mô tả |
|--------|------|--------|
| `WorkoutPlanCreate`, `WorkoutPlanResponse` | `workout.py` | CRUD kế hoạch tập luyện |
| `WorkoutItemCreate`, `WorkoutItemResponse` | `workout.py` | CRUD bài tập trong plan |

### Chatbot Schemas

| Schema | File | Mô tả |
|--------|------|--------|
| `ChatSessionCreate`, `ChatSessionResponse` | `chat.py` | Tạo & phản hồi phiên chat |
| `ChatMessageCreate`, `ChatMessageResponse` | `chat.py` | Tin nhắn (user/assistant) |
| `ChatSendMessageResponse` | `chat.py` | Phản hồi khi gửi tin nhắn (kèm user_msg + assistant_msg) |

### Progress & Image Schemas

| Schema | File | Mô tả |
|--------|------|--------|
| `ProgressLogCreate`, `ProgressLogResponse` | `progress_log.py` | Nhật ký theo dõi thể chất |
| `UploadedImageResponse`, `UploadedImageListResponse` | `uploaded_image.py` | Metadata ảnh upload (url, type, TTL) |

### AI Response Schemas

| Schema | File | Mô tả |
|--------|------|--------|
| `AIMealUpdateOutput` | `meal_update.py` | Structured JSON output từ AI Vision (items, confidence, notes) |
| `DailyRecommendationResponse` | `daily_recommendation.py` | Gợi ý ngày mới từ AI |

## Ví dụ sử dụng Schema

### Request Schema (Input Validation)

```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class MealLogCreate(BaseModel):
    meal_type: MealTypeEnum
    meal_time: datetime
    items: list[MealItemCreate]
    note: str | None = None

    model_config = {"from_attributes": True}
```

### Response Schema (Output Serialization)

```python
class MealLogResponse(BaseModel):
    id: UUID
    meal_type: MealTypeEnum
    meal_time: datetime
    total_calories: float
    total_protein_g: float
    total_carb_g: float
    total_fat_g: float
    items: list[MealItemResponse]
    image_url: str | None

    model_config = {"from_attributes": True}  # Cho phép tạo từ SQLAlchemy model
```

### Nested Schema (Composition)

```python
class MealLogCreate(BaseModel):
    meal_type: MealTypeEnum
    meal_time: datetime
    items: list[MealItemCreate]  # Nested schema

    model_config = {"from_attributes": True}
```

## Validation nâng cao với Field

```python
from pydantic import Field, field_validator
from uuid import UUID

class MealItemCreate(BaseModel):
    food_nutrition_id: UUID | None = None
    detected_food_name: str = Field(..., min_length=1, max_length=255)
    estimated_weight_g: float = Field(..., gt=0, le=10000)  # > 0, <= 10kg

    @field_validator("detected_food_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
```

## FastAPI Integration

```python
from fastapi import APIRouter, Depends
from app.schemas.meal import MealLogCreate, MealLogResponse

@router.post("/meal-logs", response_model=MealLogResponse, status_code=201)
async def create_meal(
    payload: MealLogCreate,           # ← Validation tự động
    db: AsyncSession = Depends(get_db),
):
    result = await create_meal_log_with_items(db, payload, current_user.id)
    return result                       # ← Serialization tự động
```

## Error Response Format

FastAPI tự động trả về format lỗi chuẩn:

```json
// 422 Validation Error
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

// 400 Bad Request
{
  "detail": "Invalid meal_type. Must be one of: bua_sang, bua_trua..."
}
```

## Best Practices

- Mỗi schema chỉ nên chứa các trường cần thiết cho use case cụ thể (không dump toàn bộ model)
- Dùng `Field()` để mô tả validation rõ ràng trong Swagger
- Tách biệt schema cho input (`*Create`, `*Update`) và output (`*Response`)
- Đặt `model_config = {"from_attributes": True}` cho mọi response schema
