# SmartMeal API — Backend Server

## Mục đích

Đây là **backend server** của ứng dụng SmartMeal — một hệ thống web đa ngôn ngữ (Tiếng Việt + English) hỗ trợ quản lý dinh dưỡng, theo dõi tiến trình thể chất và tập luyện với sự trợ giúp của AI. Backend được xây dựng bằng **FastAPI** (Python 3.12+) kết hợp **PostgreSQL**, hỗ trợ async toàn bộ.

## Tính năng cốt lõi

| Tính năng | Mô tả |
|------------|--------|
| **Auth** | Đăng ký / Đăng nhập / JWT access + refresh token, bcrypt password hashing |
| **User Profile** | Hồ sơ thể chất (chiều cao, cân nặng, % mỡ, vòng đo, mức vận động, chế độ ăn, dị ứng) |
| **Nutrition Goals** | Tính BMR / TDEE / BMI theo công thức Mifflin-St Jeor, đặt mục tiêu calo/macro |
| **Meal Logs** | Ghi nhận bữa ăn kèm chi tiết món ăn, tính calo/macro |
| **Food Nutrition DB** | Cơ sở dữ liệu thực phẩm Việt Nam + USDA, tìm kiếm, CRUD |
| **Dashboard** | Thống kê calo/macro theo ngày và tuần, timezone-aware |
| **Progress Logs** | Nhật ký theo dõi cân nặng, % mỡ, số đo cơ thể, ảnh tiến bộ |
| **Workout Plans** | Kế hoạch tập luyện (1 active plan/user), quản lý bài tập |
| **AI Meal Update** | Nhận diện món ăn từ ảnh (Gemini Vision) → tự động ghi nhận bữa ăn |
| **AI Daily Planner** | Sinh gợi ý lịch trình ăn uống + tập luyện cho ngày mới (Groq/Gemini) |
| **AI Chatbot** | Trợ lý AI tương tác theo ngữ cảnh (profile, goals, meal history, insights) |
| **Image Upload** | Upload ảnh với metadata, tự động dọn dẹp theo TTL |

## Công nghệ sử dụng

| Category | Công nghệ | Giải thích |
|----------|-----------|------------|
| **Framework** | FastAPI | Web framework async, auto-generated OpenAPI docs, type-safe |
| **Language** | Python 3.12+ | Hỗ trợ async/await toàn bộ |
| **Database** | PostgreSQL 15+ | Cơ sở dữ liệu quan hệ mạnh mẽ |
| **ORM** | SQLAlchemy 2.0 (async) | Async ORM với SQLAlchemy 2.0 style (Mapped, mapped_column) |
| **Migrations** | Alembic | Quản lý phiên bản database schema |
| **Validation** | Pydantic v2 | Xác thực dữ liệu và serialization |
| **Auth** | JWT (python-jose) + Bcrypt (passlib) | Xác thực và băm mật khẩu |
| **AI** | Google Gemini + Groq | Nhận diện ảnh, sinh text, chatbot |
| **Cache** | Redis (redis-py async) | Cache kết quả AI, tránh gọi trùng |
| **Rate Limit** | slowapi | Giới hạn request trên mỗi IP |
| **Scheduler** | APScheduler | Chạy job dọn dẹp ảnh định kỳ |
| **Testing** | pytest + pytest-asyncio | Unit tests async |
| **Linting** | ruff | Fast Python linter |
| **Container** | Docker | Triển khai containerized |

## Cấu trúc thư mục

```
apps/api/
├── app/                         # Toàn bộ source code
│   ├── main.py                 # Entry point, CORS, router registration, lifespan
│   ├── api/                    # API Routers (endpoints)
│   │   ├── deps.py            # Auth dependencies: get_current_user, ensure_user_access
│   │   └── v1/               # v1 Endpoints (auth, profiles, meals, AI,...)
│   ├── models/                 # SQLAlchemy ORM Models (16 bảng)
│   ├── schemas/                # Pydantic Schemas (validation & serialization)
│   ├── services/               # Business Logic Layer
│   ├── ai/                     # AI Provider Abstraction (Factory pattern)
│   │   ├── base.py            # Abstract AIProvider interface
│   │   ├── factory.py         # Factory: chọn provider theo config
│   │   └── providers/          # Implementations: Gemini, Groq
│   ├── chatbot/               # AI Chatbot System
│   │   ├── service.py         # Core chatbot logic
│   │   ├── context_builder.py # Xây dựng context từ user data
│   │   ├── context_policy.py  # Quy tắc truy cập dữ liệu
│   │   ├── prompts.py         # System prompts
│   │   └── utils.py           # Helper functions
│   ├── core/                   # Configuration & Security
│   │   ├── config.py          # Pydantic Settings (tất cả env vars)
│   │   ├── security.py        # JWT helpers, password hashing
│   │   ├── cache.py           # Redis cache wrapper
│   │   └── rate_limiter.py    # Rate limiter setup
│   └── db/                     # Database Connection
│       └── session.py          # Async engine, session factory, Base
├── alembic/                    # Database migrations
│   ├── env.py                 # Migration environment
│   └── versions/              # Migration scripts (4 migrations)
├── scripts/                    # Utility scripts
│   ├── seed_food_data.py     # Seed ~65 món ăn Việt Nam
│   ├── seed_demo_data.py     # Seed 10 user với 10 ngày dữ liệu
│   └── cleanup_expired_images.py # Cleanup script
├── tests/                     # Unit tests (pytest)
├── Dockerfile                 # Docker container (Python 3.12-slim)
├── Makefile                  # Dev commands
├── requirements.txt           # Python dependencies (redis, hiredis)
├── pyproject.toml            # Python project config (pytest, ruff)
├── alembic.ini              # Alembic configuration
└── .env.example             # Environment variables template
```

## Cách chạy

### Yêu cầu hệ thống

- Python >= 3.12
- PostgreSQL >= 15
- Redis (optional, app chạy degraded mode nếu không có)
- Docker (optional)

### Cài đặt & Khởi chạy

```bash
# 1. Cài dependencies
cd apps/api
pip install -r requirements.txt

# 2. Tạo file .env từ template
cp .env.example .env
# Chỉnh sửa .env: điền DATABASE_URL, SECRET_KEY, GEMINI_API_KEY, GROQ_API_KEY

# 3. Chạy database migrations
alembic upgrade head

# 4. Seed dữ liệu thực phẩm (tùy chọn, không chạy trong production)
make seed  # hoặc: python scripts/seed_food_data.py

# 5. Chạy development server
make dev   # hoặc: uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker build -t smartmeal-api apps/api/
docker run -p 8000:8000 --env-file apps/api/.env smartmeal-api
```

### Lệnh Makefile

```bash
make install   # Cài dependencies
make dev       # Chạy dev server với hot-reload
make migrate   # Chạy Alembic migrations
make seed      # Seed food data (development only)
make test      # Chạy pytest
make lint      # Chạy ruff linter
```

## API Documentation

Khi server đang chạy:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

## Database Schema (16 bảng)

```
users                          -- Tài khoản người dùng (soft delete)
user_profiles                  -- Hồ sơ thể chất (1:1 với users)
nutrition_goals                -- Mục tiêu dinh dưỡng (1 active/user)
food_nutrition                 -- Cơ sở dữ liệu thực phẩm
meal_logs                      -- Nhật ký bữa ăn
meal_items                     -- Chi tiết món trong bữa ăn
ai_analysis_logs               -- Log gọi AI API
daily_recommendations          -- Kết quả AI Daily Planner
progress_logs                  -- Nhật ký theo dõi thể chất
workout_plans                  -- Kế hoạch tập luyện (1 active/user)
workout_items                  -- Bài tập trong kế hoạch
chat_sessions                  -- Phiên chat với AI Coach
chat_messages                  -- Tin nhắn trong phiên chat
uploaded_images                -- Metadata ảnh upload
conversation_insights          -- Insights trích xuất từ cuộc trò chuyện
```

## Environment Variables (.env.example)

```env
ENVIRONMENT=development
SECRET_KEY=change-me-use-a-long-random-string

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/smartmeal

# AI Providers
AI_MEAL_PROVIDER=gemini
AI_CHAT_PROVIDER=groq
AI_PLANNER_PROVIDER=groq
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=
GROQ_TEXT_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

# Redis
REDIS_URL=redis://localhost:6379/0
```

## Image Storage System

```
DB: uploaded_images (metadata only)
Disk: uploads/{user_id}/{image_type}/{image_id}.{ext}
URL:  /uploads/{user_id}/{image_type}/{image_id}.{ext}
```

| Type | TTL | Auto-delete |
|------|-----|-------------|
| `avatar` | Never | No |
| `meal` | 7 days | Yes |
| `temporary` | 1 day | Yes |
| `progress` | Never | No |

## Testing

```bash
# Chạy tất cả tests
make test

# Test cụ thể
pytest tests/test_meal_service.py -v
```

## Bảo mật

- Mật khẩu được hash bằng **bcrypt**
- JWT tokens (HS256) cho xác thực API
- Role-based access control: `user`, `admin`
- Production validator: từ chối chạy nếu SECRET_KEY yếu
- Rate limiting trên các endpoint AI
- Soft delete cho User (không hard delete)
