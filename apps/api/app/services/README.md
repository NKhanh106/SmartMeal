# Thư mục services/ - Business Logic Layer

## Mục đích

Chứa các **service classes** - nơi viết logic nghiệp vụ chính của ứng dụng. Services tách biệt business logic khỏi API routes, giúp code sạch hơn, dễ test hơn, và tái sử dụng được.

## Kiến trúc Layer

```
API Route → Service Layer → Database (Models)
```

**Benefits:**
- **Separation of Concerns**: API routes chỉ xử lý HTTP, services xử lý business logic
- **Reusability**: Nhiều endpoints có thể gọi cùng một service
- **Testability**: Dễ dàng viết unit tests cho services
- **Maintainability**: Thay đổi business logic chỉ cần sửa một chỗ

## Các Services

### meal_service.py
Xử lý nghiệp vụ liên quan đến bữa ăn:
- Tạo/cập nhật/xóa meal logs
- Tính toán tổng dinh dưỡng của bữa ăn
- Validate food items
- Lấy meal history theo ngày/tuần/tháng
- Tính macro nutrients breakdown

### nutrition_service.py
Quản lý dinh dưỡng:
- Tính toán BMR (Basal Metabolic Rate)
- Tính TDEE (Total Daily Energy Expenditure)
- Quản lý nutrition goals
- Tính deficit/surplus calories
- Theo dõi progress so với goals

### workout_service.py
Quản lý bài tập:
- CRUD workout plans
- Ghi nhận workout sessions
- Tính calories burned
- Lấy workout history
- Đề xuất bài tập phù hợp

### dashboard_service.py
Tổng hợp dữ liệu dashboard:
- Thống kê tuần/tháng
- Progress charts data
- Today's summary (calories consumed vs goal)
- Weekly trends
- Streak calculations

### ai_meal_update_service.py
AI phân tích bữa ăn:
- Nhận diện thực phẩm từ mô tả
- Đề xuất portions
- Cập nhật meal log tự động
- Nutrition calculation

## Cấu trúc Service

```python
class MealService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_meal_log(
        self, 
        user_id: UUID, 
        meal_data: CreateMealSchema
    ) -> MealLog:
        # Business logic here
        # Validate
        # Calculate nutrition
        # Save to database
        # Return result
        pass
    
    def get_user_meals(
        self, 
        user_id: UUID, 
        start_date: date, 
        end_date: date
    ) -> List[MealLog]:
        # Query database
        # Transform data
        # Return
        pass
```

## Sử dụng Services

Trong API routes:

```python
from app.services.meal_service import MealService

@router.post("/meals")
async def create_meal(
    meal_data: CreateMealSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    service = MealService(db)
    result = service.create_meal_log(current_user.id, meal_data)
    return result
```

## Dependency Injection

Services được inject vào routes qua FastAPI's `Depends()`:

```python
def get_meal_service(db: Session = Depends(get_db)) -> MealService:
    return MealService(db)

@router.post("/meals")
async def create_meal(
    meal_data: CreateMealSchema,
    service: MealService = Depends(get_meal_service)
):
    return service.create_meal_log(meal_data)
```

## Transaction Management

Services xử lý database transactions:

```python
def create_meal_with_items(self, user_id: UUID, data: MealSchema):
    try:
        # Start transaction
        meal = self.create_meal_log(user_id, data)
        
        for item in data.items:
            self.add_food_item(meal.id, item)
        
        # Commit automatically on success
        return meal
    except Exception:
        # Rollback on error
        self.db.rollback()
        raise
```

## Validation trong Service

```python
def validate_portion(self, food_id: UUID, quantity: float) -> bool:
    MIN_PORTION = 0.1  # 100g
    MAX_PORTION = 5000  # 5kg
    
    if not MIN_PORTION <= quantity <= MAX_PORTION:
        raise ValueError(f"Portion must be between {MIN_PORTION} and {MAX_PORTION}")
    
    return True
```
