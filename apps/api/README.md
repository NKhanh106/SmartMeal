# ⚙️ SmartMeal Backend — FastAPI

## Tổng quan

Backend của SmartMeal được viết bằng **FastAPI** với database **PostgreSQL** (SQLAlchemy 2.0 async) và migrations qua **Alembic**. Hệ thống tuân theo **Layered Architecture** (API → Service → Data), với AI layer tách biệt hoàn toàn khỏi business logic.

---

## Cấu trúc thư mục

```
apps/api/
├── app/
│   ├── main.py                  # FastAPI entry point, CORS, router mount
│   ├── dependencies.py          # Shared FastAPI dependencies
│   │
│   ├── api/                     # ── Layer 1: API Routes ──
│   │   └── v1/
│   │       ├── router.py        # Gộp tất cả sub-routers vào prefix /api/v1
│   │       ├── deps.py          # Auth dependencies (get_current_user, ensure_user_access)
│   │       ├── auth.py          # /auth — register, login, me
│   │       ├── user_profiles.py # /user-profiles
│   │       ├── nutrition_goals.py # /nutrition-goals
│   │       ├── food_nutrition.py # /food-nutrition
│   │       ├── meal_logs.py     # /meal-logs
│   │       ├── dashboard.py     # /dashboard
│   │       ├── progress_logs.py # /progress-logs
│   │       ├── workout_plans.py # /workout-plans
│   │       ├── ai_chatbot.py    # /ai/chat
│   │       ├── ai_daily_planner.py # /ai/daily-planner
│   │       └── ai_meal_update.py # /ai/meal-update
│   │
│   ├── services/                 # ── Layer 2: Business Logic ──
│   │   ├── auth_service.py      # (inline trong auth.py)
│   │   ├── meal_service.py       # Tạo meal + meal_items, cascade
│   │   ├── nutrition_service.py  # Tính BMR/TDEE/BMI (Mifflin-St Jeor)
│   │   ├── dashboard_service.py # Tổng hợp calo/macro ngày & tuần
│   │   ├── progress_log_service.py # Upsert progress log
│   │   ├── workout_service.py   # CRUD workout plan & items
│   │   ├── food_nutrition_service.py # Ước lượng dinh dưỡng theo cân nặng
│   │   ├── ai_log_service.py    # Ghi AI call logs
│   │   ├── ai_meal_update_service.py # Gọi AI nhận diện ảnh, map kết quả
│   │   └── daily_recommendation_service.py # Sinh gợi ý ngày mới
│   │
│   ├── chatbot/                 # ── AI Chatbot Module ──
│   │   ├── service.py           # Luồng: tạo session → lưu tin nhắn → gọi AI → log
│   │   ├── context_builder.py  # Trích xuất context từ DB (profile, goals, meals...)
│   │   ├── context_policy.py    # Giới hạn số lượng message/meal đưa vào context
│   │   ├── prompts.py           # System prompt định nghĩa vai trò AI Coach
│   │   └── utils.py            # Tiện ích (auto-title từ tin nhắn đầu)
│   │
│   ├── ai/                      # ── AI Provider Abstraction ──
│   │   ├── base.py             # Abstract class AIProvider (generate_text, generate_json, analyze_image_json)
│   │   ├── factory.py          # Factory: chọn provider theo env, có caching
│   │   ├── providers/
│   │   │   ├── gemini_provider.py # Implement Gemini SDK
│   │   │   └── groq_provider.py  # Implement Groq SDK
│   │   └── prompts/
│   │       └── daily_planner_prompt.py # Prompt template cho daily planner
│   │
│   ├── models/                  # ── Layer 3: Data Access (SQLAlchemy 2.0) ──
│   │   ├── enums.py            # PostgreSQL ENUM types (Gender, ActivityLevel, MealType...)
│   │   ├── user.py             # Bảng users
│   │   ├── user_profile.py     # Bảng user_profiles
│   │   ├── nutrition_goal.py   # Bảng nutrition_goals
│   │   ├── food_nutrition.py   # Bảng food_nutrition
│   │   ├── meal.py             # Bảng meals (meal_logs) + meal_items
│   │   ├── progress_log.py     # Bảng progress_logs
│   │   ├── workout_plan.py     # Bảng workout_plans + workout_items
│   │   ├── ai_log.py          # Bảng ai_analysis_logs
│   │   ├── daily_recommendation.py # Bảng daily_recommendations
│   │   └── chat.py            # Bảng chat_sessions + chat_messages
│   │
│   ├── schemas/                 # ── Pydantic Schemas ──
│   │   ├── user.py             # UserCreate, UserResponse
│   │   ├── user_profile.py     # UserProfileCreate/Update/Response
│   │   ├── nutrition_goal.py   # NutritionGoalCreate/Calculate/Response
│   │   ├── food_nutrition.py   # FoodNutritionCreate/Update/Response
│   │   ├── meal.py             # MealLogCreate/Response, MealItemCreate
│   │   ├── meal_update.py      # AIMealUpdateOutput, MealUpdatePreview, Confirm
│   │   ├── dashboard.py        # DailyDashboardResponse, WeeklyDashboardResponse
│   │   ├── progress_log.py     # ProgressLogCreate/Update/Response
│   │   ├── workout.py          # WorkoutPlanCreate, WorkoutItemCreate/Update
│   │   ├── chat.py             # ChatSessionCreate/Response, ChatMessageCreate/Response
│   │   ├── daily_recommendation.py # DailyRecommendationResponse
│   │   ├── token.py            # Token, TokenData
│   │   └── ai_log.py          # AiLogCreate
│   │
│   ├── core/                    # ── Core Infrastructure ──
│   │   ├── config.py           # Pydantic Settings — load & validate all env vars
│   │   └── security.py         # bcrypt hashing, JWT create/verify
│   │
│   └── db/                      # ── Database Setup ──
│       └── session.py          # AsyncEngine + AsyncSession factory
│
├── alembic/                      # Database migrations
│   ├── versions/
│   │   ├── 20260427_0001_initial_core_schema.py # Bảng core đầu tiên
│   │   └── 20260429_0002_add_progress_workout_tables.py # Progress + Workout tables
│   ├── env.py
│   ├── alembic.ini
│   └── script.py.mako
│
├── tests/                        # Pytest tests
│   ├── conftest.py              # Fixtures (db session, test client)
│   ├── test_auth.py
│   ├── test_profile.py
│   ├── test_nutrition.py
│   ├── test_validation_and_meals.py
│   └── test_food_permissions.py
│
├── Makefile                      # Lệnh: install, dev, migrate, test, lint
├── requirements.txt              # Python dependencies
├── .env.example                  # Template biến môi trường
└── Dockerfile
```

---

## Layered Architecture

```
 Request
   ↓
┌─────────────────────┐
│  API Router         │  Nhận request, validate nhanh, gọi service
│  (app/api/v1/*.py)  │  Không chứa logic nghiệp vụ
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Service Layer      │  Xử lý nghiệp vụ, gọi DB/SQLAlchemy,
│  (app/services/*)   │  gọi AI, trả về domain objects
└──────────┬──────────┘
           ↓
┌─────────────────────┐
│  Model / Schema     │  SQLAlchemy Models ↔ Pydantic Schemas
│  (app/models/*)     │  Định nghĩa cấu trúc dữ liệu
│  (app/schemas/*)    │
└─────────────────────┘
```

---

## Environment Variables

Sao chép `.env.example` → `.env`:

| Biến | Mô tả | Bắt buộc |
|-------|--------|-----------|
| `ENVIRONMENT` | `development` / `production` | ✅ |
| `SECRET_KEY` | Secret key cho JWT (dài, ngẫu nhiên) | ✅ |
| `POSTGRES_USER` | PostgreSQL username | ✅ |
| `POSTGRES_PASSWORD` | PostgreSQL password | ✅ |
| `POSTGRES_HOST` | PostgreSQL host | ✅ |
| `POSTGRES_PORT` | PostgreSQL port | ✅ |
| `POSTGRES_DB` | Database name | ✅ |
| `DATABASE_URL` | Full connection string (`postgresql://...`) | ✅ |
| `BACKEND_CORS_ORIGINS` | JSON array origins (VD: `["http://localhost:3000"]`) | ✅ |
| `AI_CHAT_PROVIDER` | `gemini` hoặc `groq` | ✅ |
| `AI_PLANNER_PROVIDER` | `gemini` hoặc `groq` | ✅ |
| `AI_MEAL_PROVIDER` | `gemini` hoặc `groq` | ✅ |
| `GEMINI_API_KEY` | Google Gemini API key | ✅ (nếu dùng Gemini) |
| `GEMINI_MODEL` | Tên model Gemini (mặc định: `gemini-2.5-flash`) | ✅ |
| `GROQ_API_KEY` | Groq API key | ✅ (nếu dùng Groq) |
| `GROQ_TEXT_MODEL` | Model text Groq (mặc định: `llama-3.3-70b-versatile`) | ✅ |
| `GROQ_VISION_MODEL` | Model vision Groq | ✅ |
| `USDA_API_KEY` | USDA FoodData Central API key (tùy chọn) | ❌ |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Thời gian hết hạn JWT (mặc định: 30 phút) | ❌ |

---

## Các lệnh Makefile

```bash
cd apps/api

make install     # pip install -r requirements.txt
make dev         # uvicorn app.main:app --reload
make migrate     # alembic upgrade head
make test        # pytest
make lint        # ruff check app tests
```

---

## Database Migrations

```bash
# Tạo migration mới
alembic revision --autogenerate -m "description"

# Chạy migration lên head
alembic upgrade head

# Rollback 1 migration
alembic downgrade -1

# Xem lịch sử migration
alembic history
```

---

## API Prefix & Versioning

Tất cả endpoints đều có prefix `/api/v1`. Cấu trúc URL:

```
/api/v1/auth/register
/api/v1/auth/login
/api/v1/user-profiles
/api/v1/nutrition-goals
/api/v1/nutrition-goals/calculate
/api/v1/nutrition-goals/active
/api/v1/food-nutrition
/api/v1/food-nutrition/search
/api/v1/food-nutrition/{food_id}
/api/v1/meal-logs
/api/v1/meal-logs/{meal_id}
/api/v1/dashboard/today
/api/v1/dashboard/weekly
/api/v1/progress-logs
/api/v1/workout-plans
/api/v1/ai/meal-update/preview
/api/v1/ai/meal-update/confirm
/api/v1/ai/daily-planner/generate
/api/v1/ai/daily-planner/date/{date}
/api/v1/ai/chat/sessions
/api/v1/ai/chat/sessions/{session_id}/messages
```

---

## Authentication & Authorization

- **JWT Bearer Token** — access token trong header `Authorization: Bearer <token>`
- **bcrypt** — password hashing (passlib)
- **`get_current_user`** (deps.py) — lấy user từ token, dùng làm `Depends()` trong route
- **`ensure_user_access`** (deps.py) — kiểm tra user hiện tại có quyền truy cập data của user_id khác (admin bypass)
- **Login rate limiting** — theo dõi số lần thử đăng nhập, khóa tài khoản tạm thời

---

## AI Integration

### Provider Abstraction

```python
# app/ai/base.py
class AIProvider(ABC):
    async def generate_text(self, prompt: str, ...) -> str: ...
    async def generate_json(self, prompt: str, response_schema: type, ...) -> Any: ...
    async def analyze_image_json(self, image_bytes: bytes, prompt: str, ...) -> Any: ...
```

### Factory (chọn provider theo env)

```python
# app/ai/factory.py
provider = get_ai_provider("chat")  # → Groq hoặc Gemini
provider = get_ai_provider("meal")   # → Gemini hoặc Groq
```

### Synchronous AI calls in async context

Gemini/Groq SDK là sync. Để tránh block event loop, dùng `run_in_threadpool`:

```python
from fastapi.concurrency import run_in_threadpool
result = await run_in_threadpool(provider.generate_json, ...)
```

---

## Key Business Logic

### Nutrition Calculation (Mifflin-St Jeor)

```
BMR (nam) = (10 × cân nặng_kg) + (6.25 × chiều cao_cm) − (5 × tuổi) + 5
BMR (nữ) = (10 × cân nặng_kg) + (6.25 × chiều cao_cm) − (5 × tuổi) − 161
TDEE = BMR × ActivityMultiplier
Daily Calorie Target = TDEE × GoalModifier
```

### Meal Logging

1. Tạo `Meal` record với `meal_time`, `meal_type`
2. Batch-insert `MealItem` records (cascade nếu meal bị xóa)
3. Mỗi item ghi rõ `food_nutrition_id`, cân nặng, và `source` (`ai_nhan_dien` / `nhap_thu_cong`)

### Workout Plan Constraint

- Chỉ **1 active plan** per user tại mỗi thời điểm
- Khi tạo plan mới → deactivate plan cũ

### AI Meal Update Flow

```
1. POST /ai/meal-update/preview
   → Validate ảnh (JPEG/PNG/WEBP, max ~10MB)
   → Gọi AI Vision (Gemini) → JSON {items[], overall_confidence}
   → Map food_name → food_nutrition_id (fuzzy match)
   → Trả về MealUpdatePreviewResponse

2. POST /ai/meal-update/confirm
   → Validate preview data
   → Tạo MealLog + MealItems (source='ai_nhan_dien')
   → Ghi AI log (latency, raw_response, status)
   → Trả về meal_log_id
```

---

## Testing

```bash
make test
# 18 passed, 12 skipped

# Chạy file cụ thể
pytest tests/test_auth.py -v
```

Test coverage chính:
- Auth: đăng ký, đăng nhập, JWT, login rate limiting
- Profile: CRUD, validation ngày sinh
- Nutrition: tính BMR/TDEE, đặt goal
- Meals: tạo meal + items, validation
- Food Nutrition: phân quyền admin vs user
