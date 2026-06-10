# SmartMeal API Test Suite

## Directory Structure

```
tests/
├── conftest.py                    # Shared pytest fixtures (auth, DB session, app factory)
├── sma_eval/                     # SMA-Eval v1 benchmark suite
│   ├── README.md                 # Full benchmark documentation
│   ├── conftest.py              # Benchmark fixtures (auth, user state, TDEE helpers)
│   ├── dataset.json             # Test case definitions (Tier A / B / C)
│   ├── metrics.py              # 7 custom metrics + SMAMetricSuite
│   ├── reporter.py             # CHAS v2 calculator + Markdown/HTML report generators
│   └── runner.py              # SMARunner, SSE_Token_Aggregator, DB assertion loop
│
├── test_auth.py                 # Authentication: register, login, refresh, logout
├── test_chat_session.py         # Chat session CRUD + message history
├── test_health_monitor_agent.py # HealthMonitor unit tests
├── test_extractor_agent.py      # ExtractorAgent unit tests
├── test_orchestrator.py        # Orchestrator routing + Phase 1/2/3 flow
├── test_meal_extraction.py     # Food extraction from chat text
├── test_nutrition.py            # Nutrition goal CRUD + TDEE calculations
├── test_profile.py              # User profile CRUD
├── test_food_permissions.py     # Food nutrition permission checks
├── test_validation_and_meals.py # Meal log creation validation
├── test_depth_modes.py          # QUICK / DEEP / EXPERT depth routing
├── test_clarification.py        # Clarification card anti-loop protection
├── test_chatbot_utils.py       # Chat title generation, sanitize helpers
├── test_cache_lock.py          # Cache lock acquisition / release
├── test_cache_stampede.py      # Cache stampede prevention logic
├── test_stampede_integration.py # Integration: cache stampede + Redis
├── test_session_pool.py          # Connection pool checkout monitoring
├── test_trigram_migration.py   # Alembic migration smoke tests
├── test_safety_fixes.py       # Safety fix regression tests (A-3/A-4, D-2/D-3, D-5, C-1/C-2)
└── test_data_writers.py        # UpdateProposal → DB write pipeline
```

## Test Categories

| Category | Files | Purpose |
|---|---|---|
| Unit — Agents | `test_health_monitor_agent.py`, `test_extractor_agent.py`, `test_orchestrator.py` | Test individual agent logic, routing, Phase 1/2/3 separation |
| Unit — Services | `test_nutrition.py`, `test_profile.py`, `test_meal_extraction.py` | Test business logic: TDEE math, meal creation, food matching |
| Unit — Infrastructure | `test_cache_lock.py`, `test_cache_stampede.py`, `test_session_pool.py` | Test Redis cache, PgBouncer pool behaviour |
| Integration | `test_stampede_integration.py`, `test_depth_modes.py`, `test_clarification.py` | Test cross-component flows |
| Regression | `test_safety_fixes.py`, `test_data_writers.py` | Regression tests for A/D/C/FIX-series safety fixes |
| Benchmark | `sma_eval/` | SMA-Eval v1 — see `sma_eval/README.md` |

## Running Tests

```bash
# All unit tests
cd apps/api
python -m pytest tests/ -q

# Skip benchmark suite (long-running)
python -m pytest tests/ -q --ignore=tests/sma_eval/

# Benchmark suite only
python -m pytest tests/sma_eval/ -v

# Single file
python -m pytest tests/test_health_monitor_agent.py -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term-missing -q
```

## SMA-Eval v1 Benchmark

The benchmark suite (`tests/sma_eval/`) evaluates the full 3-phase multi-agent pipeline:

```
Tier A — Hard Constraint Rules     (allergen violations, TDEE floor)
Tier B — Agent Interaction/Conflict (IAC, TDQ, RRA)
Tier C — Infrastructure           (pool survival, token efficiency)
```

See `sma_eval/README.md` for full documentation on metrics, CHAS v2 formula, ablation study, and CLI usage.
