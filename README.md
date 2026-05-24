# SmartMeal

AI-powered nutrition and fitness tracking platform for Vietnamese users. Combines a multi-agent AI system with personalized health profiling to deliver nutrition advice, fitness coaching, and meal tracking through a conversational chat interface.

## What It Does

SmartMeal is a personal nutrition and fitness assistant accessed through a chat interface. Users log meals by simply describing what they ate ("sáng nay tôi ăn bánh mì với sữa"), ask nutrition questions ("tôi nên ăn gì để giảm cân?"), or request workout plans ("gợi ý bài tập gym cho người mới"). The AI understands Vietnamese, tracks macros, monitors health conditions, and adapts recommendations based on the user's profile and conversation history.

## Architecture Overview

```
Next.js 15 (Web)
     ↕ REST + SSE
FastAPI (API)
     ↕
Multi-Agent Orchestrator
  ├── Extractor Agent      → UserMemory (PostgreSQL JSONB)
  ├── Health Monitor        → AgentInsight
  ├── Nutrition Advisor     → MealLog
  ├── Fitness Coach         → WorkoutPlan
  └── Web Researcher       → Cached findings (Redis)
     ↕
PostgreSQL 16 + Redis 7 + Alembic
```

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Next.js (App Router) | 15.x |
| UI | Radix UI + Tailwind CSS | 4.x |
| State | TanStack React Query | v5 |
| Backend | FastAPI + Uvicorn | 0.110+ |
| Language | Python | 3.12 |
| ORM | SQLAlchemy (async) | 2.0 |
| Database | PostgreSQL | 16 |
| Cache | Redis | 7 |
| AI | Groq API + Google Gemini | — |
| Auth | JWT + bcrypt | — |
| Migrations | Alembic | — |
| Containers | Docker + Docker Compose | — |

## Project Structure

```
SmartMeal/
├── apps/
│   ├── api/          # FastAPI backend
│   │   ├── app/
│   │   │   ├── agents/         # Multi-agent AI system
│   │   │   ├── api/v1/         # REST API endpoints
│   │   │   ├── core/           # Config, security, cache
│   │   │   ├── models/          # SQLAlchemy ORM models
│   │   │   ├── schemas/         # Pydantic request/response
│   │   │   ├── services/        # Business logic layer
│   │   │   ├── chatbot/         # Chat pipeline (cards, triggers, context)
│   │   │   ├── db/              # DB session management
│   │   │   └── main.py          # FastAPI app entry point
│   │   ├── migrations/          # Alembic migration scripts
│   │   ├── scripts/             # Seed data, utilities
│   │   └── tests/               # pytest test suite
│   │
│   └── web/           # Next.js 15 frontend
│       └── src/
│           ├── app/             # Next.js pages (App Router)
│           ├── components/       # React components
│           ├── hooks/           # Custom React hooks
│           ├── services/        # API client functions
│           └── lib/             # Utilities, types, constants
│
├── docker-compose.yml  # Local development stack
├── .env.example        # Environment template
└── README.md           # This file
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- pnpm
- PostgreSQL 16 (or Supabase connection URL)
- Redis 7

### Local Development

1. **Clone and install dependencies**

```bash
# Backend
cd apps/api
pip install -r requirements.txt

# Frontend
cd apps/web
pnpm install
```

2. **Configure environment**

```bash
# Backend
cp apps/api/.env.example apps/api/.env
# Edit apps/api/.env with your database URL, Redis URL, and API keys

# Frontend
cp apps/web/.env.example apps/web/.env.local
```

3. **Run database migrations**

```bash
cd apps/api
alembic upgrade head
```

4. **Seed food data (optional)**

```bash
cd apps/api
python scripts/seed_food_data.py
python scripts/seed_demo_data.py  # Creates demo user
```

5. **Start development servers**

```bash
# Terminal 1 — API
cd apps/api && uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd apps/web && pnpm dev
```

The frontend is at `http://localhost:3000`, the API at `http://localhost:8000`.

### Demo Credentials

After running `seed_demo_data.py`:

- **Email:** demo@smartmeal.vn
- **Password:** Demo123!

## Environment Variables

### Backend (apps/api/.env)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `SECRET_KEY` | JWT signing key (32+ chars in production) |
| `ALGORITHM` | JWT algorithm (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry (default: 1440) |
| `GROQ_API_KEY` | Groq API key for LLM calls |
| `GEMINI_API_KEY` | Google Gemini API key for vision |
| `ENVIRONMENT` | `development` or `production` |
| `BACKEND_CORS_ORIGINS` | Allowed frontend URL(s) |

### Frontend (apps/web/.env.local)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | Backend API URL |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key |

## Running with Docker

```bash
# Start all services (api, web, redis)
docker-compose up --build

# Start in background
docker-compose up -d --build
```

The API is at `http://localhost:8000`, the frontend at `http://localhost:3000`.

## API Documentation

Interactive API docs are available in development mode:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

Docs are disabled in production (`ENVIRONMENT=production`).

## Testing

```bash
# Backend tests
cd apps/api && python -m pytest tests/ -q

# TypeScript check
cd apps/web && npx tsc --noEmit
```

## License

Private project — all rights reserved.
