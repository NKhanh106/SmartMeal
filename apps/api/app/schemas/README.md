# Thư mục schemas/ - Pydantic Schemas

## Mục đích

Chứa các **Pydantic schemas** - định nghĩa cấu trúc dữ liệu để xác thực (validate) request từ client và serialize response. Đây là lớp trung gian giữa API endpoints và database models.

## Tại sao cần Schemas?

1. **Validation**: Tự động kiểm tra dữ liệu đầu vào (required fields, types, ranges)
2. **Serialization**: Chuyển đổi database models → JSON response
3. **Documentation**: Auto-generated OpenAPI/Swagger docs từ schemas
4. **Security**: Ngăn chặn dữ liệu không hợp lệ vào hệ thống
5. **Separation**: Tách biệt database structure và API contract

## Loại Schemas

### Request Schemas (Input)
Dùng cho POST/PUT requests - định nghĩa dữ liệu client gửi lên:

```python
class CreateMealLogSchema(BaseModel):
    date: date
    meal_type: MealType
    food_items: List[FoodItemSchema]
```

### Response Schemas (Output)
Dùng cho response - định nghĩa dữ liệu trả về cho client:

```python
class MealLogResponse(BaseModel):
    id: UUID
    date: date
    meal_type: MealType
    total_calories: float
    total_protein: float
    # ... fields to include
    
    class Config:
        from_attributes = True  # Cho phép tạo từ ORM model
```

### Config Schemas
Các schema cấu hình hệ thống:
- `pagination.py` - Phân trang
- `filters.py` - Bộ lọc tìm kiếm

## Các file schemas

| File | Mô tả |
|------|-------|
| `user.py` | Schemas cho user registration, login, profile |
| `auth.py` | Login request, token response, refresh token |
| `meal.py` | Meal log schemas (create, update, response) |
| `nutrition.py` | Nutrition goal schemas |
| `food.py` | Food nutrition schemas |
| `workout.py` | Workout plan & session schemas |
| `progress.py` | Progress log schemas |
| `dashboard.py` | Dashboard data schemas |
| `chat.py` | Chat message schemas |
| `recommendation.py` | AI recommendation schemas |
| `common.py` | Shared schemas (Response wrapper, Pagination, Filters) |

## Response Wrapper

Tất cả API responses được wrapper trong format chuẩn:

```python
class ResponseSchema(BaseModel):
    success: bool
    data: Any = None
    message: str = "Operation successful"
    errors: List[str] = []
```

## Validation Examples

```python
from pydantic import Field, validator

class CreateUserSchema(BaseModel):
    email: EmailStr  # Email format validation
    password: str = Field(..., min_length=8)  # Min length
    age: int = Field(..., ge=13, le=120)  # Range validation
    height: float = Field(..., gt=0)  # Must be positive
    
    @validator('password')
    def password_complexity(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase')
        return v
```

## Nested Schemas

Định nghĩa cấu trúc phức tạp:

```python
class FoodItemSchema(BaseModel):
    food_nutrition_id: UUID
    quantity: float = Field(..., gt=0)
    
class MealLogSchema(BaseModel):
    date: date
    meal_type: MealType
    items: List[FoodItemSchema]
    notes: Optional[str] = None
```

## Với Relationships

Sử dụng `from_attributes = True` để serialize SQLAlchemy models:

```python
class UserProfileResponse(BaseModel):
    id: UUID
    age: int
    gender: str
    height: float
    weight: float
    activity_level: str
    
    class Config:
        from_attributes = True
```
