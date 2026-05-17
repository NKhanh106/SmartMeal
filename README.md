# 🥗 SmartMeal — Trợ lý Dinh dưỡng & Luyện tập Cá nhân hóa bằng AI

> **Trạng thái**: MVP đạt ~90% — Backend đã audit & fix bugs, Frontend scaffold sẵn sàng phát triển UI.

---

## Tài liệu

### 📖 Tài liệu tổng quan (Đọc trước)

**[`TOTAL_ABOUT_PROJECT.md`](./TOTAL_ABOUT_PROJECT.md)** — Tài liệu siêu chi tiết bao gồm:
- Tổng quan dự án, tính năng, và vấn đề cốt lõi
- Biểu đồ kiến trúc hệ thống (Mermaid.js)
- Biểu đồ luồng dữ liệu AI Meal Recognition (Mermaid.js)
- Danh sách đầy đủ công nghệ & thư viện
- Cấu trúc thư mục chi tiết với comment
- Hướng dẫn cài đặt từ đầu
- Danh sách đầy đủ API Endpoints

### 📂 Tài liệu theo module

#### Backend (apps/api/)

| File | Mô tả |
|------|--------|
| [`apps/api/README.md`](./apps/api/README.md) | Tổng quan backend, cách chạy, công nghệ |
| [`apps/api/app/README.md`](./apps/api/app/README.md) | Core application logic, routing flow |
| [`apps/api/app/api/v1/README.md`](./apps/api/app/api/v1/README.md) | Danh sách tất cả API endpoints |
| [`apps/api/app/models/README.md`](./apps/api/app/models/README.md) | 16 database tables, ORM models |
| [`apps/api/app/schemas/README.md`](./apps/api/app/schemas/README.md) | Pydantic schemas, validation |
| [`apps/api/app/services/README.md`](./apps/api/app/services/README.md) | Business logic layer |
| [`apps/api/app/core/README.md`](./apps/api/app/core/README.md) | Config, security, cache, rate limiter |
| [`apps/api/app/ai/README.md`](./apps/api/app/ai/README.md) | AI providers (Gemini, Groq) |
| [`apps/api/app/chatbot/README.md`](./apps/api/app/chatbot/README.md) | AI chatbot system |

#### Frontend (apps/web/)

| File | Mô tả |
|------|--------|
| [`apps/web/README.md`](./apps/web/README.md) | Tổng quan frontend, routing, auth flow |
| [`apps/web/src/README.md`](./apps/web/src/README.md) | Source code structure, providers |
| [`apps/web/src/components/README.md`](./apps/web/src/components/README.md) | React components |
| [`apps/web/src/lib/README.md`](./apps/web/src/lib/README.md) | Axios client, utilities |
| [`apps/web/src/services/README.md`](./apps/web/src/services/README.md) | API service layer |

---

## Tính năng cốt lõi

| Tính năng | Mô tả |
|------------|--------|
| **Auth** | Đăng ký / Đăng nhập / JWT token + bcrypt |
| **User Profile** | Hồ sơ thể chất (chiều cao, cân nặng, % mỡ, vòng đo...) |
| **Nutrition Goals** | Tính BMR / TDEE / BMI theo Mifflin-St Jeor |
| **Meal Logs** | Ghi nhận bữa ăn kèm chi tiết món ăn, tính calo/macro |
| **Food Nutrition DB** | Cơ sở dữ liệu ~65 món ăn Việt Nam + USDA |
| **Dashboard** | Thống kê calo/macro theo ngày và tuần, timezone-aware |
| **Progress Logs** | Nhật ký theo dõi cân nặng, % mỡ, ảnh tiến bộ |
| **Workout Plans** | Kế hoạch tập luyện (1 active plan/user) |
| **AI Meal Update** | Nhận diện món ăn từ ảnh (Gemini Vision) → tự động ghi nhận bữa ăn |
| **AI Daily Planner** | Sinh gợi ý lịch trình ăn uống + tập luyện cho ngày mới |
| **AI Chatbot** | Trợ lý AI tương tác theo ngữ cảnh (profile, goals, meal history) |

---

## Kiến trúc

```
SmartMeal/                          # Root — Turborepo monorepo (pnpm workspaces)
├── apps/
│   ├── api/                      # Backend (FastAPI + PostgreSQL + Alembic)
│   │   ├── app/               # Source code (models, schemas, services, AI, chatbot)
│   │   ├── alembic/           # Database migrations
│   │   └── scripts/           # Seed data scripts
│   └── web/                      # Frontend (Next.js 15 + Tailwind CSS v4 + shadcn/ui)
├── .env.example                   # Template biến môi trường
├── pnpm-workspace.yaml            # pnpm workspaces
├── turbo.json                    # Turborepo pipeline
└── TOTAL_ABOUT_PROJECT.md         # Tài liệu tổng quan chi tiết
```

### Frontend → Backend Communication

- **Base URL**: `http://127.0.0.1:8000`
- **API Prefix**: Tất cả endpoints đều có prefix `/api/v1`
- **Auth**: JWT Bearer token trong header `Authorization: Bearer <token>`
- **Swagger**: `http://127.0.0.1:8000/docs`

---

## Yêu cầu hệ thống

| Công cụ | Phiên bản | Ghi chú |
|---------|-----------|---------|
| `Node.js` | >= 20 | Cần cho frontend |
| `pnpm` | >= 9 | Package manager |
| `Python` | >= 3.12 | Backend runtime |
| `PostgreSQL` | >= 15 | Database |
| `Redis` | Latest | Optional (app chạy degraded mode nếu không có) |

---

## Cài đặt & Khởi chạy nhanh

```bash
# 1. Cài dependencies
make install

# 2. Cấu hình .env
cp apps/api/.env.example apps/api/.env
# Chỉnh sửa: DATABASE_URL, SECRET_KEY, GEMINI_API_KEY, GROQ_API_KEY

# 3. Chạy migrations
make migrate-api

# 4. Seed dữ liệu (development)
make seed

# 5. Chạy Backend
make dev-api      # → http://localhost:8000/docs

# 6. Chạy Frontend (terminal khác)
make dev-web      # → http://localhost:3000
```

**Tài khoản demo** (sau khi seed):
- Email: `user1@smartmeal.local` → `user10@smartmeal.local`
- Password: `SmartMeal123`

### Lệnh Makefile (root)

| Lệnh | Chức năng |
|-------|-----------|
| `make install` | Cài tất cả dependencies (pnpm) |
| `make dev-web` | Chạy frontend dev server |
| `make dev-api` | Chạy backend dev server |
| `make migrate-api` | Chạy Alembic migrations |
| `make test-api` | Chạy pytest |
| `make seed` | Seed food data (development only) |

---

## Database Schema

Database gồm **16 bảng**, được quản lý qua **Alembic** (4 migrations):

```
users                          -- Tài khoản người dùng (soft delete)
user_profiles                  -- Hồ sơ thể chất (1:1 với users)
nutrition_goals                -- Mục tiêu dinh dưỡng (1 active/user)
food_nutrition                 -- Cơ sở dữ liệu thực phẩm
meal_logs                      -- Nhật ký bữa ăn
meal_items                     -- Chi tiết món trong bữa ăn
ai_analysis_logs               -- Log gọi AI (latency, prompt, response)
daily_recommendations          -- Kết quả AI Daily Planner
progress_logs                  -- Nhật ký theo dõi thể chất
workout_plans                  -- Kế hoạch tập luyện (1 active/user)
workout_items                  -- Bài tập trong kế hoạch
chat_sessions                  -- Phiên chat với AI Coach
chat_messages                  -- Tin nhắn trong phiên chat
uploaded_images                -- Metadata ảnh upload
conversation_insights          -- Insights trích xuất từ cuộc trò chuyện
```

---

## AI Providers

| Provider | Mô hình | Mục đích | Cấu hình |
|----------|---------|-----------|-----------|
| **Gemini** | `gemini-2.5-flash` | Nhận diện món ăn từ ảnh (Vision) | `GEMINI_API_KEY` |
| **Groq** | `llama-3.3-70b-versatile` | Daily Planner, Chatbot (text) | `GROQ_API_KEY` |

Có thể chọn provider qua biến: `AI_CHAT_PROVIDER`, `AI_PLANNER_PROVIDER`, `AI_MEAL_PROVIDER`.

---

## Các file quan trọng

| File | Mục đích |
|------|---------|
| `apps/api/app/main.py` | FastAPI entry point, CORS, router registration, lifespan |
| `apps/api/app/core/config.py` | Pydantic Settings — tất cả env vars |
| `apps/api/app/core/security.py` | Password hashing (bcrypt), JWT helpers |
| `apps/api/app/api/deps.py` | Auth dependencies (`get_current_user`, `ensure_user_access`) |
| `apps/api/app/ai/factory.py` | AI Provider factory với caching |
| `apps/api/alembic/versions/*.py` | Database migrations |
| `apps/web/src/lib/api-client.ts` | Axios client với JWT interceptors |
| `apps/web/src/providers/query-provider.tsx` | TanStack Query provider |
| `apps/api/scripts/seed_demo_data.py` | Seed 10 user + 10 ngày dữ liệu demo |
| `TOTAL_ABOUT_PROJECT.md` | Tài liệu tổng quan đầy đủ |
