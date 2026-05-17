# Thư mục `models/` — SQLAlchemy ORM Models

## Mục đích

Chứa toàn bộ **SQLAlchemy ORM models** — định nghĩa cấu trúc 16 bảng trong PostgreSQL database dưới dạng các Python class. Mỗi model tương ứng với một bảng, và các mối quan hệ (relationships) giữa các bảng được thiết lập qua đây.

## Tại sao dùng ORM?

- **An toàn**: Tránh SQL injection vì không dùng raw SQL trực tiếp
- **Type-safe**: Nhờ SQLAlchemy 2.0 style với `Mapped[]` và `mapped_column`, IDE có thể type-check
- **Quản lý schema**: Alembic migrations tự động sinh từ các thay đổi ở đây
- **Relationship**: Dễ dàng `.relationship()` để join bảng mà không cần viết SQL

## Danh sách Models

### Models xác thực & người dùng

| Model | File | Mô tả |
|-------|------|--------|
| `User` | `user.py` | Tài khoản người dùng (email, password_hash, role, soft delete) |
| `UserProfile` | `user_profile.py` | Hồ sơ thể chất (chiều cao, cân nặng, % mỡ, mức vận động, chế độ ăn, dị ứng) |

### Models dinh dưỡng

| Model | File | Mô tả |
|-------|------|--------|
| `NutritionGoal` | `nutrition_goal.py` | Mục tiêu dinh dưỡng cá nhân (BMR, TDEE, BMI, macro targets). Có ràng buộc: mỗi user chỉ có 1 active goal |
| `FoodNutrition` | `food_nutrition.py` | Cơ sở dữ liệu thực phẩm (tên, calo, protein, carb, fat, fiber, đường, muối per 100g) |
| `MealLog` | `meal.py` | Nhật ký bữa ăn (user_id, loại bữa ăn, thời gian, tổng macro, ảnh, AI confidence) |
| `MealItem` | `meal.py` | Chi tiết từng món trong bữa ăn (tên món, cân nặng ước lượng, macro, nguồn: AI nhận diện / người dùng xác nhận / nhập tay) |

### Models thể dục

| Model | File | Mô tả |
|-------|------|--------|
| `WorkoutPlan` | `workout_plan.py` | Kế hoạch tập luyện (tên, mục tiêu, độ khó, ngày bắt đầu/kết thúc, trạng thái active) |
| `WorkoutItem` | `workout_item.py` | Bài tập trong kế hoạch (tên bài tập, số set/rep, thời gian, ghi chú) |

### Models theo dõi tiến độ

| Model | File | Mô tả |
|-------|------|--------|
| `ProgressLog` | `progress_log.py` | Nhật ký theo dõi cân nặng và số đo cơ thể theo ngày (weight, body fat, waist, neck, chest, hip, ảnh) |

### Models AI & Chat

| Model | File | Mô tả |
|-------|------|--------|
| `ChatSession` | `chat.py` | Phiên trò chuyện với AI Coach (user_id, title, status: active/deleted) |
| `ChatMessage` | `chat.py` | Tin nhắn trong phiên chat (session_id, role: user/assistant, content, metadata JSON) |
| `AILog` | `ai_log.py` | Log gọi AI API (provider, model, latency, prompt version, raw response, status) |
| `DailyRecommendation` | `daily_recommendation.py` | Kết quả gợi ý ngày mới từ AI (meal plan + workout plan + insights) |

### Models hệ thống

| Model | File | Mô tả |
|-------|------|--------|
| `UploadedImage` | `uploaded_image.py` | Metadata ảnh upload (user_id, loại: avatar/meal/temporary/progress, file_path, TTL, linked_entity) |
| `ConversationInsight` | `conversation_insight.py` | Insights trích xuất từ cuộc trò chuyện (allergies, preferences, health constraints) |

## Enum Types (`enums.py`)

| Enum | Giá trị | Dùng trong |
|------|---------|-----------|
| `GenderType` | nam, nu, khac, khong_muon_noi | UserProfile |
| `ActivityLevelType` | it_van_dong → van_dong_rat_nhieu | UserProfile, TDEE calculation |
| `DietTypeEnum` | binh_thuong, an_chay, thuan_chay, keto, it_tinh_bot, nhieu_dam | UserProfile |
| `NutritionGoalType` | giam_can, giu_can, tang_co | NutritionGoal |
| `MealTypeEnum` | bua_sang, bua_trua, bua_toi, an_vat, khac | MealLog |
| `FoodSourceType` | he_thong, usda, thu_cong, ai_goi_y | FoodNutrition |
| `ItemSourceType` | ai_nhan_dien, nguoi_dung_xac_nhan, nhap_thu_cong | MealItem |
| `WorkoutDifficultyType` | nguoi_moi, trung_binh, nang_cao | WorkoutPlan |

## Ví dụ cấu trúc Model (SQLAlchemy 2.0 Style)

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base

class MealLog(Base):
    __tablename__ = "meal_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    meal_type: Mapped[MealTypeEnum] = mapped_column(
        Enum(MealTypeEnum, name="meal_type_enum", create_type=False),
        nullable=False, default=MealTypeEnum.khac
    )
    total_calories: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    # Relationship 1-N
    items = relationship("MealItem", back_populates="meal_log", cascade="all, delete-orphan")
```

## Mối quan hệ giữa các bảng

```
users (1)───(1) user_profiles
     │
     ├──(N) meal_logs ──(N) meal_items
     ├──(N) nutrition_goals
     ├──(N) progress_logs
     ├──(N) workout_plans ──(N) workout_items
     ├──(N) chat_sessions ──(N) chat_messages
     ├──(N) ai_analysis_logs
     ├──(N) daily_recommendations
     ├──(N) uploaded_images
     └──(N) conversation_insights
```

## Ràng buộc đặc biệt (Constraints)

- **unique constraint**: `user_profiles.user_id` — mỗi user chỉ có 1 profile
- **partial unique index**: `nutrition_goals` — chỉ có 1 active goal mỗi user (`is_active = true`)
- **unique constraint**: `progress_logs(user_id, log_date)` — mỗi user chỉ ghi 1 log mỗi ngày
- **check constraint**: `users.role IN ('user', 'admin')`
- **foreign key constraint**: `meal_logs(nutrition_goal_id, user_id)` → `nutrition_goals(id, user_id)` (composite FK)

## Cách tạo migration khi thay đổi model

```bash
cd apps/api
alembic revision --autogenerate -m "Mô tả thay đổi"
alembic upgrade head
```

## Best Practices

- Luôn dùng `server_default=text("now()")` cho timestamp thay vì Python datetime
- Dùng UUID thay vì auto-increment integer cho primary key (bảo mật hơn)
- Soft delete (xoá mềm) bằng `deleted_at` thay vì hard delete cho User
- Đặt `nullable=False` chỉ khi thực sự bắt buộc
- Thêm index cho các trường thường xuyên query (user_id, created_at, log_date)
