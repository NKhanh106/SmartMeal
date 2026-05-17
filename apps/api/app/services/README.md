# Thư mục `services/` — Business Logic Layer

## Mục đích

Chứa toàn bộ **business logic** của backend SmartMeal, tách biệt khỏi API routes. Mỗi service đóng gói logic nghiệp vụ cho một domain cụ thể. Design pattern này giúp code **dễ test**, **tái sử dụng**, và **bảo trì** hơn.

## Kiến trúc phân lớp

```
API Route (app/api/v1/)
    ↓ (Pydantic Schema Validation)
Service Layer (app/services/)   ← Business Logic ở đây
    ↓
Model Layer (app/models/)       ← ORM entities
    ↓
Database (PostgreSQL)
```

## Danh sách Services

### Nutrition & Meal Services

| Service | File | Mô tả |
|---------|------|--------|
| `meal_service` | `meal_service.py` | Tạo meal log kèm items, cập nhật tổng macro, validate items |
| `nutrition_service` | `nutrition_service.py` | Tính BMR/Mifflin-St Jeor, TDEE, BMI, macro targets theo mục tiêu |
| `food_nutrition_service` | `food_nutrition_service.py` | CRUD thực phẩm, tìm kiếm, USDA integration |
| `food_mapping_service` | `food_mapping_service.py` | Ánh xạ tên món AI nhận diện → food_nutrition DB (fuzzy match, fallback) |

### Dashboard & Progress Services

| Service | File | Mô tả |
|---------|------|--------|
| `dashboard_service` | `dashboard_service.py` | Thống kê calo/macro ngày & tuần, timezone-aware, progress comparison |
| `progress_log_service` | `progress_log_service.py` | CRUD progress logs, tính BMI, weight trend |

### Workout Services

| Service | File | Mô tả |
|---------|------|--------|
| `workout_service` | `workout_service.py` | CRUD workout plans, quản lý active plan (1/user), workout items |

### AI Services

| Service | File | Mô tả |
|---------|------|--------|
| `ai_meal_update_service` | `ai_meal_update_service.py` | Pipeline nhận diện món ăn từ ảnh: AI Vision → food mapping → nutrition calc |
| `daily_recommendation_service` | `daily_recommendation_service.py` | AI sinh gợi ý bữa ăn + kế hoạch tập cho ngày mới |
| `ai_log_service` | `ai_log_service.py` | Ghi log mỗi lần gọi AI (provider, model, latency, prompt, response, status) |
| `conversation_insights_service` | `conversation_insights_service.py` | Trích xuất & lưu insights từ cuộc trò chuyện (allergy, preferences) |
| `learning_service` | `learning_service.py` | Ghi nhận phản hồi người dùng về kết quả AI → cải thiện nhận diện |

### Image Services

| Service | File | Mô tả |
|---------|------|--------|
| `image_storage_service` | `image_storage_service.py` | Upload, lưu metadata, xóa ảnh, link image → entity |
| `image_cleanup_scheduler` | `image_cleanup_scheduler.py` | APScheduler: chạy daily lúc 02:00 UTC, xóa ảnh hết hạn |

### Planner Services

| Service | File | Mô tả |
|---------|------|--------|
| `planner_constraint_engine` | `planner_constraint_engine.py` | Xây dựng constraints (budget calo, allergies, preferences) cho AI daily planner |

## Ví dụ cấu trúc Service

```python
async def create_meal_log_with_items(
    db: AsyncSession,
    payload: MealLogCreate,
    user_id: UUID,
) -> MealLog:
    """Tạo meal log với items, tự động tính tổng macro."""
    meal = MealLog(
        user_id=user_id,
        meal_type=payload.meal_type,
        meal_time=payload.meal_time,
    )
    db.add(meal)
    await db.flush()

    total_cal = 0.0
    for item_payload in payload.items:
        # Business logic: lookup food nutrition, calculate per weight
        item = MealItem(meal_log_id=meal.id, **item_payload.model_dump())
        db.add(item)
        total_cal += item.calories

    meal.total_calories = total_cal
    await db.commit()
    await db.refresh(meal)
    return meal
```

## Dependency Injection trong FastAPI

Services được gọi trực tiếp từ routes, nhận `db: AsyncSession` qua FastAPI dependency injection:

```python
@router.post("/meal-logs")
async def create_meal(
    payload: MealLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await create_meal_log_with_items(db, payload, current_user.id)
```

## Transaction Management

Mỗi service method tự quản lý transaction:

```python
async def service_method(db, ...):
    try:
        db.add(entity)
        await db.flush()
        # ... more operations
        await db.commit()        # thành công → commit
        return result
    except Exception:
        await db.rollback()      # thất bại → rollback
        raise
```

**Lưu ý**: Không bao giờ gọi `commit()` bên trong API route — để service quản lý.

## Cache Invalidation

Khi dữ liệu thay đổi, cần xóa cache tương ứng:

```python
# Khi user confirm meal → xóa daily plan cache
from app.services.daily_recommendation_service import invalidate_user_plan_cache
await invalidate_user_plan_cache(user_id, date.today())
```

## Image Cleanup Scheduler

Scheduler tự động chạy khi backend khởi động (trong `main.py` lifespan):

```python
from app.services.image_cleanup_scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()   # Khởi động APScheduler
    yield
    stop_scheduler()    # Dừng khi shutdown
```

Xóa ảnh theo TTL:
- `meal`: 7 ngày
- `temporary`: 1 ngày
- `avatar`, `progress`: không bao giờ tự xóa

## Testing

```bash
# Test tất cả services
cd apps/api
pytest tests/

# Test cụ thể
pytest tests/test_meal_service.py -v
```

## Best Practices

- Mỗi service method phải là `async` để tận dụng async database driver
- Service không bao giờ raise HTTPException — chỉ return data hoặc raise custom exceptions
- Validate business rules trong service, không chỉ trong schema
- Ghi log cho các operation quan trọng (AI calls, image uploads)
