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
  ├── Phase 1: HealthMonitor        → Urgent triage, medical emergency gate
  ├── Phase 2: NutritionAdvisor   → Mifflin-St Jeor macro calculator
  ├── Phase 2: FitnessCoach       → Biomechanical safety overrides
  ├── Phase 2: WebResearcher      → Real-first web search (Tavily)
  └── Phase 3: ExtractorAgent     → Fire-and-forget (Redis queue)
     ↕
PostgreSQL 16 + Redis 7 + PgBouncer + Alembic
```

### Three-Phase Pipeline

| Phase | Agents | Concurrency | Timing |
|---|---|---|---|
| Phase 1 | HealthMonitorAgent | Sequential | Blocks all Phase 2 until complete |
| Phase 2 | NutritionAdvisor, FitnessCoach, WebResearcher | Parallel | After Phase 1 completes |
| Phase 3 | ExtractorAgent | Fire-and-forget | After HTTP response begins |

### Pending State Lifecycle

When users chat about meals, the system silently extracts structured data and stores it for user confirmation:

```
User Message
    │
    ▼
create_tracked_task() ──► LPUSH to Redis extractor_queue
    │
    ▼
HTTP Response begins streaming (main connection closes)
    │
    ▼
extractor_queue_worker_loop() ──► BRPOP blocks on queue
    │
    ▼
ExtractorAgent parses chat → structured JSON
    │
    ▼
MealLog written with status = PENDING (calories=0, awaiting confirmation)
    │
    ▼
Frontend polls GET /nutrition/pending
    │
    ▼
MealConfirmationCard renders (quantity +/- stepper, macro totals)
    │
    ▼
User clicks [✓ Xác nhận lưu]
    │
    ▼
PATCH /nutrition/pending/{id}/confirm
    ├─ SELECT FOR UPDATE (row-level lock)
    ├─ Per-item negative clamp (calories ≥ 0)
    ├─ BMR floor enforcement (total ≥ BMR × 1.0)
    └─ status → APPROVED, totals recalculated
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
| Connection Pool | PgBouncer (transaction mode) | — |
| Cache | Redis | 7 |
| AI | Groq API + Google Gemini | — |
| Auth | JWT + bcrypt | — |
| Migrations | Alembic | — |
| Containers | Docker + Docker Compose | — |

## Database Connection Architecture

SmartMeal uses a **dual-connection topology** to work safely with Supabase's PgBouncer in transaction mode:

| Port | Connection | Consumer | Notes |
|---|---|---|---|
| 5432 | Direct PostgreSQL | Alembic migrations | Bypasses PgBouncer |
| 6543 | PgBouncer pooled | FastAPI runtime | `pool_size=4`, `max_overflow=12` |

**Per-worker ceiling:** 4 + 12 = 16 connections × 4 workers = **64 max** (within Supabase free tier 60-connection limit).

`pool_pre_ping` is intentionally **disabled** — a health check on a PgBouncer-inactive connection would cause PgBouncer to drop the transaction.

## Project Structure

```
SmartMeal/
├── apps/
│   ├── api/          # FastAPI backend
│   │   ├── app/
│   │   │   ├── agents/         # Multi-agent AI system (6 agents, 3-phase pipeline)
│   │   │   ├── api/v1/         # REST API endpoints
│   │   │   ├── core/           # Config, security, cache, queue
│   │   │   ├── models/         # SQLAlchemy ORM models
│   │   │   ├── schemas/        # Pydantic request/response
│   │   │   ├── services/       # Business logic layer
│   │   │   ├── chatbot/         # Chat pipeline (cards, triggers, context)
│   │   │   ├── db/             # DB session management
│   │   │   └── ai/             # AI provider abstraction + circuit breaker
│   │   ├── migrations/         # Alembic migration scripts
│   │   ├── scripts/             # Seed data, utilities
│   │   └── tests/              # pytest test suite
│   │       └── sma_eval/       # SMA-Eval v1 benchmark suite
│   │
│   └── web/           # Next.js 15 frontend
│       └── src/
│           ├── app/             # Next.js pages (App Router)
│           ├── components/       # React components + chatbot UI
│           ├── hooks/           # Custom React hooks
│           ├── services/       # API client functions
│           └── lib/            # Utilities, types, constants
│
├── docker-compose.yml  # Local development stack
├── .env.example      # Environment template
└── README.md         # This file
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

3. **Run database migrations (always use direct port 5432)**

```bash
cd apps/api
# Use direct connection — never run migrations through PgBouncer
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
| `DATABASE_URL` | PostgreSQL connection string (for runtime — uses PgBouncer port 6543) |
| `MIGRATION_DATABASE_URL` | Direct PostgreSQL for Alembic (port 5432, bypasses PgBouncer) |
| `DATABASE_POOL_URL` | Pooled connection string for FastAPI runtime |
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
# Backend unit tests
cd apps/api && python -m pytest tests/ -q

# SMA-Eval v1 benchmark suite
cd apps/api && python -m tests.sma_eval.runner --config full

# TypeScript check
cd apps/web && npx tsc --noEmit
```

## SMA-Eval v1 — Multi-Agent Benchmark

The benchmark suite evaluates the SmartMeal Multi-Agent system across three tiers of data:

| Tier | Name | Scope |
|---|---|---|
| **A** | Hard Constraints | Biomedical rules, age boundaries, calorie floors, allergen blocking |
| **B** | Reasoning & Consistency | Cross-agent conflicts, recipe feasibility, inter-agent consistency |
| **C** | Infrastructure Stress | Burst load, concurrent requests, pool survival |

Results are aggregated using **CHAS v2** (Composite Health & Agent Score):

```
CHAS v2 = (Safety_Score × 0.40) + (Quality_Score × 0.35) + (Performance_Score × 0.25)

Safety_Score    = avg(AllergenViolation, NutritionalConstraint)
Quality_Score   = avg(NutritionalEstimationMAE, InterAgentConsistency, RecipeFeasibility)
Performance_Score = f(latency_ms, pool_survival_rate, throughput_rps)
```

Run the full benchmark:

```bash
cd apps/api
python -m tests.sma_eval.runner --config full --output results.json

# Ablation studies
python -m tests.sma_eval.runner --config baseline
python -m tests.sma_eval.runner --config partial --ablation-block health_monitor
```

See `apps/api/tests/sma_eval/README.md` for full documentation.

## License

Private project — all rights reserved.
