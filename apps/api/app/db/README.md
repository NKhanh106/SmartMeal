# `app/db/` — Database Layer, Session Management & Concurrency Strategy

## Module Overview & Domain Boundaries

This folder governs all **database interaction primitives** for SmartMeal:

- **Async SQLAlchemy engine** and session factory, configured for Supabase PostgreSQL with PgBouncer in transaction mode.
- **`Base` DeclarativeBase** — the single declarative root that all ORM models inherit from.
- **`get_db()` dependency** — FastAPI `Depends()`-compatible async session provider with automatic rollback on exception.
- **Pool checkout monitoring** — `event.listens_for` hook logs pool saturation at 80% threshold.
- **Exercise seed data** — one-time seeding script for the `exercises` table.

---

## 1. Dual-Connection Topology (Supabase PostgreSQL)

SmartMeal separates database connections into **two distinct tiers** to safely operate behind Supabase's PgBouncer in transaction mode:

```
┌──────────────────────────────────────────────────────────────────┐
│               Supabase Cloud PostgreSQL                              │
│  ┌─────────────────────────┐    ┌──────────────────────────────┐  │
│  │  Direct Connection        │    │  PgBouncer Pooled (port    │  │
│  │  Port 5432              │    │  6543, transaction mode)    │  │
│  │  ─────────────────────  │    │  ─────────────────────────  │  │
│  │  DATABASE_URL            │    │  DATABASE_POOL_URL          │  │
│  │  (pgbouncer=false)     │    │  (?pgbouncer=true)          │  │
│  │  Alembic Migrations ONLY│    │  FastAPI Runtime ONLY       │  │
│  └─────────────────────────┘    └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

| Port | Connection String | Consumer | PgBouncer Layer |
|------|-----------------|----------|-----------------|
| **5432** | `DATABASE_URL` / `ASYNC_DATABASE_URL` | Alembic migrations | Direct — bypasses PgBouncer entirely |
| **6543** | `ASYNC_DATABASE_POOL_URL` | FastAPI application runtime | Behind PgBouncer (transaction mode) |

### Why Two Ports?

Supabase's free tier uses PgBouncer as a connection pooler in **transaction mode**. Key constraints:

- **Transaction mode**: `SET` statements do **not persist** across transactions — session state is reset per transaction.
- **Prepared statements are per-connection** — cannot be shared; `statement_cache_size = 0` is **mandatory**.
- **DDL operations** (Alembic migrations) are **incompatible with transaction mode** — they must connect directly on port 5432.
- **`pool_pre_ping=False` is intentional** — a health-check ping on a PgBouncer-inactive connection causes PgBouncer to mark that connection dead and drop the in-flight transaction.

---

## 2. Verified Pool Configuration (`app/db/session.py`)

```python
engine = create_async_engine(
    settings.ASYNC_DATABASE_POOL_URL,   # Supabase: host:6543 (PgBouncer)
    pool_size=4,                     # FIX-8 (C-1): Per-worker base connections
    max_overflow=12,                 # FIX-8 (C-1): Per-worker burst ceiling
    pool_timeout=30,                # Wait up to 30s for a connection
    pool_recycle=1800,              # 30 min — PgBouncer idle timeout = 60 min
    pool_pre_ping=False,             # DISABLED — prevents PgBouncer tx pollution
    connect_args={
        "server_settings": {
            "application_name": "smartmeal_backend",
        },
        "statement_cache_size": 0,           # Required for asyncpg + PgBouncer
        "max_cached_statement_lifetime": 0,   # Required for asyncpg + PgBouncer
    },
)
```

### Pool Sizing Mathematics

```
pool_size per worker         = 4
max_overflow per worker    = 12
─────────────────────────────────
Max connections per worker  = 16
Workers                  = 4
─────────────────────────────────
Total max connections     = 64 connections
PgBouncer max_connections = 80 (configured in docker-compose.yml)
Supabase Free Tier limit  = 60 connections
─────────────────────────────────
Headroom                 = 16 spare connections
```

> **FIX-8 (C-1) note**: The ceiling of 64 total connections is intentionally tight to the Supabase free-tier limit of 60. Increase `max_overflow` or reduce worker count when deploying to a tighter connection limit. The extractor queue worker (`extractor_queue_worker_loop`) consumes 1 connection per worker during extraction (~3–10s per task), so `max_overflow=12` provides adequate headroom.

---

## 3. AsyncSessionLocal Configuration

```python
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Objects remain usable after commit (avoids extra queries)
    autoflush=False,        # Manual flush control; commit is explicit per request
)
```

- `expire_on_commit=False` — ORM objects stay attached after `commit()`, preventing lazy-load queries on already-fetched relationships.
- `autoflush=False` — flushes are explicit; prevents premature dirty-writes during read-heavy operations.

---

## 4. Session Lifecycle (`get_db()`)

```
FastAPI Depends(get_db)
    │
    ▼
async with AsyncSessionLocal() as session
    │
    ├─► try: yield session
    │       └─► (success) → finally: session.close()
    │
    └─► except: await session.rollback()
              └─► finally: session.close()
```

Connections are returned to the PgBouncer pool after `session.close()`.

---

## 5. Pool Checkout Monitoring

An `event.listens_for(engine.sync_engine, "checkout")` listener fires on every connection checkout:

```
checked_out >= pool_size × 0.8  →  WARNING log
checked_out <  pool_size × 0.8  →  DEBUG log

Fields emitted: pool_size, checked_out, overflow, pool_total
POOL_WARNING_THRESHOLD = 0.8
```

---

## 6. MemoryWriteEngine Row-Level Locking (`SELECT FOR UPDATE`)

Beyond connection pooling, SmartMeal uses **PostgreSQL row-level locks** to serialize concurrent writes to `UserMemory`:

```
MemoryWriteEngine.apply()    ──► SELECT ... FOR UPDATE ON UserMemory
                                      WHERE user_id = ?
                                 ──► (lock acquired)
                                      ──► Deep merge JSONB fields
                                      ──► UPDATE UserMemory
                                      ──► COMMIT / ROLLBACK
```

This prevents race conditions when two concurrent requests both try to update the same user's memory (e.g., `HealthMonitorAgent` + `NutritionAdvisorAgent` writing simultaneously).

The lock is held for the minimum duration possible — only during the merge-and-write phase, not during the entire agent execution.

---

## 7. Exercise Seed Data

56 exercises across three goal contexts, stored in `EXERCISES_DATA`:

| Goal Type | Count | Difficulty Range |
|----------|-------|-----------------|
| `giam_can` (weight loss) | 16 | `nguoi_moi` – `trung_binh` |
| `tang_co` (muscle gain) | 14 | `nguoi_moi` – `nang_cao` |
| `giu_can` (maintenance) | 14 | `nguoi_moi` – `trung_binh` |

All exercises are bodyweight-only (`equipment_needed = False`, `is_active = True`).

Seed via: `python -m app.db.seeds.seed_exercises`

---

## File Registry

| File | Authoritative Component | Core Technical Responsibility |
|------|----------------------|----------------------------|
| `session.py` | `engine`, `AsyncSessionLocal`, `get_db()`, `Base`, `POOL_WARNING_THRESHOLD` | PgBouncer-safe async engine; pool checkout monitoring |
| `__init__.py` | Package marker | — |
| `seeds/__init__.py` | Package marker | — |
| `seeds/seed_exercises.py` | `seed_exercises()`, `EXERCISES_DATA` | One-time exercise seed (56 records) |
