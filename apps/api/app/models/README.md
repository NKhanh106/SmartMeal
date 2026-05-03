# Thư mục models/ - Database ORM Models

## Mục đích

Chứa các **SQLAlchemy ORM models** - định nghĩa cấu trúc các bảng trong PostgreSQL database dưới dạng Python classes. Mỗi model tương ứng với một bảng trong database.

## Tại sao dùng ORM?

- **An toàn**: Tránh SQL injection
- **Tiện lợi**: Làm việc với database qua objects thay vì raw SQL
- **Quản lý**: Dễ dàng migrate và version database schema
- **Relationship**: Dễ dàng thiết lập quan hệ giữa các bảng

## Các Models

### Core Models (Users & Authentication)
| Model | Mô tả |
|-------|-------|
| `User` | Tài khoản người dùng (id, email, password_hash, role, created_at) |
| `UserProfile` | Thông tin cá nhân mở rộng (age, gender, height, weight, activity_level, health_goals) |

### Nutrition Models
| Model | Mô tả |
|-------|-------|
| `FoodNutrition` | Database thực phẩm (name, calories, protein, carbs, fat, fiber, serving_size) |
| `MealLog` | Nhật ký bữa ăn (user_id, date, meal_type, food_items, total_nutrition) |
| `NutritionGoal` | Mục tiêu dinh dưỡng cá nhân (daily_calories, protein_goal, carbs_goal, fat_goal) |

### Fitness Models
| Model | Mô tả |
|-------|-------|
| `WorkoutPlan` | Kế hoạch tập luyện (name, description, duration, exercises, difficulty) |
| `WorkoutSession` | Buổi tập cụ thể (plan_id, user_id, date, duration, calories_burned, notes) |

### Progress Tracking
| Model | Mô tả |
|-------|-------|
| `ProgressLog` | Nhật ký tiến độ (weight, body_measurements, date, notes) |

### AI & Chat
| Model | Mô tả |
|-------|-------|
| `ChatSession` | Phiên trò chuyện (user_id, created_at, title) |
| `ChatMessage` | Tin nhắn trong chat (session_id, role, content, timestamp) |
| `AIUsageLog` | Log sử dụng AI (user_id, endpoint, tokens_used, cost) |
| `DailyRecommendation` | Đề xuất hàng ngày cho user |

## Cấu trúc Model

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    meal_logs = relationship("MealLog", back_populates="user")
    # ... các relationships khác
```

## Relationships

```
User (1) ←→ (1) UserProfile
User (1) ←→ (N) MealLog
User (1) ←→ (N) NutritionGoal
User (1) ←→ (N) WorkoutPlan
User (1) ←→ (N) WorkoutSession
User (1) ←→ (N) ProgressLog
User (1) ←→ (N) ChatSession (1) ←→ (N) ChatMessage
```

## Migrations

Khi thay đổi models, cần chạy Alembic migration:
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Best Practices

- Mỗi model nên có `__repr__` để debug dễ dàng
- Sử dụng UUID thay vì auto-increment integer cho security
- Thiết lập indexes cho các trường thường query (email, user_id, date)
- Sử dụng `default=func.now()` cho timestamps thay vì Python datetime
