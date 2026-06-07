# `app/core/` — Foundation & Infrastructure Layer

## Module Overview & Domain Boundaries

This folder provides the shared operational infrastructure that every other layer of the SmartMeal backend depends on. It governs:

- **Configuration**: Environment-driven settings via Pydantic `BaseSettings`, including database URLs, AI provider keys, pool parameters, and TTLs.
- **Database Session Management**: Async SQLAlchemy engine and `AsyncSessionLocal` configured for Supabase PgBouncer (transaction mode) with per-worker pool sizing.
- **Caching & Cache Stampede Prevention**: Redis-backed `cache.py` with distributed locking (`cache_lock.py`) and probabilistic early expiry (`cache_stampede.py`).
- **Security**: JWT creation/verification, bcrypt password hashing, and CORS validation.
- **Input Sanitisation**: Prompt injection prevention via Unicode normalisation and pattern matching.
- **Token Budgeting**: Per-context token estimation and truncation utilities.
- **Rate Limiting**: SlowAPI-based IP-rate limiter with `X-Forwarded-For` resolution.
- **Background Concurrency Control**: Semaphore-bounded task management preventing DB pool exhaustion under burst load.
- **Extractor Queue**: Redis `LPUSH`/BRPOP queue for deferred background extraction that cannot race with the main request.
- **Logging**: Structured stdout logging with noise reduction from external libraries.

---

## File Registry & Critical Path Map

| File Path | Authoritative Component / Class | Inbound Dependencies | Core Technical Responsibility |
|---|---|---|---|
| `__init__.py` | — (empty) | — | — |
| `background.py` | `BACKGROUND_TASK_SEMAPHORE`, `create_tracked_task()`, `run_with_semaphore()`, `extractor_queue_worker_loop()` | `settings.BACKGROUND_TASK_CONCURRENCY_LIMIT` | Global `asyncio.Semaphore(4)` bounds all fire-and-forget tasks; `extractor_queue_worker_loop()` uses Redis `BRPOP` polling |
| `cache.py` | `get_redis()`, `cache_get()`, `cache_set()`, `make_cache_key()` | `redis.asyncio`, `settings.REDIS_URL` | Global singleton Redis client; JSON serialisation; degraded-mode failures (no crash on Redis down) |
| `cache_lock.py` | `CacheLock`, `cache_lock()` async context manager | Lua `_RELEASE_SCRIPT` | SET NX + TTL distributed lock; safe release via UUID token comparison; 100ms retry interval |
| `cache_stampede.py` | `get_or_regenerate_with_lock()`, `check_and_trigger_early_expiry_refresh()`, `trigger_background_refresh()` | `CacheLock`, `create_tracked_task` | Cache-aside with distributed lock; 3-tier jittered backoff on lock failure (0.1s → 0.4s → 1.6s ±10% jitter) |
| `config.py` | `Settings`, `settings` singleton | `pydantic_settings`, `pathlib.Path` | 12 URL/credential fields; `ASYNC_DATABASE_POOL_URL` prioritises PgBouncer port 6543 over direct port 5432; `ENVIRONMENT` validator rejects wildcard CORS in production |
| `constants.py` | `HEALTH_CONDITIONS` (26 conditions), `CONDITION_RULES`, `ALLERGENS` (11), `DIETARY_RESTRICTIONS` (14), `USAGE_GOAL_TO_NUTRITION_GOAL` | — | Canonical reference constants used by agents, chatbot, and services |
| `extractor_queue.py` | `ExtractorTask`, `extractor_enqueue()` (LPUSH), `extractor_dequeue()` (BRPOP), `extractor_enqueue_proposal()`, `extractor_drain_proposals()` | `redis.asyncio`, `get_redis()` | Redis list queue for deferred extraction; `SCAN` + pipeline for atomic proposal drain |
| `logging_config.py` | `setup_logging()` | Python `logging` stdlib | Structured format `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`; suppresses uvicorn, SQLAlchemy, httpx noise |
| `rate_limiter.py` | `limiter`, `get_real_ip()` | `slowapi`, `get_remote_address` | SlowAPI Limiter keyed on first `X-Forwarded-For` IP; passes `X-Real-IP` |
| `sanitize.py` | `sanitize_for_prompt()`, `sanitize_food_name()`, `INJECTION_PATTERNS` (11 regexes) | `unicodedata` NFKC | Processing order: Unicode NFKC → strip null/control → apply ALL patterns → truncate (post-filter) |
| `security.py` | `create_access_token()`, `create_refresh_token()`, `verify_password()`, `get_password_hash()`, `pwd_context` (bcrypt) | `jose`, `passlib` | HS256 JWT encoding; refresh tokens include `jti` for atomic rotation; 7-day refresh expiry |
| `token_budget.py` | `estimate_tokens()`, `truncate_to_token_budget()`, `build_context_within_budget()` | — | Language-aware token estimation (3 chars/token Vietnamese, 4 chars/token English); priority-ordered section assembly with head+tail truncation |
| `utils.py` | `round_decimal()`, `safe_decimal()`, `serialize_dict()`, `get_active_goal()`, `now_utc()` | `decimal.ROUND_HALF_UP` | Shared decimal helpers; `Decimal` → `float` → JSON safe serialisation; canonical `get_active_goal` implementation |

---

## Local Invariants & Production Logic Rules

### Database Pooling (PgBouncer Transaction Mode)

The engine connects through PgBouncer on port 6543 at runtime, while Alembic migrations bypass PgBouncer and connect directly on port 5432.

| Parameter | Value | Rationale |
|---|---|---|
| `pool_size` | 4 | 4 workers × 4 = 16 base connections |
| `max_overflow` | 12 | Peak ceiling: 16 + 12 = 28 per worker |
| `pool_recycle` | 1,800 s (30 min) | PgBouncer max idle = 60 min; recycle before expiry |
| `pool_pre_ping` | `False` | PgBouncer handles connection health |
| `statement_cache_size` | 0 (asyncpg) | Required for PgBouncer compat — prepared stmts are per-connection |
| `max_cached_statement_lifetime` | 0 | Same as above |

### Redis Cache TTLs

| Cache Type | TTL | Trigger |
|---|---|---|
| AI general result | 3,600 s (1 h) | `AI_CACHE_TTL_SECONDS` |
| Food recognition | 86,400 s (24 h) | `FOOD_RECOGNITION_CACHE_TTL` |
| Daily plan | 43,200 s (12 h) | `DAILY_PLAN_CACHE_TTL` |
| Proposal (Redis queue) | 600 s (10 min) | `PROPOSAL_TTL_SECONDS` |

### Sanitisation Sequence (`sanitize_for_prompt`)

1. **Unicode NFKC normalisation** — collapses homoglyphs (Cyrillic `і` → Latin `i`, full-width → half-width).
2. **Control character stripping** — `[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]` removed.
3. **Pattern filtering** — all 11 `INJECTION_PATTERNS` applied in sequence; each match replaced with `[filtered]`.
4. **Post-filter truncation** — applied only after the text is clean.

### Token Budgeting

- `estimate_tokens()`: Vietnamese (>30% non-ASCII) → 3 chars/token; English → 4 chars/token.
- `build_context_within_budget()`: Sections sorted by priority (descending); lower-priority dropped first; last section truncated to fill remaining budget.
- `MAX_CONTEXT_TOKENS = 4,000` (leaves headroom for output).

### Cache Stampede Prevention — Lock Timeout Backoff

```
Lock acquire attempt → fail → jittered backoff:
  Attempt 1:  0.1s  ±10%  (0.09 – 0.11s)
  Attempt 2:  0.4s  ±10%  (0.36 – 0.44s)
  Attempt 3:  1.6s  ±10%  (1.44 – 1.76s)
All exhausted → regenerate without caching
```

### Background Task Concurrency

- `BACKGROUND_TASK_CONCURRENCY_LIMIT = 4` per worker.
- `BACKGROUND_TASK_SEMAPHORE` is a module-level `asyncio.Semaphore(4)`.
- `_active_tasks: set[asyncio.Task]` prevents garbage collection of in-flight tasks.
- `create_tracked_task()` → `run_with_semaphore()` → semaphore acquisition.

### Extractor Redis Queue

- Queue key: `smartmeal:extractor_queue` (Redis `LPUSH`/BRPOP).
- Proposal key: `smartmeal:proposal:{user_id}:{proposal_id}` (SETEX 600 s).
- Drain: `SCAN` + pipeline (single round-trip) to collect all pending proposal keys atomically, then `GETDEL` all values.

### Security Constants

| Constant | Value |
|---|---|
| Password hashing | `bcrypt` via `passlib` |
| JWT algorithm | `HS256` |
| Access token expiry | 1,440 min (24 h) |
| Refresh token expiry | 7 days |
| Refresh token includes `jti` | Yes (atomic rotation) |
| `ENVIRONMENT=production` requires `SECRET_KEY` ≥ 32 chars | Yes |

---

## Intra-Module Request Flow

### Database Session Lifecycle

```
FastAPI request
    │
    ▼
AsyncSessionLocal()          ← pool_size=4, max_overflow=12, statement_cache_size=0
    │
    ├─► Service layer (reads/writes)
    │
    ├─► (Optional) session.commit()
    │
    └─► session.close()             ← returns connection to pool
```

### Cache Stampede — Lock Acquisition Flow

```
cache_get(key) → MISS
    │
    ▼
CacheLock.acquire()  ──► Redis SET NX + TTL=60s
    │
    ├─► Lock acquired:
    │        ├─► Double-check cache (another process populated)
    │        │    ├─► HIT  → return cached value
    │        │    └─► MISS → regenerate() → cache_set() → return
    │        └─► release()
    │
    └─► Lock timeout:
             ├─► 0.1s delay → retry
             ├─► 0.4s delay → retry
             ├─► 1.6s delay → retry
             └─► All fail → regenerate() WITHOUT caching
```

### Extractor Queue Lifecycle

```
Orchestrator.process()
    │
    ▼
extractor_enqueue()  ──► LPUSH task JSON to Redis list
    │
    ▼
HTTP response returned (main transaction commits)

extractor_queue_worker_loop()
    │
    ▼
BRPOP timeout=5s  ◄── blocks until task available
    │
    ▼
ExtractorAgent.execute()  ──► MemoryWriteEngine.apply()
    │
    ▼
extractor_enqueue_proposal()  ──► SETEX proposal TTL=600s

Orchestrator (next request)
    │
    ▼
extractor_drain_proposals()  ──► SCAN + GETDEL pipeline  ──► SSE update_proposal events
```
