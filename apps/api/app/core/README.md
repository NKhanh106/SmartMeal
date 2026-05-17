# Thư mục `core/` — Cấu hình Ứng dụng & Bảo mật

## Mục đích

Chứa các thành phần **cốt lõi** của backend SmartMeal: cấu hình ứng dụng, bảo mật, cache, và rate limiting. Đây là nơi đặt tất cả các thiết lập toàn cục không nên hard-code ở nơi khác.

## Các thành phần

### 1. `config.py` — Cấu hình Ứng dụng (Pydantic Settings)

Đọc biến môi trường từ file `.env` và cung cấp typed settings cho toàn bộ ứng dụng.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "SmartMeal API"
    VERSION: str = "0.1.0"
    DATABASE_URL: str = ""
    SECRET_KEY: str = "dev-only-change-me"
    AI_MEAL_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
```

**Tính năng quan trọng:**
- Auto-detect file `.env` ở thư mục `apps/api/` hoặc root
- Production validator: từ chối chạy nếu `SECRET_KEY` yếu ở production
- Computed field `ASYNC_DATABASE_URL`: tự động thêm prefix `postgresql+asyncpg://` cho async driver
- Cache TTL settings: `AI_CACHE_TTL_SECONDS`, `FOOD_RECOGNITION_CACHE_TTL`, `DAILY_PLAN_CACHE_TTL`
- Image retention settings: ngày tự xóa ảnh theo loại (meal: 7d, temporary: 1d, progress: NULL/never)

### 2. `security.py` — Bảo mật (JWT & Password)

Các hàm helper cho xác thực:

```python
from app.core.security import create_access_token, verify_password, get_password_hash

# Tạo JWT access token (mặc định 24h)
token = create_access_token(user_id)

# Tạo refresh token (7 ngày)
refresh_token = create_refresh_token(user_id)

# Hash & verify password (bcrypt)
hashed = get_password_hash("MyPassword123")
verify_password("MyPassword123", hashed)  # → True
```

**Thuật toán**: HS256 với JWT (python-jose)
**Password hashing**: Bcrypt qua passlib

### 3. `cache.py` — Redis Cache

Wrapper async cho Redis với fail-graceful design:

```python
from app.core.cache import cache_get, cache_set, cache_delete, make_cache_key, make_image_cache_key

# Cache key cho food recognition (hash ảnh → không nhận diện lại)
key = make_image_cache_key(image_bytes)

# Lấy từ cache
cached = await cache_get(key)

# Lưu vào cache với TTL
await cache_set(key, data, ttl=86400)  # 24h

# Xóa cache
await cache_delete(key)
```

**Đặc điểm:**
- Fail-graceful: nếu Redis down, app vẫn chạy không crash
- Image cache key: SHA256 hash của bytes → tránh nhận diện cùng 1 ảnh 2 lần
- TTL từ config: `FOOD_RECOGNITION_CACHE_TTL` (24h), `AI_CACHE_TTL_SECONDS` (1h), `DAILY_PLAN_CACHE_TTL` (12h)

### 4. `rate_limiter.py` — Rate Limiting

Dùng `slowapi` để giới hạn số request:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

Áp dụng rate limit cho endpoint cụ thể:

```python
@router.post("/recognize-image")
@limiter.limit("10/minute")  # Tối đa 10 request/phút
async def recognize_meal_image(...):
    ...
```

## Environment Variables

Tất cả biến môi trường được định nghĩa trong `config.py`. File `.env.example` ở root và `apps/api/.env.example` chứa template đầy đủ.

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/smartmeal

# Security
SECRET_KEY=your-super-secret-key-here

# AI Providers
GEMINI_API_KEY=your-google-api-key
GROQ_API_KEY=your-groq-api-key

# Redis
REDIS_URL=redis://localhost:6379/0

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000"]
```

## Production Security Checks

`config.py` tự động từ chối chạy production nếu:
- `SECRET_KEY` vẫn là giá trị mặc định dev
- `SECRET_KEY` ngắn hơn 32 ký tự
- `POSTGRES_PASSWORD` vẫn là giá trị mặc định
- CORS origins chứa wildcard `*` khi `allow_credentials=True`

## CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Best Practices

- **KHÔNG** hard-code secret key hoặc API keys trong code
- Luôn tạo `.env` từ `.env.example`
- Trong production, sinh SECRET_KEY bằng: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- Redis nên được setup ở production để tận dụng cache và tránh gọi AI trùng lặp
