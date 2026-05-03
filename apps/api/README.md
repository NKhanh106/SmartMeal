# SmartMeal API - Backend Server

## Mục đích

Đây là **backend server** của ứng dụng SmartMeal, được xây dựng bằng **FastAPI** (Python) kết hợp với cơ sở dữ liệu **PostgreSQL**. API này cung cấp tất cả các endpoint cần thiết để phục vụ ứng dụng web và mobile, bao gồm xác thực người dùng, quản lý dinh dưỡng, bài tập thể dục, chatbot AI, và hệ thống phân tích dữ liệu.

## Công nghệ sử dụng

- **Framework**: FastAPI - web framework hiệu đại, hỗ trợ async, auto-generated OpenAPI docs
- **Database**: PostgreSQL - cơ sở dữ liệu quan hệ mạnh mẽ
- **ORM**: SQLAlchemy - ánh xạ đối tượng quan hệ, giúp làm việc với database dễ dàng hơn
- **Validation**: Pydantic - thư viện xác thực dữ liệu và serialization
- **Migrations**: Alembic - quản lý phiên bản database schema
- **Authentication**: JWT (JSON Web Token) với Passlib/Bcrypt để hash mật khẩu
- **AI Integration**: Google Generative AI (Gemini) và Groq - cung cấp khả năng AI cho chatbot và đề xuất thông minh
- **Testing**: Pytest - framework testing cho Python

## Cấu trúc thư mục

```
apps/api/
├── app/                    # Thư mục chính chứa toàn bộ code backend
│   ├── main.py            # Entry point - khởi tạo ứng dụng FastAPI
│   ├── api/               # Định nghĩa tất cả API endpoints
│   │   └── v1/           # Phiên bản API v1 (để dễ dàng mở rộng sau này)
│   ├── models/            # SQLAlchemy ORM models - ánh xạ bảng trong database
│   ├── schemas/           # Pydantic schemas - xác thực request/response
│   ├── services/          # Business logic - logic nghiệp vụ chính
│   ├── ai/                # Tích hợp AI providers (Gemini, Groq)
│   ├── chatbot/           # Hệ thống chatbot AI
│   ├── core/              # Cấu hình, bảo mật, constants
│   └── db/                # Kết nối database
├── alembic/               # Quản lý database migrations
│   └── versions/         # Các script migration
├── tests/                # Unit tests cho backend
├── Dockerfile            # Docker configuration
├── Makefile              # Các lệnh tiện ích (chạy server, migration, ...)
├── requirements.txt      # Python dependencies
└── pyproject.toml        # Python project configuration
```

## Các module chính

### API Endpoints (`app/api/v1/`)
Chứa tất cả routes của ứng dụng, được nhóm theo chức năng:
- **auth.py** - Đăng ký, đăng nhập, refresh token
- **user_profiles.py** - Quản lý thông tin cá nhân người dùng
- **meal_logs.py** - Ghi nhật ký bữa ăn
- **food_nutrition.py** - Tra cứu thông tin dinh dưỡng thực phẩm
- **nutrition_goals.py** - Thiết lập mục tiêu dinh dưỡng
- **workout_plans.py** - Kế hoạch tập luyện
- **progress_logs.py** - Theo dõi tiến độ
- **dashboard.py** - Dữ liệu tổng quan dashboard
- **uploads.py** - Upload và quản lý ảnh
- **ai_*.py** - Các endpoint AI (recommendations, meal analysis, chatbot)

### Models (`app/models/`)
Định nghĩa cấu trúc các bảng trong database:
- User, UserProfile - Thông tin người dùng
- MealLog, FoodNutrition - Nhật ký ăn uống
- NutritionGoal - Mục tiêu dinh dưỡng
- WorkoutPlan, WorkoutSession - Kế hoạch tập luyện
- ProgressLog - Nhật ký tiến độ
- Chat, Message, AIMessage - Dữ liệu chatbot
- DailyRecommendation - Đề xuất hàng ngày
- UploadedImage - Metadata ảnh upload

### Services (`app/services/`)
Chứa logic nghiệp vụ, tách biệt khỏi API routes:
- meal_service.py - Xử lý nghiệp vụ liên quan đến bữa ăn
- nutrition_service.py - Tính toán và quản lý dinh dưỡng
- workout_service.py - Quản lý bài tập
- dashboard_service.py - Tổng hợp dữ liệu dashboard
- image_storage_service.py - Lưu trữ và quản lý ảnh upload
- image_cleanup_scheduler.py - Scheduler tự động xóa ảnh hết hạn

### AI Integration (`app/ai/`)
- **providers/** - Triển khai cụ thể cho từng AI provider (Gemini, Groq)
- **factory.py** - Factory pattern để chọn provider phù hợp
- **prompts/** - Các prompt templates cho AI

### Chatbot (`app/chatbot/`)
Hệ thống chatbot AI thông minh:
- Xây dựng context từ lịch sử trò chuyện và dữ liệu người dùng
- Áp dụng policies để đảm bảo câu trả lời chính xác
- Tích hợp với meal logging và recommendations

## Cách chạy

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Chạy server (development)
uvicorn app.main:app --reload --port 8000

# Chạy migrations
alembic upgrade head

# Chạy tests
pytest tests/
```

## API Documentation

Khi server đang chạy, truy cập:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Database Models

Hệ thống có **16 bảng** trong database, được quản lý qua Alembic migrations:
- users, user_profiles
- meal_logs, food_nutritions
- nutrition_goals, daily_recommendations
- workout_plans, workout_sessions
- progress_logs
- chat_sessions, chat_messages
- ai_usage_logs
- uploaded_images

## Image Storage System

Hệ thống quản lý ảnh upload với metadata trong database và file trên disk.

### Storage Architecture

```
DB: uploaded_images (metadata only)
Disk: uploads/{user_id}/{image_type}/{image_id}.{ext}
URL:  /uploads/{user_id}/{image_type}/{image_id}.{ext}
```

### Image Types & Retention

| Type | TTL | Auto-delete | Use case |
|------|-----|-------------|----------|
| `avatar` | Never (`NULL`) | No | Profile picture |
| `meal` | 7 days | Yes | Confirmed meal photos |
| `temporary` | 1 day | Yes | Preview during AI analysis |
| `progress` | Never (`NULL`) | No | Progress tracking photos |

### Image Lifecycle (Meal Upload)

```
1. User uploads photo → saved as temporary (1-day TTL)
2. AI analyzes image → returns preview with uploaded_image_id + image_url
3. User confirms meal → uploaded_image_id links image to meal_log
4. Image type promoted: temporary → meal (7-day TTL)
5. Cleanup job (daily at 02:00 UTC) removes expired images
```

### Configuration

```env
UPLOAD_DIR=uploads
MAX_IMAGE_SIZE_BYTES=5242880        # 5 MB
IMAGE_PUBLIC_BASE_URL=/uploads
IMAGE_RETENTION_DAYS_MEAL=7
IMAGE_RETENTION_DAYS_TEMPORARY=1
IMAGE_RETENTION_DAYS_PROGRESS=90    # NULL = never auto-delete
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/uploads` | Upload image |
| `GET` | `/api/v1/uploads` | List user's images |
| `GET` | `/api/v1/uploads/{id}` | Get image metadata |
| `DELETE` | `/api/v1/uploads/{id}` | Delete image (soft delete) |
| `GET` | `/uploads/{path}` | Serve uploaded files |

### Running Cleanup Manually

```bash
# Via script (cron-friendly)
python -m app.scripts.cleanup_expired_images

# Scheduler runs automatically at 02:00 UTC daily (APScheduler)
```

## Bảo mật

- Mật khẩu được hash bằng bcrypt
- JWT tokens cho xác thực API
- Role-based access control (user, admin)
- CORS configuration cho frontend
