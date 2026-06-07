# `app/db/` — Database Layer & Schema Registry

## Module Overview & Domain Boundaries

This folder governs all **database interaction primitives** for SmartMeal:

- **Async SQLAlchemy engine** and session factory, configured for Supabase PostgreSQL with PgBouncer in transaction mode.
- **`Base` DeclarativeBase** — the single declarative root that all ORM models inherit from.
- **`get_db()` dependency** — FastAPI `Depends()`-compatible async session provider with automatic rollback on exception.
- **Exercise seed data** — one-time seeding script for the `exercises` table.

Routing is split by lifecycle:

| Port | Consumer | Connection Path |
|---|---|---|
| 6543 | Application runtime (`AsyncSessionLocal`) | PgBouncer (transaction mode) |
| 5432 | Alembic migrations | Direct PostgreSQL |

---

## File Registry & Critical Path Map

| File Path | Authoritative Component / Class | Inbound Dependencies | Core Technical Responsibility |
|---|---|---|---|
| `__init__.py` | — | — | SmartMeal database package marker (empty) |
| `session.py` | `engine`, `AsyncSessionLocal`, `get_db()`, `Base`, `POOL_WARNING_THRESHOLD` | `settings.ASYNC_DATABASE_POOL_URL` | Async SQLAlchemy engine (PgBouncer port 6543); pool_size=4, max_overflow=12; `statement_cache_size=0`; `expire_on_commit=False`; pool checkout monitoring |
| `seeds/__init__.py` | — | — | Seeds package marker (empty) |
| `seeds/seed_exercises.py` | `seed_exercises()`, `EXERCISES_DATA` | `app.models.exercise.Exercise` | One-time seed of 56 bodyweight exercises across 3 goal types; run via `python -m app.db.seeds.seed_exercises` |

---

## Local Invariants & Production Logic Rules

### Async Engine Configuration

```python
create_async_engine(
    settings.ASYNC_DATABASE_POOL_URL,   # Supabase: host:6543 (PgBouncer)
    pool_size=4,                        # FIX-8: raised from 2 to 4
    max_overflow=12,                     # FIX-8: raised from 6 to 12
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,   # 1800 s (30 min)
    pool_pre_ping=settings.DATABASE_POOL_PRE_PING,  # False — PgBouncer handles health
    connect_args={
        "server_settings": {
            "application_name": "smartmeal_backend",
        },
        "statement_cache_size": 0,       # Required: asyncpg + PgBouncer compat
        "max_cached_statement_lifetime": 0,
    },
)
```

### Pool Sizing Mathematics

```
pool_size per worker      = 4
max_overflow per worker   = 12
─────────────────────────────────
Max connections per worker = 16
Workers                   = 4
─────────────────────────────────
Total max connections     = 64
PgBouncer max_connections = 80  (configured in docker-compose.yml)
```

### PgBouncer Transaction Mode Constraints

Because PgBouncer is in **transaction mode** (`pgbouncer_mode = transaction`):

- `SET` statements (session state) do **not persist** across transactions.
- **Prepared statements are per-connection** and cannot be shared; `statement_cache_size = 0` is mandatory.
- Alembic must connect **directly** on port 5432 (bypassing PgBouncer) to run migrations safely.

### AsyncSessionLocal Configuration

```python
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Objects remain usable after commit (avoids extra queries)
    autoflush=False,         # Manual flush control; commit is explicit per request
)
```

### Session Lifecycle (`get_db()`)

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

### Pool Checkout Monitoring

An `event.listens_for(engine.sync_engine, "checkout")` listener fires on every connection checkout:

```
checked_out >= pool_size × 0.8  →  WARNING log
checked_out <  pool_size × 0.8  →  DEBUG log

Fields emitted: pool_size, checked_out, overflow, pool_total
POOL_WARNING_THRESHOLD = 0.8
```

### Exercise Seed Data

56 exercises across three goal contexts, stored in `EXERCISES_DATA`:

| Goal Type | Exercise Count | Difficulty Range |
|---|---|---|
| `giam_can` (weight loss) | 16 | `nguoi_moi` – `trung_binh` |
| `tang_co` (muscle gain) | 14 | `nguoi_moi` – `nang_cao` |
| `giu_can` (maintenance) | 14 | `nguoi_moi` – `trung_binh` |

All exercises are bodyweight-only (`equipment_needed = False`, `is_active = True`).

---

## Intra-Module Request Flow

### Application DB Request Lifecycle

```
FastAPI endpoint (async def)
    │
    ▼
Depends(get_db)  ──► AsyncSessionLocal()
    │
    ├─► Service layer reads/writes via session
    │    └─► SQLAlchemy: select / insert / update / delete
    │
    ├─► (Success path) → endpoint returns → router commits
    │
    └─► (Exception) → await session.rollback()
         │
         └─► finally: await session.close()

AsyncSessionLocal.close()
    │
    ▼
Connection returned to PgBouncer pool
```

### Migration vs. Runtime Routing

```
Alembic (alembic upgrade head)
    │
    ▼
DATABASE_URL  ──► Direct PostgreSQL port 5432
                   (bypasses PgBouncer)

Application (uvicorn)
    │
    ▼
ASYNC_DATABASE_POOL_URL  ──► PgBouncer port 6543
                              (transaction mode)
```
