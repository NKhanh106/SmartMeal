# Thư mục app/ - Core Application Logic

## Mục đích

Đây là thư mục chứa toàn bộ **logic nghiệp vụ** của backend SmartMeal. Tất cả code Python liên quan đến API, database, AI, và xử lý nghiệp vụ đều nằm trong thư mục này. Đây là "trái tim" của backend server.

## Cấu trúc

```
app/
├── main.py              # Entry point - khởi tạo FastAPI app
├── api/                # API Routes (endpoints)
│   └── v1/            # API v1 - tất cả endpoints
├── models/             # SQLAlchemy ORM Models
├── schemas/            # Pydantic Schemas (validation)
├── services/           # Business Logic Layer
├── ai/                 # AI Provider Integration
├── chatbot/            # Chatbot System
├── core/               # Configuration & Security
└── db/                 # Database Connection
```

## Entry Point - main.py

File `main.py` là điểm khởi đầu của ứng dụng FastAPI, chịu trách nhiệm:
- Khởi tạo FastAPI instance
- Cấu hình CORS
- Include API routers
- Thiết lập database connection
- Đăng ký exception handlers

## Dependency Injection

FastAPI sử dụng dependency injection pattern. Các dependencies chính:
- `get_db()` - Cung cấp database session
- `get_current_user()` - Lấy user hiện tại từ JWT token
- Các service dependencies cho business logic

## Routing Flow

```
Request → Middleware → API Route (app/api/v1/) 
        → Pydantic Schema Validation 
        → Service Layer 
        → Model/ORM 
        → Database 
        → Response Serialization 
        → Client
```

## Các package chính

| Package | Mục đích |
|---------|----------|
| `api/` | Định nghĩa tất cả HTTP endpoints |
| `models/` | Ánh xạ cấu trúc database sang Python objects |
| `schemas/` | Xác thực dữ liệu vào/ra |
| `services/` | Logic nghiệp vụ chính |
| `ai/` | Tích hợp các AI providers |
| `chatbot/` | Hệ thống chatbot |
| `core/` | Cấu hình ứng dụng, security |
| `db/` | Quản lý database connections |
