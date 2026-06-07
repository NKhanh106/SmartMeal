# SmartMeal API

## Enterprise Multi-Agent Nutrition & Fitness Clinical Engineering System

FastAPI backend powering SmartMeal — an asynchronous, high-concurrency orchestration layer that drives a custom **2-Phase parallel Multi-Agent framework**, delivering deterministic biochemical, behavioral, and biomechanically-restricted nutrition and fitness recommendations in Vietnamese.

---

## Table of Contents

1. [Technical Abstract](#1-technical-abstract)
2. [High-Level Architecture Map](#2-high-level-architecture-map)
3. [Advanced Multi-Agent Directory](#3-advanced-multi-agent-directory)
4. [Production Database Infrastructure](#4-production-database-infrastructure--connection-pooling)
5. [Enterprise Security, Guardrails & Anti-Hallucination Matrix](#5-enterprise-security-guardrails--anti-hallucination-matrix)
6. [Live Search Architecture](#6-live-search-architecture-webresearcheragent)
7. [2-Phase Execution Topology — Internal Mechanics](#7-2-phase-execution-topology--internal-mechanics)
8. [Configuration Reference](#8-configuration-reference)
9. [Installation & Local Deployment](#9-installation--local-deployment)

---

## 1. Technical Abstract

SmartMeal API is a clinical-grade FastAPI application that orchestrates **6 specialized AI agents** to deliver personalized nutrition and fitness guidance. The system employs a **2-Phase execution topology**: Phase 1 gates all downstream agents with a mandatory Health Monitor clinical triage path; Phase 2 runs Nutrition Advisor, Fitness Coach, and Web Researcher in parallel isolation. Every agent writes through a **centralized `MemoryWriteEngine`** that enforces field-level ownership with deterministic row-level locking on PostgreSQL. The context-loading bottleneck was resolved by replacing 6 sequential `SELECT` queries with a single SQLAlchemy 2.0 eager-loaded `selectinload` query, crushing cold-start latency from ~250ms to ~20ms. A Redis-based async task queue eliminates races between the main request transaction and background extraction workers. All user input passes through a 4-step cryptographic sanitization pipeline before entering any prompt. Safety is enforced by a two-layer biomechanical defense: deterministic `SafetyMatrix` rule overrides before the LLM call, and substring-regex post-processing on LLM output regardless of model compliance.

---

## 2. High-Level Architecture Map

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              USER MESSAGE (Vietnamese text)                          │
│                                   sanitize_for_prompt()                             │
│                                      max_length=500                                 │
└──────────────────────────────────────────┬───────────────────────────────────────┘
                                           │
                    ┌──────────────────────▼──────────────────────┐
                    │         MultiAgentOrchestrator                 │
                    │   Keyword routing + depth mode selection       │
                    │   quick | deep | expert (ResponseDepth)        │
                    └──────────────────────┬─────────────────────────┘
                                           │
                    ┌──────────────────────▼──────────────────────┐
                    │  Phase 1: HealthMonitorAgent (SEQUENTIAL)   │
                    │  ─────────────────────────────────────────  │
                    │  1. Rule-based urgent keyword scan          │
                    │  2. Negation + third-person false-positive   │
                    │  3. LLM health assessment (JSON schema)      │
                    │  4. MemoryWriteEngine: write body_snapshot    │
                    │     health_events → DB (row-level lock)       │
                    │  ⚠️ BLOCKS all Phase 2 agents until done     │
                    └──────────────────────┬─────────────────────────┘
                                           │
                    ┌──────────────────────▼──────────────────────┐
                    │  Phase 2: Specialist Agents (PARALLEL)    │
                    │  ─────────────────────────────────────────  │
                    │  ┌─────────────┐  ┌──────────────────┐    │
                    │  │ Nutrition   │  │ FitnessCoach     │    │
                    │  │ Advisor     │  │ (SafetyMatrix     │    │
                    │  │ ─────────  │  │  overrides pre-  │    │
                    │  │ Mode A:     │  │  LLM + substring  │    │
                    │  │ Mifflin-St  │  │  regex post-      │    │
                    │  │ Jeor macro  │  │  processing)     │    │
                    │  │ calculator  │  └────────┬─────────┘    │
                    │  │ Mode B:     │           │                │
                    │  │ Behavioral  │  ┌──────────▼─────────┐     │
                    │  │ empathy +  │  │  WebResearcher     │     │
                    │  │ root-cause │  │  (Tavily API +     │     │
                    │  │ analysis   │  │   Redis cache 24h) │     │
                    │  └──────┬─────┘  └──────────┬─────────┘     │
                    └─────────┼────────────────────┼────────────────┘
                              │  MemoryWriteEngine    │
                              │  (centralized write  │
                              │   authority, row-    │
                              │   level lock,       │
                              │   ownership validate)│
                              ▼                    ▼
                    ┌─────────────────────────────────────────────┐
                    │          PostgreSQL (Supabase)               │
                    │  ┌──────────┐  ┌────────────┐  ┌───────┐ │
                    │  │UserMemory│  │NutritionGoal│  │Progress│ │
                    │  │ (JSONB)  │  │             │  │  Log  │ │
                    │  └──────────┘  └────────────┘  └───────┘ │
                    └─────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────▼──────────────────────┐
                    │         Final AI Synthesis (Groq)             │
                    │    Groq streaming SSE → Frontend             │
                    └─────────────────────────────────────────────┘

 ┌─ OUT-OF-BAND PIPELINE (async, decoupled) ──────────────────────────────────────┐
 │  ExtractorAgent (Redis queue worker — runs AFTER request commit)              │
 │  ┌────────────────────────────────────────────────────────────────────────┐  │
 │  │  Text-to-Meal extraction    │  ConversationInsight upsert (SQL table)│  │
 │  │  Text-to-health-events        │  UpdateProposal records                  │  │
 │  │  Key facts, sore areas        │  (confirmed by user → data_writers.py)  │  │
 │  └────────────────────────────────────────────────────────────────────────┘  │
 │  Proposals emitted via SSE `update_proposal` event to frontend               │
 └────────────────────────────────────────────────────────────────────────────────┘
```

### Entry Points

| Endpoint | Protocol | Use Case |
|---|---|---|
| `POST /api/v1/ai/chat/stream` | SSE (Server-Sent Events) | Full streaming AI response with agent analysis |
| `POST /api/v1/ai/chat` | JSON | Non-streaming request (structured cards only) |

---

## 3. Advanced Multi-Agent Directory

### Agent Registry

| Agent Name | Authoritative Class & File Path | Trigger Condition / Routing Rules | Clinical Core Capabilities |
|---|---|---|---|
| **Orchestrator** | `MultiAgentOrchestrator` — `app/agents/multi_agent_orchestrator.py` | Keyword-based microsecond dispatch on `HEALTH_KEYWORDS`, `NUTRITION_KEYWORDS`, `FITNESS_KEYWORDS`, `RESEARCH_TRIGGERS`; also triggers on active unresolved health events | 2-Phase routing engine: sequential Phase 1 gate, parallel Phase 2 isolation; anti-loop clarification protection via Redis TTL; `MemoryWriteEngine` centralized write coordination; final Groq synthesis with 1500-token budgeted context |
| **Extractor** | `ExtractorAgent` — `app/agents/extractor_agent.py` | Deferred async execution via Redis BRPOP queue (runs after request commits); never runs inline with user request | Silent text-to-meal extraction (food names, calories, macros); text-to-health-events; key facts upsert; body snapshot merge; session summarization at 5+ messages; `ConversationInsight` SQL table upsert; `UpdateProposal` generation |
| **Health Monitor** | `HealthMonitorAgent` — `app/agents/health_monitor_agent.py` | Triggered when user message contains Vietnamese health keywords (`mệt`, `đau`, `tiêu chảy`, `chóng mặt`, etc.) OR when `UserMemory.health_events` has unresolved events | Phase 1 gatekeeper — MUST complete before any Phase 2 agent runs; rule-based urgent keyword scan with negation pattern matching (9 regex patterns); third-person report detection (14 Vietnamese family-relationship indicators); structured JSON health assessment (overall, energy, digestion, musculoskeletal, metabolic); fitness clearance output feeding SafetyMatrix; recovery event auto-resolution via keyword matching |
| **Nutrition Advisor** | `NutritionAdvisorAgent` — `app/agents/nutrition_advisor_agent.py` | Triggered on food/nutrition keywords OR fallback rule (messages < 30 chars get NutritionAdvisor to ensure response) | Two-path architecture: **Mode A** — algorithmic Mifflin-St Jeor macro calculator injected into prompt before LLM (BMR → TDEE → target calories → protein/carbs/fat); **Mode B** — behavioral clinical psychology analysis triggered by 17-pattern classifier (skipping meals, late-night eating, emotional sweet/savory, binge eating, disordered eating) with root-cause physiological explanation, empathy-first language, harm-reduction alternatives, and max 2 trigger-focused clarifying questions; allergen verification on all suggestions; clarification card emission for intent ambiguity (2–4 options) |
| **Fitness Coach** | `FitnessCoachAgent` — `app/agents/fitness_coach_agent.py` | Triggered on fitness keywords (`tập`, `gym`, `cardio`, `workout`, `bài tập`, etc.) | Two-layer biomechanical safety: **Layer 1** (pre-LLM) — `SafetyMatrix` deterministic exercise blocks from injury regions; **Layer 2** (post-LLM) — substring regex enforcement purges any escaped forbidden exercise from LLM output; illness-severity forced rest (`rest` type with empty exercises list); workout type decision tree based on clearance codes; workout recommendation JSON schema with `avoid_exercises`, `alternative_exercises`, `recovery_focus`, `schedule_adjustment` |
| **Web Researcher** | `WebResearcherAgent` — `app/agents/web_researcher_agent.py` | On-demand only — triggered by research keywords (`mới nhất`, `nghiên cứu`, `có thật không`, `khoa học`, `bằng chứng`, etc.) OR low-confidence topics (supplements, keto, intermittent fasting, etc.) | Real-first architecture: `AsyncTavilyClient` with domain whitelist (14 medical/trust nodes); `advanced` search depth; trusted source tiering (Tier 1: PubMed/WHO/CDC/Mayo/NIH; Tier 2: Healthline/Examine.com/Vinmec; Tier 3: SuckhoeDoiSong/BacSiDanang/WebMD); Redis atomic cache with 24h TTL per query per day; rate limit: 3 searches/user/day via `AgentRun` table count; automated `_ai_synthesis_fallback` with explicit `ai_synthesis_disclaimer` label when Tavily is unavailable or exhausted |

---

## 4. Production Database Infrastructure & Connection Pooling

### Dual Connection String Topology (Supabase PostgreSQL)

The system separates database connections into two tiers to prevent DDL locking and PgBouncer transaction-mode conflicts:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Supabase Cloud PostgreSQL                      │
│  ┌───────────────────────┐    ┌────────────────────────────┐  │
│  │  Direct Connection     │    │  PgBouncer Pooled (port    │  │
│  │  Port 5432            │    │  6543, transaction mode)    │  │
│  │  ─────────────────    │    │  ────────────────────────    │  │
│  │  DATABASE_URL         │    │  DATABASE_POOL_URL          │  │
│  │  (pgbouncer=false)   │    │  (?pgbouncer=true)          │  │
│  │  Reserved: Alembic     │    │  FastAPI runtime only        │  │
│  │  migrations ONLY       │    │  ⚠️ pool_pre_ping=DISABLED  │  │
│  └───────────────────────┘    └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Key rationale for `pool_pre_ping=False`:** When FastAPI uses PgBouncer in transaction mode, a `pool_pre_ping` health check (`SELECT 1`) taken from a PgBouncer-inactive connection causes PgBouncer to mark that connection as dead and drop it. This breaks the in-flight transaction. The system intentionally disables `pool_pre_ping` and relies on PgBouncer's own connection lifecycle management instead.

### Verified Pooling Metrics (`app/db/session.py`)

```python
pool_size=4          # Per-worker base connections
max_overflow=12      # Per-worker burst ceiling: 4 + 12 = 16
pool_recycle=1800    # 30 min — PgBouncer sessions expire at 60 min idle
pool_pre_ping=False  # PURPOSEFULLY DISABLED — prevents PgBouncer tx pollution
# Prepared statement cache disabled for asyncpg compatibility
connect_args={
    "statement_cache_size": 0,
    "max_cached_statement_lifetime": 0,
}
```

**Per-worker ceiling:** 16 connections × 4 workers = **64 max** (intentionally tight to Supabase free-tier 60-connection limit — adjust overflow or worker count for larger deployments).

### The N+1 Query Resolution (`app/agents/context_loader.py`)

The original context-loading pattern executed **6 sequential `SELECT` queries** per request (profile, memory, nutrition_goals, workout_plans, progress_logs, meal_logs), each introducing a separate round-trip latency of ~40–50ms over Supabase Singapore, totaling ~250ms cold-start for every agent call.

**Resolution:** Replaced with a single SQLAlchemy 2.0 eager-loaded query using `selectinload`:

```python
stmt = (
    select(User)
    .where(User.id == uid)
    .options(
        selectinload(User.profile),
        selectinload(User.memory),
        selectinload(User.nutrition_goals),
        selectinload(User.workout_plans),
        selectinload(User.progress_logs),
        selectinload(User.meal_logs),
    )
)
```

**Result:** Cold-start agent latency reduced from **~250ms → ~20ms**. The `FullUserContext` dataclass is assembled in Python from the eagerly-loaded relationships, with at-most 1 additional round-trip for relationship resolution.

---

## 5. Enterprise Security, Guardrails & Anti-Hallucination Matrix

### 5.1 Input Sanitization Pipeline (`app/core/sanitize.py`)

Every user message passes through `sanitize_for_prompt()` at the **orchestrator entry point** before entering any agent prompt. The 4-step cryptographic processing order is:

```
Step 1 ──► Unicode NFKC Normalization
            unicodedata.normalize("NFKC", text)
            Degrades homoglyphs: Cyrillic 'і' → Latin 'i'
            Half-width → full-width normalization
            Defeats mixed-script injection tricks

Step 2 ──► Control Character Strip
            re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
            Null bytes, vertical tabs, form feeds removed

Step 3 ──► Injection Pattern Regex Filters (ALL applied, order matters)
            INJECTION_PATTERNS list — 9 compiled regex patterns:
            • "ignore previous instructions" variants
            • "you are now" role-play injection
            • "<|...|>" special token injection (Llama)
            • "[INST]...[/INST]" instruction tag injection
            • "### instruction" markdown injection
            • XML tag injection (system/user/assistant)
            • Null byte sequences
            Each matched pattern → "[filtered]"

Step 4 ──► max_length Truncation (500 chars default)
            Truncation happens AFTER sanitization so boundary-spanning
            payloads cannot slip through the cut.
```

### 5.2 Biomechanical Safety Override (`app/agents/safety_matrix.py`)

The `FitnessCoachAgent` employs a **two-layer defense system** that operates regardless of LLM compliance:

**Layer 1 — Pre-LLM Deterministic Gate (`SafetyMatrix.evaluate()`)**

The `SafetyMatrix` class reads injury data from `HealthMonitorAgent` Phase 1 output and produces mandatory exercise blocks. The matrix covers **5 body regions × 6 region-specific block sets**:

| Body Region | Blocked Exercises | Safe Alternatives |
|---|---|---|
| Back / Spine (`_BACK_MATRIX`) | Barbell Squat, Deadlift, Overhead Press, Bent Over Row, Jump Squat | Leg Press (tựa lưng), Leg Extension, Lying Leg Curl, Romanian Deadlift |
| Shoulder / Rotator (`_SHOULDER_MATRIX`) | Bench Press, Plank, Push-up, Shoulder Press, Burpee | Incline Dumbbell Press, Knee Push-up, Lateral Raise, Face Pull |
| Knee / Ligament (`_KNEE_MATRIX`) | Jump Squat, Burpee, Lunge, Box Jump, Running | Goblet Squat, Leg Press, Hip Thrust, Đạp xe, Bơi lội |
| Wrist / Hand (`_WRIST_MATRIX`) | Push-up, Plank, Bench Press | Knee Push-up, Wall Push-up, Dumbbell Press, Machine Chest Press |
| Hip (`_HIP_MATRIX`) | Deadlift, Lunge, Hip Thrust nặng | Glute Bridge bodyweight, Clamshell, Goblet Squat |
| Illness / Cardio-limited (`_CARDIO_LIMITED`) | Running, HIIT, Burpee | Đi bộ nhẹ, Đạp xe chậm, Yoga stretch, Thở diaphragmatic |

Severity evaluation uses **mitigating qualifier** detection: phrases like `nhẹ`, `hơi`, `vừa`, `mild`, `hồi phục` reduce severe keywords to mild restrictions instead of forced rest.

**Layer 2 — Post-LLM Substring Regex Scrubbing (`_enforce_safety_result()`)**

After the LLM generates a response, `_enforce_safety_result()` runs a substring regex match across all exercise names in the output. This catches:

- **Emoji-stripped names**: "🏋️ Squat" → normalized → "Squat" → blocked
- **Synonyms**: "Gánh tạ" (Deadlift in Vietnamese) → blocked
- **Variants**: "Back Squat", "Squat lưng", "Barbell Squat nâng cao" → all blocked

The `forced_workout_type` from `SafetyMatrix` overrides the LLM's decision: if the matrix mandates `rest`, the exercise list is cleared, duration set to 0, and a clinical motivation string is injected.

### 5.3 Behavioral Classifier & Mode B JSON Schema (`app/agents/nutrition_advisor_agent.py`)

The system detects **6 distinct disordered eating patterns** via a **17-pattern regex array** mapping user queries:

| Category | Label | Example Patterns |
|---|---|---|
| `skipping_meals` | Bỏ bữa / Nhịn ăn | `bỏ bữa`, `nhịn đói`, `chưa ăn sáng` |
| `late_night_eating` | Ăn đêm | `ăn đêm`, `thèm đêm khuya`, `order đồ đêm` |
| `emotional_eating_sweet` | Thèm ngọt | `thèm ngọt`, `stress ăn`, `ăn bánh theo cảm xúc` |
| `emotional_eating_savory` | Thèm đồ chiên | `thèm đồ chiên`, `buồn nên ăn`, `ăn giải tỏa` |
| `binge_eating` | Ăn vô độ | `ăn quá nhiều`, `mất kiểm soát`, `ăn không no` |
| `disordered_eating` | Hạn chế cực đoan | `chỉ ăn rau thôi`, `sợ lên cân`, `nạp rồi thôi` |

**Anti-false-positive gate:** Objective reason keywords (`bận học`, `trễ giờ`, `bệnh`, `ốm`) within ±50 characters of a pattern match suppress the trigger — e.g., "bỏ bữa sáng vì bận học" is not flagged as disordered.

Mode B enforces a strict JSON response structure:

```json
{
  "needs_clarification": false,
  "behavioral_response": {
    "root_cause": "Cortisol và ghrelin tăng cao vào buổi tối khi stress kéo dài...",
    "empathy_statement": "Đây là phản ứng sinh lý, không phải lỗi ý chí...",
    "short_term_alternative": "Hạt điều 10g + trà gừng — giảm thèm ngọt tự nhiên",
    "clarifying_questions": [
      { "question": "Bạn thường cảm thấy thèm ngọt vào khung giờ nào?", "purpose": "trigger_identification" }
    ],
    "user_facing_text": "..."
  }
}
```

**Output Guardrails** (`app/agents/output_guardrails.py`): After LLM generation, `filter_prohibited_phrases()` mechanically replaces judgmental language (`"đừng ăn"`, `"bắt buộc phải nhịn"`, `"bạn có lỗi"`) with empathetic alternatives. `append_medical_disclaimer()` then injects a Vietnamese-language disclaimer — enforced at the Python layer, not relying on the LLM's compliance.

---

## 6. Live Search Architecture (`WebResearcherAgent`)

### Real-First Query Routing

```
User query ──► AI query distillation ──► Redis cache check (key: user_id + query + today)
                                              │
                           HIT ──► return cached findings
                           MISS ──► AsyncTavilyClient.search()
                                              │
                              results ──► AI summarize real content
                              no results / API error ──► _ai_synthesis_fallback
                                              │
                              findings ──► Redis SETEX (TTL=86400s) ──► return
```

**Tavily API call parameters:**
```python
client.search(
    query=search_query,
    max_results=5,
    search_depth="advanced",
    include_domains=TRUSTED_DOMAINS,  # 14 whitelisted medical/scientific domains
)
timeout=10.0,
```

**AI summarization constraint:** The Groq synthesis model is explicitly forbidden from inventing URLs or claims — it summarizes only the actual Snippets returned by Tavily. The `_ai_synthesis_fallback` mode prepends `ai_synthesis_disclaimer: "Thông tin này được tổng hợp từ kiến thức AI, không phải từ web search thực."` and is transparent about using only domain names (not full URLs).

### Two-Layer Financial Protection

1. **Redis atomic cache** — `cache_key = sha256(user_id:query:today)[:16]`, TTL = 86,400 seconds (24h). Same query on the same day returns the cached result without consuming Tavily quota.
2. **Hard rate limiter** — `count_agent_runs_today()` queries the `AgentRun` table: `SELECT COUNT(*) WHERE user_id = ? AND agent_name = 'web_researcher' AND created_at >= today_00:00`. If count >= 3, the agent returns a `rate_limited: True` payload and does not call Tavily.

### Trusted Source Domain Registry

| Tier | Domain | Type |
|---|---|---|
| 1 | `pubmed.ncbi.nlm.nih.gov` | Academic |
| 1 | `who.int` | Health Authority |
| 1 | `cdc.gov` | Health Authority |
| 1 | `mayoclinic.org` | Hospital |
| 1 | `nih.gov` | Health Authority |
| 2 | `healthline.com` | Health Media |
| 2 | `examine.com` | Nutrition Science |
| 2 | `vinmec.com` | Hospital (Vietnam) |
| 2 | `medicalnewstoday.com` | Health Media |
| 2 | `nutritionfacts.org` | Nutrition Media |
| 3 | `suckhoedoisong.vn` | Health Media (Vietnam) |
| 3 | `bacsidanang.vn` | Health Media (Vietnam) |
| 3 | `webmd.com` | Health Media |
| 3 | *(via Tavily include_domains)* | |

---

## 7. 2-Phase Execution Topology — Internal Mechanics

### Phase 1: Sequential Health Clearance (`app/agents/multi_agent_orchestrator.py`, lines 249–281)

```
Phase 1 always runs first — no Phase 2 agent is dispatched until Phase 1 completes.

Flow:
1. _needs_health_check(msg_lower, memory)
   → True if health keyword found OR unresolved health_events exist

2. HealthMonitorAgent().run(context, db)
   → asyncio.wait_for(timeout=depth_config.phase1_timeout)
   → depth_config.phase1_timeout: quick=0, deep=3.0s, expert=5.0s

3. On success: context.agent_results["health"] = health_result
   → apply_memory_updates("health_monitor", memory_updates, db)

4. On timeout/exception: _make_health_fallback(reason)
   → Returns conservative AgentResult with confidence=0.0
   → Synthesized into response with "⚠️ Health assessment unavailable" note

5. Initial session closed: await db.close()
   → All subsequent DB operations use session_factory (isolated sessions)
```

### Phase 2: Parallel Isolation (`app/agents/multi_agent_orchestrator.py`, lines 283–373)

```
Phase 2 dispatch: each agent runs in its own AsyncSession
  → prevents SQLAlchemy 2.0 AsyncSession concurrency violations

Each Phase 2 agent:
  → Generates responses and memory_proposals (read-only relative to memory)
  → Returns AgentResult with memory_updates dict
  → Orchestrator routes memory_updates through MemoryWriteEngine
  → MemoryWriteEngine.commit() is the SINGLE write point after Phase 2

DEEP mode disambiguation rule:
  if should_run_nutrition AND should_run_fitness:
      should_run_fitness = False  # nutrition takes priority in deep mode
```

### Centralized Write Engine (`app/agents/memory_service.py`)

`MemoryWriteEngine` is the **only entity** authorized to write to `UserMemory`. It enforces:

- **Field ownership map** — each of the 8 memory fields has exactly 1 canonical owner:
  ```
  body_snapshot        → health_monitor
  health_events        → health_monitor
  nutrition_memory     → nutrition_advisor
  fitness_memory       → fitness_coach
  key_facts            → extractor
  conversation_summary → extractor
  recent_meals         → extractor
  ```
- **Unauthorized writes are BLOCKED** (not silently dropped) — logged with agent name, field path, and owner.
- **Row-level locking** via `SELECT ... FOR UPDATE` on `UserMemory` — concurrent writes are serialized at the database level.
- **Optimistic locking** with `extraction_version` — conflicts detected and retried with exponential backoff + ±30% jitter.
- **Deep merge strategy** — new sore areas are merged additively (never replaced); key facts are upserted by text deduplication.

---

## 8. Configuration Reference

### Environment Variables (`apps/api/.env.production`)

```ini
# ── App ───────────────────────────────────────────────────────────────────────
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
VERSION=1.0.0

# ── Security — MUST change, minimum 32 characters ─────────────────────────────
SECRET_KEY=CHANGE_ME_USE_at_least_32_random_characters
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ── Database — Supabase ───────────────────────────────────────────────────────
#
# App runtime (port 6543 — pooled via PgBouncer, transaction mode):
#   postgresql+asyncpg://postgres:PASSWORD@db.PROJECT_REF.supabase.co:6543/postgres?sslmode=require
#
# Migrations (port 5432 — direct connection, no PgBouncer):
#   MIGRATION_DATABASE_URL=postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres?sslmode=require
#
# ⚠️ Password special characters MUST be URL-encoded:
#   @ → %40, # → %23, $ → %24, % → %25, & → %26, + → %2B, / → %2F, : → %3A, = → %3D, ? → %3F
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:6543/postgres?sslmode=require

# Alembic migrations ONLY — uses direct connection (port 5432)
MIGRATION_DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres?sslmode=require

# ── Redis ──────────────────────────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=20

# ── AI Providers ───────────────────────────────────────────────────────────────
AI_CHAT_PROVIDER=groq
AI_PLANNER_PROVIDER=groq
AI_MEAL_PROVIDER=gemini

GROQ_API_KEY=gsk_CHANGE_ME
GROQ_TEXT_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

GEMINI_API_KEY=AIza_CHANGE_ME
GEMINI_MODEL=gemini-2.5-flash

# ── Web Research (Tavily) ───────────────────────────────────────────────────
TAVILY_API_KEY=
TAVILY_ENABLED=true

# ── CORS — list real domains, NOT wildcard ─────────────────────────────────────
BACKEND_CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]

# ── Cache TTL ─────────────────────────────────────────────────────────────────
AI_CACHE_TTL_SECONDS=3600
FOOD_RECOGNITION_CACHE_TTL=86400
DAILY_PLAN_CACHE_TTL=43200
```

### Database Pool Settings (`app/core/config.py`)

| Setting | Value | Purpose |
|---|---|---|
| `DATABASE_POOL_SIZE` | 4 | Per-worker base connections |
| `DATABASE_MAX_OVERFLOW` | 12 | Per-worker burst ceiling (16 total) |
| `DATABASE_POOL_TIMEOUT` | 30 | Seconds to wait for a connection |
| `DATABASE_POOL_RECYCLE` | 1800 | 30 min — PgBouncer idle timeout is 60 min |
| `DATABASE_POOL_PRE_PING` | `False` | **Intentionally disabled** — prevents PgBouncer transaction pollution |
| `BACKGROUND_TASK_CONCURRENCY_LIMIT` | 4 | Bounded semaphore for all fire-and-forget tasks |

---

## 9. Installation & Local Deployment

### Prerequisites

- Python 3.12+
- Node.js 20+ (for frontend)
- PostgreSQL 16 or Supabase connection
- Redis 7+

### Step 1 — Environment Setup

```bash
cd apps/api

# Copy the production template
cp .env.production.example .env

# Edit .env with your actual credentials:
#   - DATABASE_URL (pooled, port 6543 for app runtime)
#   - MIGRATION_DATABASE_URL (direct, port 5432 for alembic)
#   - GROQ_API_KEY
#   - GEMINI_API_KEY
#   - TAVILY_API_KEY (optional — AI synthesis fallback works without it)
#   - REDIS_URL
```

### Step 2 — Install Dependencies

```bash
cd apps/api
pip install -r requirements.txt
```

### Step 3 — Database Migrations (Direct Port Only)

```bash
# ⚠️ IMPORTANT: Always run migrations via MIGRATION_DATABASE_URL (port 5432 direct)
# Never use the pooled DATABASE_URL for migrations — PgBouncer does not support DDL

export DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres?sslmode=require"
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "describe_your_change"
```

### Step 4 — Run the Development Server

```bash
cd apps/api

# Single worker (development)
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0

# Production cluster (4 workers, 1 per CPU core recommended)
uvicorn app.main:app \
  --workers 4 \
  --host 0.0.0.0 \
  --port 8000 \
  --worker-class uvicorn.workers.UvicornWorker
```

The extractor queue worker starts automatically inside each Uvicorn worker process via the `lifespan` context manager — **no separate process needed**.

### Step 5 — Docker Deployment

```bash
# From repository root
docker-compose up --build

# Or in background
docker-compose up -d --build
```

The `docker-compose.yml` orchestrates the API, web, and Redis services. Ensure `DATABASE_URL` and `MIGRATION_DATABASE_URL` point to your Supabase project in the `.env` file mounted into the API container.

### Step 6 — Verify the System

```bash
# Health check
curl http://localhost:8000/api/v1/health

# API docs (development only)
# http://localhost:8000/docs
# http://localhost:8000/redoc

# Production disables docs — set ENVIRONMENT=development to enable
```

---

## Key File Index

| File | Purpose |
|---|---|
| `app/agents/multi_agent_orchestrator.py` | Central routing engine — 2-phase execution, keyword dispatch, anti-loop |
| `app/agents/extractor_agent.py` | Silent information extraction — meals, health events, facts, proposals |
| `app/agents/health_monitor_agent.py` | Clinical triage — Phase 1 gatekeeper, urgent keyword scan, fitness clearance |
| `app/agents/nutrition_advisor_agent.py` | Mode A macro calculator + Mode B behavioral empathy classifier |
| `app/agents/fitness_coach_agent.py` | Safety-first trainer with two-layer biomechanical override |
| `app/agents/web_researcher_agent.py` | Real-first Tavily search with Redis cache and rate limiting |
| `app/agents/memory_service.py` | Centralized `MemoryWriteEngine` with field ownership and optimistic locking |
| `app/agents/context_loader.py` | Single-query eager-loaded user context loader (~20ms cold-start) |
| `app/agents/safety_matrix.py` | Deterministic injury-to-exercise block matrix |
| `app/agents/output_guardrails.py` | Post-LLM prohibited phrase filter + medical disclaimer injector |
| `app/core/sanitize.py` | 4-step input sanitization pipeline |
| `app/core/extractor_queue.py` | Redis BRPOP async task queue — deferred extraction |
| `app/core/background.py` | Semaphore-bounded background tasks + queue worker loop |
| `app/core/cache.py` | Redis cache abstraction with graceful degradation |
| `app/ai/circuit_breaker.py` | CLOSED / OPEN / HALF_OPEN circuit breaker per AI provider |
| `app/db/session.py` | SQLAlchemy 2.0 async engine with PgBouncer-safe pool config |
| `app/core/config.py` | Pydantic settings — dual DB URL, pool metrics, production validators |
| `app/agents/data_writers.py` | UpdateProposal record writers with biomedical floor/ceiling validation |
