# 🥗 SmartMeal — Trợ lý Dinh dưỡng & Luyện tập Cá nhân hóa bằng AI

SmartMeal là hệ thống **web app** đa ngôn ngữ (Tiếng Việt + English) giúp người dùng quản lý dinh dưỡng, theo dõi tiến trình thể chất và tập luyện, có sự hỗ trợ của AI. Backend sử dụng **FastAPI** + **PostgreSQL**, Frontend sử dụng **Next.js 15** (App Router).

> **Trạng thái**: MVP đạt ~90% — Backend đã audit & fix bugs, Frontend scaffold sẵn sàng phát triển UI.

---

## Tính năng cốt lõi

| Tính năng | Mô tả | Backend file |
|---|---|---|
| **Auth** | Đăng ký / Đăng nhập / JWT token + bcrypt | `apps/api/app/api/v1/auth.py` |
| **User Profile** | Hồ sơ thể chất (chiều cao, cân nặng, % mỡ, vòng đo...) | `apps/api/app/api/v1/user_profiles.py` |
| **Nutrition Goals** | Tính BMR / TDEE / BMI theo Mifflin-St Jeor, đặt mục tiêu calo/macro | `apps/api/app/api/v1/nutrition_goals.py` |
| **Meal Logs** | Ghi nhận bữa ăn kèm chi tiết món ăn, tính calo/macro | `apps/api/app/api/v1/meal_logs.py` |
| **Food Nutrition DB** | Cơ sở dữ liệu thực phẩm, tìm kiếm, CRUD, ước lượng dinh dưỡng | `apps/api/app/api/v1/food_nutrition.py` |
| **Dashboard** | Thống kê calo/macro theo ngày và tuần, timezone-aware | `apps/api/app/api/v1/dashboard.py` |
| **Progress Logs** | Nhật ký theo dõi cân nặng, % mỡ, ảnh tiến bộ | `apps/api/app/api/v1/progress_logs.py` |
| **Workout Plans** | Kế hoạch tập luyện (1 active plan/user), quản lý bài tập | `apps/api/app/api/v1/workout_plans.py` |
| **AI Meal Update** | Nhận diện món ăn từ ảnh (Gemini Vision) → tự động ghi nhận bữa ăn | `apps/api/app/api/v1/ai_meal_update.py` |
| **AI Daily Planner** | Sinh gợi ý lịch trình ăn uống + tập luyện cho ngày mới (Groq/Gemini) | `apps/api/app/api/v1/ai_daily_planner.py` |
| **AI Chatbot** | Trợ lý AI tương tác theo ngữ cảnh (profile, goals, meal history) | `apps/api/app/api/v1/ai_chatbot.py` + `apps/api/app/chatbot/` |

---

## Kiến trúc

```
SmartMeal/                          # Root — Turborepo monorepo (pnpm workspaces)
├── apps/
│   ├── api/                      # Backend (FastAPI + PostgreSQL + Alembic)
│   └── web/                      # Frontend (Next.js 15 + Tailwind CSS v4 + shadcn/ui)
├── .env.example                   # Template biến môi trường
├── Makefile                       # Lệnh cài đặt & chạy nhanh (root)
├── pnpm-workspace.yaml            # Cấu hình pnpm workspaces
└── turbo.json                    # Cấu hình Turborepo pipeline
```

### Frontend → Backend Communication

- **Base URL**: `http://127.0.0.1:8000` (cấu hình qua `NEXT_PUBLIC_API_BASE_URL` trong `.env.local`)
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

---

## Cài đặt & Khởi chạy

### 1. Clone & Cài dependencies

```bash
# Clone repo
cd SmartMeal

# Cài tất cả packages (frontend + backend) qua pnpm workspaces
make install
# hoặc: pnpm install
```

### 2. Cấu hình biến môi trường

```bash
# Backend
cp apps/api/.env.example apps/api/.env
# Chỉnh sửa apps/api/.env: điền DATABASE_URL, SECRET_KEY, GEMINI_API_KEY, GROQ_API_KEY

# Frontend
cp apps/web/.env.local.example apps/web/.env.local  # (nếu có file mẫu)
# Hoặc tạo file apps/web/.env.local với:
#   NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### 3. Khởi tạo Database (Alembic migrations)

```bash
make migrate-api
# hoặc: cd apps/api && alembic upgrade head
```

### 4. Chạy Backend

```bash
make dev-api
# hoặc: cd apps/api && uvicorn app.main:app --reload
# Swagger: http://127.0.0.1:8000/docs
# Health:   http://127.0.0.1:8000/health
```

### 5. Chạy Frontend

```bash
make dev-web
# hoặc: pnpm --filter web dev
# App:      http://localhost:3000
```

### Lệnh Makefile (root)

| Lệnh | Chức năng |
|-------|-----------|
| `make install` | Cài tất cả dependencies (pnpm) |
| `make dev-web` | Chạy frontend dev server |
| `make dev-api` | Chạy backend dev server |
| `make migrate-api` | Chạy Alembic migrations |
| `make test-api` | Chạy pytest |

---

## Database Schema

Database gồm **15 bảng**, được quản lý qua **Alembic** (2 migrations):

```
users                          -- Tài khoản người dùng
user_profiles                  -- Hồ sơ thể chất (1:1 với users)
nutrition_goals                -- Mục tiêu dinh dưỡng (1 active/user)
food_nutrition                 -- Cơ sở dữ liệu thực phẩm
meals                          -- Bữa ăn (meal_logs)
meal_items                     -- Chi tiết từng món trong bữa ăn
ai_analysis_logs               -- Log gọi AI (latency, prompt, response)
daily_recommendations          -- Kết quả AI Daily Planner
progress_logs                  -- Nhật ký theo dõi thể chất
workout_plans                  -- Kế hoạch tập luyện (1 active/user)
workout_items                  -- Bài tập trong kế hoạch
chat_sessions                  -- Phiên chat với AI Coach
chat_messages                  -- Tin nhắn trong phiên chat
```

---

## AI Providers

| Provider | Mô hình | Mục đích | Cấu hình |
|----------|---------|-----------|-----------|
| **Gemini** | `gemini-2.5-flash` | Nhận diện món ăn từ ảnh (Vision) | `GEMINI_API_KEY` |
| **Groq** | `llama-3.3-70b-versatile` | Daily Planner, Chatbot (text) | `GROQ_API_KEY` |
| **Groq Vision** | `meta-llama/llama-4-scout-17b-16e-instruct` | Fallback nhận diện ảnh | `GROQ_API_KEY` |

Có thể chọn provider qua biến: `AI_CHAT_PROVIDER`, `AI_PLANNER_PROVIDER`, `AI_MEAL_PROVIDER`.

---

## Testing

```bash
# Chạy tất cả tests (backend)
make test-api

# Output mẫu: 18 passed, 12 skipped
```

---

## Backend API Endpoints

| Nhóm | Prefix | Mô tả |
|------|--------|-------|
| Auth | `/api/v1/auth` | Đăng ký, đăng nhập, token refresh |
| Users | `/api/v1/users` | Thông tin user |
| Profiles | `/api/v1/user-profiles` | CRUD hồ sơ thể chất |
| Nutrition Goals | `/api/v1/nutrition-goals` | Tính & lưu mục tiêu dinh dưỡng |
| Food Nutrition | `/api/v1/food-nutrition` | Cơ sở dữ liệu thực phẩm |
| Meal Logs | `/api/v1/meal-logs` | Ghi nhận & truy vấn bữa ăn |
| Dashboard | `/api/v1/dashboard` | Thống kê calo/macro ngày & tuần |
| Progress Logs | `/api/v1/progress-logs` | Nhật ký theo dõi thể chất |
| Workout Plans | `/api/v1/workout-plans` | Kế hoạch & bài tập |
| AI Meal Update | `/api/v1/ai/meal-update` | Preview & confirm bữa ăn từ ảnh |
| AI Daily Planner | `/api/v1/ai/daily-planner` | Sinh gợi ý ngày mới |
| AI Chatbot | `/api/v1/ai/chat` | Chat session & tin nhắn |

---

## Các file quan trọng

| File | Mục đích |
|------|---------|
| `apps/api/app/main.py` | FastAPI app entry point, CORS, router registration |
| `apps/api/app/core/config.py` | Pydantic Settings — tất cả env vars |
| `apps/api/app/core/security.py` | Password hashing (bcrypt), JWT helpers |
| `apps/api/app/api/deps.py` | Auth dependencies (`get_current_user`, `ensure_user_access`) |
| `apps/api/app/ai/factory.py` | AI Provider factory với caching |
| `apps/api/alembic/versions/*.py` | Database migrations |
| `apps/web/src/lib/api-client.ts` | Axios client với JWT interceptors |
| `apps/web/src/providers/query-provider.tsx` | TanStack Query provider |
| `.env.example` | Template tất cả biến môi trường |
