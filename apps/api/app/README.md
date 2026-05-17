# Thư mục `app/` — Core Application Logic

## Mục đích

Đây là thư mục chứa toàn bộ **logic nghiệp vụ** của backend SmartMeal. Tất cả code Python liên quan đến API endpoints, database models, schemas, AI providers, và xử lý nghiệp vụ đều nằm trong thư mục này.

## Entry Point — `main.py`

File `main.py` là điểm khởi đầu của ứng dụng FastAPI:

```python
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for SmartMeal nutrition and fitness assistant",
    lifespan=lifespan,
)
```

**Nhiệm vụ của main.py:**
- Khởi tạo FastAPI instance
- Cấu hình CORS middleware
- Đăng ký tất cả API routers với prefix `/api/v1`
- Mount static files cho uploaded images (`/uploads/...`)
- Thiết lập rate limiter và exception handlers
- Lifecycle management: startup → chạy scheduler + warm up Redis, shutdown → cleanup

## Lifecycle (Startup & Shutdown)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()  # APScheduler: cleanup images daily at 02:00 UTC
    await get_redis(); await redis.ping()  # Warm up Redis
    yield
    stop_scheduler()   # Dừng scheduler
    await cache_close()  # Đóng Redis connection
```

## Routing Flow

```
HTTP Request
    │
    ▼
CORS Middleware
    │
    ▼
Rate Limiter Middleware
    │
    ▼
API Router (app/api/v1/*.py)
    │
    ▼
Dependency Injection (get_current_user, get_db)
    │
    ▼
Pydantic Schema Validation (app/schemas/)
    │
    ▼
Service Layer (app/services/)
    │
    ▼
ORM Layer (app/models/) ←→ Database (PostgreSQL)
    │
    ▼
Response Serialization (Pydantic)
    │
    ▼
Client
```

## Cấu trúc

```
app/
├── main.py                  # Entry point — FastAPI app initialization
├── api/                    # HTTP API Routers
│   ├── deps.py            # Auth dependencies (JWT validation, user access)
│   └── v1/              # v1 API Endpoints (13 router files)
├── models/                 # SQLAlchemy ORM Models (16 bảng)
├── schemas/                # Pydantic Schemas (validation & serialization)
├── services/               # Business Logic Layer (14 service files)
├── ai/                     # AI Provider Abstraction Layer
│   ├── base.py            # Abstract AIProvider class
│   ├── factory.py         # Factory: chọn provider theo config
│   ├── orchestrator.py    # AI call orchestration
│   ├── ai_logger.py       # AI call logging decorator
│   ├── circuit_breaker.py # Circuit breaker pattern
│   ├── providers/          # Implementations: Gemini, Groq
│   └── prompts/           # System prompts cho AI use cases
├── chatbot/               # AI Chatbot System
│   ├── service.py         # Core chatbot: message handling, AI calls
│   ├── context_builder.py # Xây dựng context từ user profile, goals, history
│   ├── context_policy.py  # Context access policies & validation
│   ├── prompts.py         # System prompt & prompt builders
│   └── utils.py          # Chat title generation, helpers
├── core/                  # Configuration & Security
│   ├── config.py         # Pydantic Settings (tất cả env vars)
│   ├── security.py        # JWT helpers, bcrypt password
│   ├── cache.py          # Redis cache wrapper
│   ├── rate_limiter.py   # Rate limiter setup (slowapi)
│   └── utils.py          # General utilities
└── db/                    # Database Connection
    └── session.py         # Async engine, session factory, Base class
```

## Dependency Injection Pattern

FastAPI dùng dependency injection để cung cấp dependencies cho mỗi request:

```python
from app.api.deps import get_current_user, get_db
from app.db.session import get_db

@router.post("/meal-logs")
async def create_meal(
    payload: MealLogCreate,                    # Pydantic validation
    db: AsyncSession = Depends(get_db),       # Database session
    current_user: User = Depends(get_current_user),  # Authenticated user
):
    ...
```

## Các module chính

| Module | Mục đích |
|--------|-----------|
| `api/` | Tất cả HTTP endpoints — xử lý request/response |
| `models/` | Ánh xạ cấu trúc database sang Python objects |
| `schemas/` | Xác thực dữ liệu vào/ra |
| `services/` | Logic nghiệp vụ chính — tách biệt khỏi HTTP layer |
| `ai/` | Abstraction layer cho các AI providers |
| `chatbot/` | Hệ thống chatbot AI với context awareness |
| `core/` | Cấu hình ứng dụng, bảo mật, cache |
| `db/` | Quản lý database connections |

## Truy cập cấu hình

```python
from app.core.config import settings

# Đọc biến môi trường
settings.DATABASE_URL
settings.GEMINI_API_KEY
settings.REDIS_URL
```
