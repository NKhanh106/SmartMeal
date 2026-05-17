# 🥗 SmartMeal — Tài liệu Tổng quan Dự án

> **Ngôn ngữ**: Tiếng Việt (Vietnamese)
> **Trạng thái**: MVP đạt ~90% — Backend đã audit & fix bugs, Frontend scaffold sẵn sàng phát triển UI.

---

## Mục lục

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Kiến trúc & Luồng xử lý](#2-kiến-trúc--luồng-xử-lý)
3. [Công nghệ & Thư viện sử dụng](#3-công-nghệ--thư-viện-sử-dụng)
4. [Cấu trúc thư mục chi tiết](#4-cấu-trúc-thư-mục-chi-tiết)
5. [Cài đặt & Vận hành](#5-cài-đặt--vận-hành)
6. [API Endpoints](#6-api-endpoints)

---

## 1. Tổng quan dự án

### 1.1. SmartMeal là gì?

**SmartMeal** là một **hệ thống web app đa ngôn ngữ** (Tiếng Việt + English) giúp người dùng quản lý dinh dưỡng, theo dõi tiến trình thể chất và tập luyện, có sự hỗ trợ của trí tuệ nhân tạo (AI). Hệ thống cung cấp:

- **Ghi nhận bữa ăn thông minh**: Người dùng chỉ cần chụp ảnh đồ ăn, AI sẽ tự động nhận diện các món ăn, ước lượng khối lượng và tính toán calo/macro.
- **Theo dõi dinh dưỡng cá nhân hóa**: Tính BMR/TDEE/BMI tự động dựa trên hồ sơ thể chất, đặt mục tiêu calo và macro phù hợp với từng người.
- **Lập kế hoạch tập luyện**: Quản lý kế hoạch tập gym, cardio với các bài tập cụ thể.
- **AI Chatbot tư vấn dinh dưỡng**: Trò chuyện tự nhiên với AI Coach để được tư vấn về chế độ ăn, bài tập phù hợp.
- **AI Daily Planner**: Gợi ý lịch trình ăn uống và tập luyện cho ngày mới dựa trên mục tiêu cá nhân.
- **Theo dõi tiến độ**: Nhật ký cân nặng, số đo cơ thể và ảnh tiến bộ.

### 1.2. Vấn đề cốt lõi

Nhiều người muốn ăn uống lành mạnh và tập luyện nhưng gặp khó khăn:

- **Không biết ước lượng calo**: Không có công cụ để tính calo của bữa ăn thông thường, đặc biệt là món ăn Việt Nam.
- **Thiếu kiến thức dinh dưỡng**: Không biết nên ăn bao nhiêu calo, protein, carb, fat mỗi ngày.
- **Không theo dõi được tiến độ**: Không có cách để xem mình đã ăn bao nhiêu calo trong ngày.
- **Thiếu động lực và tư vấn**: Cần lời khuyên cá nhân hóa mà không có chuyên gia.

### 1.3. Giải pháp

SmartMeal giải quyết bằng cách:

1. **AI nhận diện món ăn từ ảnh** — Người dùng chụp ảnh đĩa ăn, AI tự động nhận diện từng món, ước lượng cân nặng, và tính macro.
2. **Tính BMR/TDEE tự động** — Hệ thống tự động tính toán nhu cầu calo dựa trên công thức Mifflin-St Jeor.
3. **Dashboard theo dõi ngày/tuần** — Hiển thị tổng calo, macro đã nạp so với mục tiêu.
4. **AI Chatbot đa ngữ cảnh** — Trả lời câu hỏi dinh dưỡng dựa trên profile, mục tiêu và lịch sử ăn uống của người dùng.
5. **Gợi ý cá nhân hóa** — Đề xuất thực đơn và bài tập phù hợp với mục tiêu (giảm cân / giữ cân / tăng cơ).

### 1.4. Tính năng chính

| Tính năng | Mô tả |
|------------|--------|
| **Auth** | Đăng ký / Đăng nhập / JWT token + bcrypt |
| **User Profile** | Hồ sơ thể chất (chiều cao, cân nặng, % mỡ, vòng đo, mức vận động, chế độ ăn, dị ứng) |
| **Nutrition Goals** | Tính BMR / TDEE / BMI theo Mifflin-St Jeor, đặt mục tiêu calo/macro |
| **Meal Logs** | Ghi nhận bữa ăn kèm chi tiết món ăn, tính calo/macro |
| **Food Nutrition DB** | Cơ sở dữ liệu ~65 món ăn Việt Nam + USDA, tìm kiếm |
| **Dashboard** | Thống kê calo/macro theo ngày và tuần, timezone-aware |
| **Progress Logs** | Nhật ký theo dõi cân nặng, % mỡ, ảnh tiến bộ |
| **Workout Plans** | Kế hoạch tập luyện (1 active plan/user), quản lý bài tập |
| **AI Meal Update** | Nhận diện món ăn từ ảnh (Gemini Vision) → tự động ghi nhận bữa ăn |
| **AI Daily Planner** | Sinh gợi ý lịch trình ăn uống + tập luyện cho ngày mới |
| **AI Chatbot** | Trợ lý AI tương tác theo ngữ cảnh (profile, goals, meal history) |
| **Image Upload** | Upload ảnh với metadata, tự động dọn dẹp theo TTL |

---

## 2. Kiến trúc & Luồng xử lý

### 2.1. Biểu đồ Kiến trúc Hệ thống (Mermaid.js)

```mermaid
graph TB
    %% External Users
    User(("👤 Người dùng"))
    Browser["🌐 Browser / Mobile"]
    User --> Browser

    %% Frontend
    Browser --> Frontend["⚛️ Next.js 15 Frontend<br/>(apps/web)"]
    Frontend --> |"HTTP + JWT"| API["🔷 FastAPI Backend<br/>(apps/api)"]
    
    %% Frontend Components
    Frontend --> |"TanStack Query"| Services["📡 API Services<br/>(src/services/)"]
    Frontend --> |"Auth Context"| AuthFE["🔐 Auth Context<br/>(src/contexts/)"]
    Frontend --> |"React Components"| Components["🧩 UI Components<br/>(src/components/)"]
    
    %% Backend Components
    API --> |"Routes"| Routers["📡 API Routers<br/>(api/v1/)"]
    API --> |"Services"| ServicesBE["⚙️ Business Logic<br/>(services/)"]
    API --> |"Validation"| Schemas["📋 Pydantic Schemas<br/>(schemas/)"]
    API --> |"Dependencies"| Deps["🔑 Auth Dependencies<br/>(api/deps.py)"]
    
    %% AI Layer
    ServicesBE --> |"AI Calls"| AI["🤖 AI Layer"]
    AI --> AIFactory["🏭 AI Factory<br/>(ai/factory.py)"]
    AIFactory --> Gemini["🟡 Gemini Provider<br/>(Gemini Vision)"]
    AIFactory --> Groq["🟣 Groq Provider<br/>(LLM Text)"]
    
    %% Cache Layer
    API --> |"Cache"| Redis[("🟠 Redis Cache<br/>(cache.py)")]
    Redis --> |"AI Results"| AI
    Redis --> |"Image Hash"| ImgHash["🖼️ Image Hash<br/>(SHA256)"]
    
    %% Database
    ServicesBE --> |"ORM"| ORM[("🗄️ PostgreSQL<br/>(SQLAlchemy 2.0 async)")]
    
    %% DB Tables
    ORM --> Users["👤 users"]
    ORM --> Profiles["📊 user_profiles"]
    ORM --> NutritionGoals["🎯 nutrition_goals"]
    ORM --> Meals["🍽️ meal_logs"]
    ORM --> MealItems["🥗 meal_items"]
    ORM --> Foods["🍎 food_nutrition"]
    ORM --> Progress["📈 progress_logs"]
    ORM --> Workouts["🏋️ workout_plans"]
    ORM --> Chat["💬 chat_sessions"]
    ORM --> Images["🖼️ uploaded_images"]
    
    %% File Storage
    API --> |"Static Files"| Uploads["📁 uploads/ folder<br/>(image storage)"]
    
    %% External Services
    Gemini --> |"Vision API"| GoogleCloud["☁️ Google Cloud<br/>(Gemini API)"]
    Groq --> |"Inference API"| GroqCloud["☁️ Groq Cloud<br/>(Groq API)"]

    %% Styling
    Frontend --> |"Tailwind v4"| Tailwind["🎨 Tailwind CSS v4"]
    Frontend --> |"shadcn/ui"| Shadcn["🧩 shadcn/ui<br/>(Radix UI)"]
    
    %% Monorepo
    subgraph "🏗️ Turborepo Monorepo (pnpm workspaces)"
        Frontend
        API
    end

    %% Styling
    classDef fastapi fill:#009688,color:#fff
    classDef nextjs fill:#000,color:#fff
    classDef postgres fill:#336791,color:#fff
    classDef redis fill:#DC382D,color:#fff
    classDef ai fill:#FABC0C,color:#000
    classDef groq fill:#7B2CBF,color:#fff
```

**Giải thích kiến trúc:**

- **Frontend (Next.js 15)**: Giao diện người dùng, sử dụng TanStack Query để quản lý server state, React Context cho auth state. Giao tiếp với backend qua HTTP với JWT Bearer token.
- **Backend (FastAPI)**: REST API với async toàn bộ. Tiếp nhận request, validate bằng Pydantic, xử lý business logic trong services, tương tác với database qua SQLAlchemy 2.0 async.
- **AI Layer**: Abstraction layer sử dụng Factory pattern. Có thể switch giữa Gemini (cho vision) và Groq (cho text generation) qua config. Kết quả AI được cache trong Redis.
- **Redis Cache**: Cache kết quả nhận diện ảnh (theo SHA256 hash) để tránh gọi AI trùng lặp. TTL: 24h cho food recognition, 12h cho daily plan.
- **PostgreSQL**: 16 bảng lưu trữ toàn bộ dữ liệu: users, profiles, meals, foods, workouts, chats, images...
- **File Storage**: Ảnh upload được lưu trên disk tại `uploads/` và được phục vụ qua static files. Metadata lưu trong `uploaded_images` table.

---

### 2.2. Biểu đồ Luồng Dữ liệu — AI Meal Recognition

```mermaid
flowchart LR
    subgraph "👤 Người dùng"
        Photo["📸 Chụp ảnh đồ ăn"]
        Confirm["✅ Xác nhận & Lưu"]
    end

    subgraph "🌐 Frontend"
        FE_Upload["Upload ảnh lên API"]
        FE_Display["Hiển thị kết quả preview"]
        FE_Save["Gửi xác nhận lưu meal"]
    end

    subgraph "🔷 Backend API"
        API_Validate["Validate ảnh<br/>(magic bytes)"]
        API_SaveTemp["Lưu ảnh tạm<br/>(temporary, 1 ngày)"]
        API_CacheCheck["Check Redis cache"]
        
        subgraph "🤖 AI Meal Update Service"
            AI_Vision["🟡 Gemini Vision<br/>(analyze_image_json)"]
            AI_Match["🔍 Food Mapping<br/>(match_food_name)"]
            AI_Calc["🧮 Nutrition Calc<br/>(calculate_nutrition)"]
        end
        
        API_SaveMeal["💾 Lưu meal vào DB"]
        API_Log["📝 AI Log (latency, prompt, response)"]
        API_Cache["🟠 Cache result<br/>(SHA256 image hash)"]
    end

    subgraph "🗄️ Database"
        FoodDB["🍎 food_nutrition"]
        MealLog["🍽️ meal_logs"]
        MealItem["🥗 meal_items"]
        AI_LogTable["📝 ai_analysis_logs"]
    end

    Photo --> FE_Upload
    FE_Upload --> API_Validate
    API_Validate --> API_SaveTemp
    
    API_SaveTemp --> API_CacheCheck
    API_CacheCheck --> |"Cache MISS"| AI_Vision
    API_CacheCheck --> |"Cache HIT"| FE_Display
    
    AI_Vision --> AI_Match
    AI_Match --> FoodDB
    AI_Match --> AI_Calc
    AI_Calc --> API_Log
    API_Log --> AI_LogTable
    API_Log --> API_Cache
    API_Cache --> Redis[("🟠 Redis")]
    
    AI_Vision --> FE_Display
    FE_Display --> Confirm
    Confirm --> FE_Save
    FE_Save --> API_SaveMeal
    API_SaveMeal --> MealLog
    API_SaveMeal --> MealItem
    API_SaveMeal --> |"Promote image<br/>temporary → meal"| ImgPromote["🖼️ Update image TTL<br/>(1 day → 7 days)"]
```

**Giải thích luồng nhận diện bữa ăn:**

1. Người dùng chụp ảnh đồ ăn từ giao diện web.
2. Frontend gửi ảnh lên `POST /api/v1/ai/meal-update/recognize-image`.
3. Backend validate ảnh (kiểm tra magic bytes, kích thước).
4. Backend lưu ảnh vào disk với type `temporary` (TTL 1 ngày).
5. Backend check Redis cache: nếu cùng ảnh đã từng gửi → return cached result.
6. Nếu cache miss: gọi Gemini Vision API để nhận diện món ăn.
7. Với mỗi món nhận diện được, hệ thống:
   - Ánh xạ tên món → `food_nutrition` database (fuzzy match)
   - Tính macro dựa trên cân nặng ước lượng
8. Kết quả được cache vào Redis (SHA256 hash của ảnh, TTL 24h).
9. Preview trả về cho frontend: danh sách món, cân nặng, calo, macro.
10. Người dùng xác nhận → `POST /api/v1/ai/meal-update/confirm`.
11. Backend tạo `meal_log` + `meal_items`, promote ảnh từ `temporary` → `meal` (TTL 7 ngày).

---

### 2.3. Biểu đồ Luồng Chatbot

```mermaid
sequenceDiagram
    actor User as 👤 Người dùng
    participant FE as ⚛️ Frontend
    participant API as 🔷 FastAPI
    participant ChatSVC as 💬 Chatbot Service
    participant Context as 🎯 Context Builder
    participant Groq as 🟣 Groq API
    participant DB as 🗄️ PostgreSQL

    User->>FE: Gửi tin nhắn
    FE->>API: POST /api/v1/ai/chat/sessions/{id}/messages/stream
    API->>ChatSVC: send_chat_message()
    ChatSVC->>DB: Lưu user message
    ChatSVC->>Context: build_chatbot_context()
    Context->>DB: Lấy user profile
    Context->>DB: Lấy nutrition goals
    Context->>DB: Lấy 5 meal logs gần nhất
    Context->>DB: Lấy progress logs
    DB-->>Context: Dữ liệu ngữ cảnh
    Context-->>ChatSVC: Context dict
    ChatSVC->>ChatSVC: build_chatbot_user_prompt()

    alt Non-Streaming
        ChatSVC->>Groq: generate_text()
        Groq-->>ChatSVC: Full response
    else Streaming
        ChatSVC->>Groq: Stream response
        Groq-->>ChatSVC: Token by token
        ChatSVC-->>FE: SSE: {delta: "..."}
        User-->>FE: Thấy text hiển thị từng từ
    end

    ChatSVC->>DB: Lưu assistant message
    ChatSVC->>DB: Extract & save insights
    ChatSVC-->>FE: {done: true, message_id}
    FE-->>User: Hiển thị response đầy đủ
```

---

## 3. Công nghệ & Thư viện sử dụng

### 3.1. Ngôn ngữ lập trình

| Công nghệ | Phiên bản | Mục đích | Tại sao dùng |
|-----------|-----------|-----------|---------------|
| **Python** | >= 3.12 | Backend runtime | Async/await mạnh mẽ, hệ sinh thái AI phong phú, FastAPI framework hiện đại |
| **TypeScript** | 5.x | Frontend | Type safety giúp giảm bugs, IDE autocomplete xuất sắc, React ecosystem tốt nhất |

### 3.2. Backend Frameworks & Libraries

| Thư viện | Phiên bản | Mục đích | Tại sao dùng |
|-----------|-----------|-----------|---------------|
| **FastAPI** | Latest | Web framework | Async native, auto-generated OpenAPI docs, type-safe, hiệu suất cao |
| **SQLAlchemy** | 2.0 | ORM | Async ORM với SQLAlchemy 2.0 style (Mapped, mapped_column) cho type safety tốt nhất |
| **Pydantic** | v2 | Data validation | Validation & serialization mạnh mẽ, settings management, performance tốt |
| **asyncpg** | Latest | PostgreSQL async driver | Fast async driver cho PostgreSQL, kết hợp tốt với SQLAlchemy async |
| **Alembic** | Latest | Database migrations | Quản lý schema versioning cho PostgreSQL |
| **python-jose** | Latest | JWT handling | Encode/decode JWT tokens, thư viện nhẹ |
| **passlib** + **bcrypt** | Latest | Password hashing | Băm mật khẩu an toàn, deprecation-safe với bcrypt |
| **slowapi** | Latest | Rate limiting | Giới hạn request/Phút/IP trên endpoint AI |
| **APScheduler** | Latest | Job scheduler | Chạy job dọn dẹp ảnh định kỳ (02:00 UTC hàng ngày) |
| **ruff** | Latest | Python linter | Fast Python linter (Rust-based), thay thế flake8/isort |
| **pytest** + **pytest-asyncio** | Latest | Testing | Async test support, fixture system mạnh mẽ |
| **redis** | Latest | Redis async client | Cache AI results, fail-graceful design |

### 3.3. AI & Machine Learning

| Thư viện | Mục đích | Tại sao dùng |
|-----------|-----------|---------------|
| **Google Gemini** (SDK) | Nhận diện món ăn từ ảnh (vision model) | Multimodal model mạnh mẽ, nhận diện ảnh đồ ăn chính xác |
| **Groq** (SDK) | Text generation cho chatbot & daily planner | Inference speed cực nhanh (~100-500ms), chi phí thấp |
| **Factory Pattern** | Chọn AI provider theo config | Dễ dàng switch provider, không cần sửa business logic |
| **Circuit Breaker** | Ngăn cascading failures khi AI provider down | Hệ thống graceful degradation |
| **AI Logger** | Ghi log mọi lần gọi AI | Audit, debug, tính chi phí |

### 3.4. Database

| Thư viện | Mục đích | Tại sao dùng |
|-----------|-----------|---------------|
| **PostgreSQL** | Cơ sở dữ liệu chính | ACID-compliant, hỗ trợ JSONB, full-text search, reliable |
| **Redis** | Cache layer | Cache kết quả AI (tránh gọi trùng), fail-graceful nếu không có |
| **SQLAlchemy Async** | Async ORM | Non-blocking DB operations, tận dụng connection pool hiệu quả |

### 3.5. Frontend Frameworks & Libraries

| Thư viện | Phiên bản | Mục đích | Tại sao dùng |
|-----------|-----------|-----------|---------------|
| **Next.js** | 15.x | React framework | App Router, Server Components, built-in optimization |
| **React** | 19.x | UI library | Component-based, ecosystem lớn nhất |
| **Tailwind CSS** | v4 | Utility-first CSS | Rapid UI development, responsive design dễ dàng |
| **shadcn/ui** | Latest | UI components | Accessible, customizable, Radix UI primitives |
| **Radix UI** | Latest | Headless components | Accessible, unstyled, full control over styling |
| **TanStack Query** | 5.x | Server state management | Caching, background refetch, optimistic updates |
| **Axios** | Latest | HTTP client | Interceptors, error handling, TypedRequest helpers |
| **React Hook Form** | Latest | Form management | Performance, validation integration |
| **Zod** | Latest | Schema validation | TypeScript-first, composable schemas |
| **Recharts** | Latest | Data visualization | Biểu đồ dinh dưỡng, progress tracking |
| **Framer Motion** | Latest | Animations | Smooth transitions, gesture handling |
| **Lucide React** | Latest | Icons | Consistent, tree-shakeable icon library |
| **Sonner** | Latest | Toast notifications | Lightweight, accessible toasts |
| **browser-image-compression** | Latest | Image compression | Nén ảnh trước khi upload lên server |

### 3.6. DevOps & Infrastructure

| Công nghệ | Mục đích | Tại sao dùng |
|-----------|-----------|---------------|
| **Turborepo** | Build orchestration | Caching build outputs, parallel execution, monorepo support |
| **pnpm** | Package manager | Fast, disk-efficient, workspaces support |
| **Docker** | Containerization | Triển khai nhất quán, development parity |
| **PostgreSQL** | Database server | Persistent data storage |
| **Redis** | In-memory cache | Speed, TTL-based expiration |

---

## 4. Cấu trúc thư mục chi tiết

```
SmartMeal/                           # Root — Turborepo monorepo (pnpm workspaces)
│
├── .env.example                     # Template biến môi trường (root, dùng chung)
├── .cursor/rules/                   # Cursor AI coding rules
│   └── rules-all.mdc              # Karpathy behavioral guidelines
├── pnpm-workspace.yaml             # Định nghĩa workspaces: apps/*
├── turbo.json                     # Build pipeline config (build, dev)
├── package.json                   # Root: Turborepo + pnpm scripts
├── README.md                      # Project README (redirects)
├── TOTAL_ABOUT_PROJECT.md          # ← Tài liệu tổng quan này
├── reset_dev.sql                  # Script reset database cho development
├── create_table.sql               # SQL tạo bảng (backup)
└── note.txt                      # Ghi chú phát triển
│
├── apps/
│   ├── api/                       # Backend — FastAPI + PostgreSQL
│   │   ├── app/                  # Source code chính
│   │   │   ├── main.py          # Entry point — FastAPI app, lifespan, CORS, routers
│   │   │   ├── api/             # HTTP API Routers
│   │   │   │   ├── deps.py      # Auth deps: get_current_user, ensure_user_access
│   │   │   │   └── v1/         # v1 Endpoints
│   │   │   │       ├── router.py             # Router registry
│   │   │   │       ├── auth.py              # /auth: register, login, refresh
│   │   │   │       ├── user_profiles.py     # /user-profiles: CRUD hồ sơ thể chất
│   │   │   │       ├── nutrition_goals.py   # /nutrition-goals: BMR/TDEE/BMI, targets
│   │   │   │       ├── food_nutrition.py    # /food-nutrition: tra cứu thực phẩm
│   │   │   │       ├── meal_logs.py         # /meal-logs: CRUD bữa ăn
│   │   │   │       ├── dashboard.py         # /dashboard: thống kê ngày/tuần
│   │   │   │       ├── progress_logs.py     # /progress-logs: theo dõi cân nặng
│   │   │   │       ├── workout_plans.py     # /workout-plans: CRUD kế hoạch tập
│   │   │   │       ├── uploads.py           # /uploads: upload ảnh
│   │   │   │       ├── ai_meal_update.py   # /ai/meal-update: nhận diện ảnh
│   │   │   │       ├── ai_daily_planner.py # /ai/daily-planner: gợi ý ngày mới
│   │   │   │       ├── ai_chatbot.py       # /ai/chat: chatbot AI
│   │   │   │       ├── health.py             # /health: health check
│   │   │   │       └── README.md            # Tài liệu API v1
│   │   │   ├── models/             # SQLAlchemy ORM — 16 bảng
│   │   │   │       ├── __init__.py
│   │   │   │       ├── enums.py             # Enum types
│   │   │   │       ├── user.py              # users
│   │   │   │       ├── user_profile.py      # user_profiles
│   │   │   │       ├── nutrition_goal.py    # nutrition_goals
│   │   │   │       ├── food_nutrition.py    # food_nutrition
│   │   │   │       ├── meal.py              # meal_logs, meal_items
│   │   │   │       ├── progress_log.py      # progress_logs
│   │   │   │       ├── workout_plan.py       # workout_plans
│   │   │   │       ├── workout_item.py       # workout_items
│   │   │   │       ├── chat.py               # chat_sessions, chat_messages
│   │   │   │       ├── ai_log.py             # ai_analysis_logs
│   │   │   │       ├── daily_recommendation.py
│   │   │   │       ├── uploaded_image.py
│   │   │   │       └── conversation_insight.py
│   │   │   ├── schemas/            # Pydantic schemas — validation & serialization
│   │   │   │       ├── user.py, user_profile.py, token.py
│   │   │   │       ├── food_nutrition.py, nutrition_goal.py
│   │   │   │       ├── meal.py, meal_update.py
│   │   │   │       ├── dashboard.py, progress_log.py
│   │   │   │       ├── workout.py, chat.py
│   │   │   │       ├── daily_recommendation.py, uploaded_image.py
│   │   │   │       └── README.md
│   │   │   ├── services/           # Business logic — 14 service files
│   │   │   │       ├── meal_service.py
│   │   │   │       ├── nutrition_service.py
│   │   │   │       ├── food_nutrition_service.py
│   │   │   │       ├── food_mapping_service.py  # Fuzzy match AI → DB
│   │   │   │       ├── dashboard_service.py
│   │   │   │       ├── progress_log_service.py
│   │   │   │       ├── workout_service.py
│   │   │   │       ├── ai_meal_update_service.py
│   │   │   │       ├── daily_recommendation_service.py
│   │   │   │       ├── ai_log_service.py
│   │   │   │       ├── conversation_insights_service.py
│   │   │   │       ├── learning_service.py
│   │   │   │       ├── image_storage_service.py
│   │   │   │       ├── image_cleanup_scheduler.py
│   │   │   │       ├── planner_constraint_engine.py
│   │   │   │       └── README.md
│   │   │   ├── ai/               # AI Provider Abstraction
│   │   │   │       ├── base.py             # Abstract AIProvider class
│   │   │   │       ├── factory.py          # Factory: chọn provider theo config
│   │   │   │       ├── orchestrator.py
│   │   │   │       ├── ai_logger.py         # Log decorator cho AI calls
│   │   │   │       ├── circuit_breaker.py
│   │   │   │       ├── providers/
│   │   │   │       │   ├── gemini_provider.py   # Gemini Vision
│   │   │   │       │   └── groq_provider.py     # Groq text
│   │   │   │       └── prompts/
│   │   │   │           └── daily_planner_prompt.py
│   │   │   ├── chatbot/           # AI Chatbot System
│   │   │   │       ├── service.py              # Core: message handling, AI calls
│   │   │   │       ├── context_builder.py      # Xây dựng context từ user data
│   │   │   │       ├── context_policy.py       # Access policies, privacy
│   │   │   │       ├── prompts.py              # System prompt & builders
│   │   │   │       └── utils.py                # Helper functions
│   │   │   ├── core/              # Configuration & Security
│   │   │   │       ├── config.py             # Pydantic Settings
│   │   │   │       ├── security.py           # JWT, bcrypt
│   │   │   │       ├── cache.py              # Redis wrapper
│   │   │   │       ├── rate_limiter.py      # slowapi limiter
│   │   │   │       └── utils.py
│   │   │   └── db/                # Database Connection
│   │   │       └── session.py           # Async engine, session factory, Base
│   │   ├── alembic/               # Database migrations
│   │   │   ├── env.py
│   │   │   └── versions/          # 4 migration scripts
│   │   ├── scripts/               # Utility scripts
│   │   │   ├── seed_food_data.py    # Seed ~65 món ăn Việt Nam
│   │   │   ├── seed_demo_data.py     # Seed 10 user + 10 ngày dữ liệu
│   │   │   └── cleanup_expired_images.py
│   │   ├── tests/                 # pytest unit tests
│   │   ├── Dockerfile             # Docker container
│   │   ├── Makefile              # Dev commands (install, dev, migrate, test, lint, seed)
│   │   ├── requirements.txt      # Python deps (redis, hiredis)
│   │   ├── pyproject.toml        # Python project config (pytest, ruff)
│   │   ├── alembic.ini           # Alembic config
│   │   ├── .env.example         # Template env vars
│   │   └── README.md             # Backend documentation
│   │
│   └── web/                       # Frontend — Next.js 15 + React 19
│       ├── src/                   # Source code
│       │   ├── app/              # Next.js App Router
│       │   │   ├── layout.tsx         # Root layout
│       │   │   ├── page.tsx           # Landing page
│       │   │   ├── (auth)/            # Auth routes
│       │   │   │   ├── layout.tsx
│       │   │   │   ├── login/page.tsx
│       │   │   │   └── register/page.tsx
│       │   │   └── (dashboard)/       # Protected routes
│       │   │       ├── layout.tsx      # Dashboard layout
│       │   │       ├── dashboard/page.tsx
│       │   │       ├── upload/page.tsx
│       │   │       ├── history/page.tsx
│       │   │       ├── analytics/page.tsx
│       │   │       ├── goals/page.tsx
│       │   │       ├── workout/page.tsx
│       │   │       ├── recommendations/page.tsx
│       │   │       └── profile/page.tsx
│       │   ├── components/       # React components
│       │   │   ├── ui/         # shadcn/ui (button, card, input, dialog...)
│       │   │   ├── layout/     # Header, Sidebar, DashboardLayout
│       │   │   └── chatbot/    # FloatingChatBot, ChatPanel, ChatMessage...
│       │   ├── contexts/        # AuthContext
│       │   ├── hooks/          # use-chatbot hook
│       │   ├── lib/            # Utilities
│       │   │   ├── api-client.ts     # Axios instance + interceptors
│       │   │   ├── utils.ts          # cn(), helpers
│       │   │   └── profile-utils.ts
│       │   ├── providers/       # AppProviders, QueryProvider
│       │   ├── services/        # Typed API calls
│       │   │   ├── auth.service.ts
│       │   │   ├── meal.service.ts
│       │   │   ├── profile.service.ts
│       │   │   ├── nutrition-goal.service.ts
│       │   │   ├── workout.service.ts
│       │   │   ├── progress-log.service.ts
│       │   │   ├── analytics.service.ts
│       │   │   ├── chatbot.service.ts
│       │   │   ├── recommendation.service.ts
│       │   │   └── health-service.ts
│       │   └── types/           # TypeScript types
│       ├── middleware.ts         # Next.js auth protection
│       ├── next.config.ts       # Next.js config
│       ├── tsconfig.json        # TypeScript + path aliases (@/*)
│       ├── tailwind.config.ts  # Tailwind CSS v4
│       ├── postcss.config.js
│       ├── components.json     # shadcn/ui config
│       ├── package.json         # Dependencies & scripts
│       └── README.md            # Frontend documentation
│
├── packages/                    # (Reserved for shared packages)
└── .gitignore
```

---

## 5. Cài đặt & Vận hành

### 5.1. Yêu cầu hệ thống

| Công cụ | Phiên bản tối thiểu | Ghi chú |
|---------|---------------------|---------|
| `Node.js` | >= 20 | Cần cho frontend |
| `pnpm` | >= 9 | Package manager |
| `Python` | >= 3.12 | Backend runtime |
| `PostgreSQL` | >= 15 | Database |
| `Redis` | Latest | Optional, app chạy degraded mode nếu không có |
| `Docker` | Latest | Optional cho production |

### 5.2. Cách cài đặt từ đầu

#### Bước 1: Clone & Cài dependencies

```bash
# Clone repo
git clone <repo-url> SmartMeal
cd SmartMeal

# Cài tất cả packages qua pnpm workspaces
pnpm install

# Hoặc dùng Makefile
make install
```

#### Bước 2: Cấu hình biến môi trường

```bash
# Backend — tạo .env từ template
cp apps/api/.env.example apps/api/.env

# Frontend — tạo .env.local
# (Next.js tự động đọc .env.local)
# Đảm bảo NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**Nội dung `.env` tối thiểu:**

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/smartmeal

# Security — thay bằng chuỗi ngẫu nhiên dài
SECRET_KEY=your-super-secret-key-at-least-32-chars

# AI — lấy API key từ Google Cloud Console / Groq Dashboard
GEMINI_API_KEY=your-gemini-api-key
GROQ_API_KEY=your-groq-api-key

# Redis — tùy chọn
REDIS_URL=redis://localhost:6379/0
```

#### Bước 3: Khởi tạo PostgreSQL

```sql
-- Tạo database
CREATE DATABASE smartmeal;

-- Tạo user (tùy chọn)
CREATE USER postgres WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE smartmeal TO postgres;
```

#### Bước 4: Chạy Database Migrations

```bash
# Cách 1: Dùng Makefile
make migrate-api

# Cách 2: Trực tiếp
cd apps/api
alembic upgrade head
```

#### Bước 5: Seed dữ liệu thực phẩm (Development)

```bash
# Seed ~65 món ăn Việt Nam
make seed

# Hoặc seed dữ liệu demo đầy đủ (10 user, 10 ngày dữ liệu)
cd apps/api
python -m scripts.seed_demo_data
```

**Tài khoản demo** (sau khi seed):
- Email: `user1@smartmeal.local` → `user10@smartmeal.local`
- Password: `SmartMeal123`

#### Bước 6: Khởi chạy Backend

```bash
# Cách 1: Dùng Makefile
make dev-api

# Cách 2: Trực tiếp
cd apps/api
uvicorn app.main:app --reload --port 8000 --host 127.0.0.1

# Kiểm tra
# Swagger UI: http://localhost:8000/docs
# Health:     http://localhost:8000/health
# Root:       http://localhost:8000/
```

#### Bước 7: Khởi chạy Frontend

```bash
# Cách 1: Dùng Makefile
make dev-web

# Cách 2: Trực tiếp
cd apps/web
pnpm dev

# App: http://localhost:3000
```

#### Bước 8: (Tùy chọn) Khởi tạo Redis

```bash
# macOS (Homebrew)
brew install redis
brew services start redis

# Linux
sudo apt install redis-server
sudo systemctl start redis

# Windows (WSL2 recommended)
# Hoặc dùng Docker
docker run -d -p 6379:6379 redis:alpine
```

### 5.3. Docker Deployment

```bash
# Build backend Docker image
docker build -t smartmeal-api apps/api/

# Run với env file
docker run -p 8000:8000 \
  --env-file apps/api/.env \
  -v $(pwd)/uploads:/app/uploads \
  smartmeal-api
```

### 5.4. Lệnh Makefile tổng hợp

| Lệnh | Chức năng |
|-------|-----------|
| `make install` | Cài tất cả dependencies (pnpm) |
| `make dev-web` | Chạy frontend dev server (localhost:3000) |
| `make dev-api` | Chạy backend dev server (localhost:8000) |
| `make migrate-api` | Chạy Alembic migrations |
| `make test-api` | Chạy pytest (backend) |
| `make install:api` | Cài Python deps (backend) |
| `make seed` | Seed food data (development only) |

---

## 6. API Endpoints

### 6.1. Tổng quan

Base URL: `http://localhost:8000`
API Prefix: `/api/v1`
Auth: JWT Bearer token trong header `Authorization: Bearer <token>`

### 6.2. Danh sách Endpoints

#### Authentication

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `POST` | `/api/v1/auth/register` | Public | Đăng ký tài khoản mới |
| `POST` | `/api/v1/auth/login` | Public | Đăng nhập, nhận JWT tokens |
| `POST` | `/api/v1/auth/refresh` | Public | Refresh access token |
| `GET` | `/api/v1/auth/me` | Required | Lấy thông tin user hiện tại |

#### User Profiles

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/api/v1/user-profiles/me` | Required | Lấy profile của user hiện tại |
| `POST` | `/api/v1/user-profiles` | Required | Tạo profile (sau khi đăng ký) |
| `PUT` | `/api/v1/user-profiles/{id}` | Required | Cập nhật profile |

#### Nutrition Goals

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/api/v1/nutrition-goals` | Required | Lấy goal active hiện tại |
| `POST` | `/api/v1/nutrition-goals` | Required | Tính BMR/TDEE/BMI & tạo goal |
| `PUT` | `/api/v1/nutrition-goals/{id}` | Required | Cập nhật goal |

#### Food Nutrition

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/api/v1/food-nutrition` | Required | Tìm kiếm thực phẩm |
| `GET` | `/api/v1/food-nutrition/{id}` | Required | Chi tiết thực phẩm |
| `POST` | `/api/v1/food-nutrition` | Required | Thêm thực phẩm mới |

#### Meal Logs

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/api/v1/meal-logs` | Required | Danh sách meals (filter theo date) |
| `POST` | `/api/v1/meal-logs` | Required | Tạo meal log |
| `GET` | `/api/v1/meal-logs/{id}` | Required | Chi tiết meal |
| `PUT` | `/api/v1/meal-logs/{id}` | Required | Cập nhật meal |
| `DELETE` | `/api/v1/meal-logs/{id}` | Required | Xóa meal |

#### Dashboard

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/api/v1/dashboard/today` | Required | Thống kê ngày hôm nay |
| `GET` | `/api/v1/dashboard/weekly` | Required | Thống kê 7 ngày gần nhất |

#### Progress Logs

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/api/v1/progress-logs` | Required | Danh sách progress logs |
| `POST` | `/api/v1/progress-logs` | Required | Tạo progress log |
| `GET` | `/api/v1/progress-logs/{id}` | Required | Chi tiết |
| `DELETE` | `/api/v1/progress-logs/{id}` | Required | Xóa |

#### Workout Plans

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/api/v1/workout-plans` | Required | Danh sách workout plans |
| `POST` | `/api/v1/workout-plans` | Required | Tạo plan mới |
| `GET` | `/api/v1/workout-plans/{id}` | Required | Chi tiết plan |
| `PUT` | `/api/v1/workout-plans/{id}` | Required | Cập nhật plan |
| `DELETE` | `/api/v1/workout-plans/{id}` | Required | Xóa plan |

#### AI Meal Update (Vision)

| Method | Endpoint | Auth | Rate Limit | Mô tả |
|--------|----------|------|------------|--------|
| `POST` | `/api/v1/ai/meal-update/recognize-image` | Required | 10/min | Nhận diện món ăn từ ảnh (cache-enabled) |
| `POST` | `/api/v1/ai/meal-update/preview` | Required | 10/min | Preview kết quả AI |
| `POST` | `/api/v1/ai/meal-update/confirm` | Required | — | Xác nhận & lưu meal |

#### AI Chatbot

| Method | Endpoint | Auth | Rate Limit | Mô tả |
|--------|----------|------|------------|--------|
| `POST` | `/api/v1/ai/chat/sessions` | Required | — | Tạo session mới |
| `GET` | `/api/v1/ai/chat/sessions/user` | Required | — | Danh sách sessions của user |
| `GET` | `/api/v1/ai/chat/sessions/{id}/messages` | Required | — | Tin nhắn trong session |
| `POST` | `/api/v1/ai/chat/sessions/{id}/messages` | Required | 20/min | Gửi tin nhắn (non-streaming) |
| `POST` | `/api/v1/ai/chat/sessions/{id}/messages/stream` | Required | 20/min | Gửi tin nhắn (streaming SSE) |

#### AI Daily Planner

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `POST` | `/api/v1/ai/daily-planner/generate` | Required | Sinh gợi ý bữa ăn + workout cho ngày |
| `GET` | `/api/v1/ai/daily-planner/today` | Required | Lấy gợi ý hôm nay |
| `GET` | `/api/v1/ai/daily-planner/history` | Required | Lịch sử gợi ý |

#### Image Uploads

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `POST` | `/api/v1/uploads` | Required | Upload ảnh |
| `GET` | `/api/v1/uploads` | Required | Danh sách ảnh (pagination) |
| `GET` | `/api/v1/uploads/{id}` | Required | Metadata ảnh |
| `DELETE` | `/api/v1/uploads/{id}` | Required | Xóa ảnh |

#### Health Check

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|--------|
| `GET` | `/` | Public | Root — version info |
| `GET` | `/health` | Public | Health check |

### 6.3. Ví dụ API Calls

#### Đăng nhập

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user1@smartmeal.local", "password": "SmartMeal123"}'
```

#### Tạo Meal Log

```bash
curl -X POST http://localhost:8000/api/v1/meal-logs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "meal_type": "bua_trua",
    "meal_time": "2026-05-06T12:30:00Z",
    "items": [{
      "food_nutrition_id": "uuid-here",
      "detected_food_name": "Pho bo",
      "estimated_weight_g": 400,
      "calories": 450,
      "protein_g": 25,
      "carb_g": 55,
      "fat_g": 14
    }]
  }'
```

#### Nhận diện ảnh đồ ăn

```bash
curl -X POST http://localhost:8000/api/v1/ai/meal-update/recognize-image \
  -H "Authorization: Bearer <token>" \
  -F "image=@meal.jpg" \
  -F "meal_type=bua_trua"
```

### 6.4. Error Codes

| Mã HTTP | Mô tả |
|---------|--------|
| `400` | Bad Request — dữ liệu không hợp lệ |
| `401` | Unauthorized — token không hợp lệ hoặc hết hạn |
| `403` | Forbidden — không có quyền truy cập |
| `404` | Not Found — resource không tồn tại |
| `422` | Validation Error — Pydantic validation fail |
| `429` | Too Many Requests — vượt rate limit |
| `500` | Internal Server Error |
| `503` | Service Unavailable — AI provider down |

---

## Giả định & Ghi chú

1. **AI API Keys**: Cần lấy API key từ Google AI Studio (Gemini) và Groq Console trước khi dùng tính năng AI.
2. **Redis**: Không bắt buộc — app chạy ở "degraded mode" (không cache) nếu Redis không có. Tuy nhiên, production nên có Redis để tránh gọi AI trùng lặp.
3. **Food Database**: Seed script đã có ~65 món ăn Việt Nam phổ biến. Có thể mở rộng bằng cách thêm vào `seed_food_data.py`.
4. **USDA Integration**: Code có hỗ trợ USDA API (`USDA_API_KEY` trong config) để tra cứu thực phẩm từ USDA database.
5. **Demo Data**: Script `seed_demo_data.py` tạo 10 user mẫu với profile đa dạng (béo phì, thiếu cân, sinh hoạt kém, vận động viên...).
6. **Image Storage**: Ảnh được lưu trên disk tại `uploads/` directory. Production nên dùng S3/GCS thay vì local storage.
7. **i18n**: Frontend được thiết kế hỗ trợ đa ngôn ngữ (Tiếng Việt + English).

---

*Tài liệu này được tạo tự động từ việc phân tích codebase SmartMeal. Mọi thông tin đều dựa trên mã nguồn thực tế.*
