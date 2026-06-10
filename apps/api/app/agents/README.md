# `app/agents/` — Multi-Agent System

## Module Overview & Domain Boundaries

This folder houses the entire multi-agent intelligence layer of SmartMeal's 3-Phase chatbot pipeline. It governs:

- **Phase 1 — Safety Gate (Sequential)**: `HealthMonitorAgent` performs urgent-keyword triage before any specialist response is emitted. Contains `MENTAL_HEALTH_CRISIS_KEYWORDS` hard-stop logic and rule-based negation/third-person filtering.
- **Phase 2 — Specialist Advisory (Parallel)**: `NutritionAdvisorAgent`, `FitnessCoachAgent`, and `WebResearcherAgent` each generate domain-specific recommendations in parallel, each in its own isolated `AsyncSession`.
- **Phase 3 — Deferred Extraction (Fire-and-Forget)**: `ExtractorAgent` runs via Redis `BRPOP` queue after the HTTP response begins. Writes `PENDING` MealLogs for frontend confirmation.
- **Orchestration**: `MultiAgentOrchestrator` routes requests, manages phase ordering, emits per-agent SSE `event: agent_result` for the SMA-Eval benchmark runner, and synthesises final responses.
- **Shared Infrastructure**: `BaseAgent` provides all agents with AI calls, retry logic, circuit-breaker integration, and `AgentRun` audit logging.
- **Memory Authority**: `memory_service` enforces field-level write ownership; `data_writers` translates user-confirmed `UpdateProposal`s into atomic DB writes.
- **Safety**: `safety_matrix` provides cross-agent injury-exercise guardrails; `output_guardrails` applies deterministic post-processing (medical disclaimers, prohibited-phrase filtering).

---

## File Registry & Critical Path Map

| File Path | Authoritative Component / Class | Inbound Dependencies | Core Technical Responsibility |
|---|---|---|---|
| `__init__.py` | Module re-exports | — | Exposes `AgentContext`, `AgentResult`, `BaseAgent`; `get_all_agents()`, `get_trigger_helpers()` |
| `base.py` | Backwards-compatible re-export | `base_agent.py` | Thin compat shim — forwards imports to `base_agent` |
| `base_agent.py` | `BaseAgent`, `AgentContext`, `AgentResult`, `AI_TIMEOUT_SECONDS=30` | `groq`, `tenacity`, `circuit_breaker`, `AgentRun` | Abstract agent base with AI call, retry (3-attempt exponential backoff), circuit-breaker, token tracking, `_log_start/_log_complete` for `AgentRun` audit rows |
| `context_loader.py` | `load_full_user_context()`, `FullUserContext`, `NutritionSnapshot`, `BodySnapshotData`, `FitnessSnapshotData` | SQLAlchemy `selectinload` eager loading | Single-query (6-relation `selectinload`) data loader for all agents; aggregates 7-day meal logs; computes `kcal_gap_today`, `kcal_adherence_7d`, weight trend; computes `profile_completeness` score |
| `data_writers.py` | `execute_confirmed_update()`, `DataWriteResult`, 9 writer functions | `UpdateProposal` schema, `MemoryWriteEngine`, `meal_service` | Translates user-confirmed proposals to DB writes; enforces biomedical floor/ceiling validation (D-2/D-3/A-5); calls `invalidate_user_plan_cache()` after every write |
| `depth_config.py` | `DepthConfig`, `DEPTH_CONFIGS`, `get_depth_config()`, `ResponseDepth` enum | — | Three depth tiers: `QUICK` (extractor only, 400 tokens), `DEEP` (4 agents, 500–700 tokens), `EXPERT` (5 agents, 800 tokens) with explicit timeout budgets per phase |
| `extractor_agent.py` | `ExtractorAgent` | `AgentContext`, `memory_service`, `proposal_builder`, `ConversationInsight` | Post-every-message extraction; `memory_write_engine` path; writes `ConversationInsight` records; session-summary at msg-count ≥ 5; triggers `_mark_session_extracted` |
| `fitness_coach_agent.py` | `FitnessCoachAgent` | `SafetyMatrix`, `get_memory_context_for_agent`, `output_guardrails` | Injury-safety gate (`apply_safety_overrides`) before LLM; forced `rest`/`light_activity` overrides for illness severity; regex substring block matching for exercise names; receives `is_elderly` demographic flag from orchestrator to block HIIT/Tabata |
| `health_monitor_agent.py` | `HealthMonitorAgent`, `MENTAL_HEALTH_CRISIS_KEYWORDS` | URGENT_KEYWORDS, NEGATION_PATTERNS, `_is_negated`, `_is_third_person_report` | Rule-based urgent triage (8+ keyword phrases) + negation + third-person filtering; `ASSESSMENT_SCHEMA` JSON output; `_resolve_matching_health_events` recovery auto-resolution; `MH_CRISIS_KEYWORDS` hard-stop emitting crisis card |
| `memory_service.py` | `MemoryWriteEngine`, `apply_memory_updates()`, `apply_memory_updates_with_retry()`, `MEMORY_OWNERSHIP`, `memory_write_engine()` | `UserMemory` model, optimistic lock (extraction_version), Redis queue | Field ownership map (Phase 1 HARD rule: each field has exactly 1 canonical writer); `get_or_create_memory` uses `SELECT FOR UPDATE`; retry with ±30% jitter backoff; `memory_write_engine()` factory for Phase 2 isolated writes |
| `multi_agent_orchestrator.py` | `MultiAgentOrchestrator`, `_make_health_fallback()` | All agents, `groq_circuit`, `load_full_user_context`, `MemoryWriteEngine`, `depth_config` | Keyword-based routing; Phase 1 `HealthMonitor` always runs first (blocking); Redis extractor queue via `create_tracked_task()` + `extractor_queue_worker_loop`; anti-loop clarification tracking (3 Redis keys per session); SSE event types: `depth`, `card`, `agent_result`, `update_proposal`, `delta`, `done` |
| `nutrition_advisor_agent.py` | `NutritionAdvisorAgent` | `calculate_macro_targets`, `VAGUE_NUTRITION_PATTERNS`, `BEHAVIORAL_EATING_PATTERNS` | Two-path AI schema (direct advice vs clarification card); Mode A behavioral eating classifier (6 categories, objective-reason suppressors); `MODE_A_TOOL`: `Mifflin-St Jeor` injection before LLM prompt (BMR floor ≥ 1.0 × BMR); allergen verification filter |
| `output_guardrails.py` | `append_medical_disclaimer()`, `filter_prohibited_phrases()`, `PROHIBITED_PHRASES` | — | Deterministic out-of-band enforcement; C-1: medical disclaimers per domain; C-3: 20 judgmental-phrase replacements |
| `proposal_builder.py` | `build_proposals_from_extraction()` | `UpdateProposal`, `UpdateTarget`, `FullUserContext` | Converts AI extraction dict → `UpdateProposal` list; `confidence ≥ 0.7` gate; meal-type inference by hour-of-day |
| `prompt_builder.py` | `build_health_monitor_context()`, `build_nutrition_advisor_context()`, `build_fitness_coach_context()`, `build_orchestrator_summary()` | `FullUserContext` dataclasses | Per-agent context string builders; 12 adherence-ratio thresholds; CONDITION_RULES mapping; injury-safety rule string builders |
| `safety_matrix.py` | `SafetyMatrix`, `apply_safety_overrides()`, `_REGION_MATRIX` | `_CLEARANCE_TO_REGION` | 6 body-region matrices (back, shoulder, knee, wrist, hip, cardio-limited); 4-tier severity check with mitigating-qualifier suppression; `forced_workout_type` propagation |
| `web_researcher_agent.py` | `WebResearcherAgent` | `TavilyClient`, `groq_circuit`, rate-limit helpers | Tavily-first, AI-synthesis fallback; 3 searches/day/user rate limit via `AgentRun` count; 15-domain trusted-source whitelist; `SOURCE_QUALITY` tier metadata; SHA256 cache key (daily, per-user) |

---

## Local Invariants & Production Logic Rules

### Phase 1 / 2 / 3 Separation
- **Phase 1** (`HealthMonitor`): Runs in the initial `AsyncSession` **before** `db.close()`. Its writes commit atomically with the session. Emits `event: agent_result` via SSE for SMA-Eval.
- **Phase 2** (`NutritionAdvisor`, `FitnessCoach`, `WebResearcher`): Each runs in an **isolated session** from `session_factory` inside `asyncio.Task`. All Phase 2 writes are routed through **one** `MemoryWriteEngine` instance committed after all agents complete. Emits `event: agent_result` via SSE for SMA-Eval.
- **Phase 3** (`ExtractorAgent`): Runs via Redis queue (`LPUSH`/`BRPOP`) **after** the HTTP response begins, in a separate transaction via `create_tracked_task(extractor_queue_worker_loop())`. Writes `PENDING` MealLog records with `total_calories=sum_of_items` for frontend confirmation. Proposals are drained via SSE `event: update_proposal`.

### Memory Field Ownership (Phase 1 HARD Rule)
```
body_snapshot         → health_monitor    conversation_summary → extractor
health_events        → health_monitor    recent_meals         → extractor
nutrition_memory      → nutrition_advisor  key_facts           → extractor
fitness_memory        → fitness_coach
```
Unauthorized writes are **BLOCKED** (hard, not silently dropped). SUPER_AGENTS (`orchestrator`, `data_writer`, `None`) bypass all checks.

### Safety Matrix Rules
| Region | Blocked | Alternatives |
|---|---|---|
| back / lower_back / spine | Barbell Squat, Deadlift, Overhead Press, Bent Over Row, Jump Squat | Leg Press, Leg Extension, Romanian Deadlift |
| shoulder / shoulders | Bench Press, Plank, Push-up, Shoulder Press, Burpee | Incline DB Press, Knee Push-up, Lateral Raise |
| knee / knees | Jump Squat, Burpee, Lunge, Box Jump, Running | Goblet Squat, Leg Press, Cycling, Swimming |
| wrist | Push-up, Plank, Bench Press | Wall Push-up, DB Press, Machine Chest Press |
| hip | Deadlift, Lunge, Hip Thrust (heavy) | Bodyweight Hip Thrust, Glute Bridge, Clamshell |
| cardio_limited / illness | Running, HIIT, Burpee | Walking, Stretching, Diaphragmatic breathing |
| **elderly (age >= 65)** | **HIIT, Tabata** | Low-intensity cardio, walking, yoga |

### Biomedical Validation Floor/Ceiling (data_writers + nutrition_math)
| Field | Floor | Ceiling |
|---|---|---|
| Body weight | 20.0 kg | 300.0 kg |
| Daily calories | 1.0 × BMR kcal (MINIMUM_CALORIE_FLOOR_FACTOR = 1.0) | 6,000 kcal |
| Protein | — | 300 g |
| Fat | — | 200 g |
| Carbohydrate | — | 900 g |
| Hydration | 500 ml | 10,000 ml |

### Behavioral Eating Pattern Detection (NutritionAdvisor)
Six categories with objective-reason suppression keywords: `bận`, `bận học`, `họp`, `bệnh`, `thỉnh thoảng`, etc. — prevents false positives from scheduling/health mentions.

### Depth Mode Token Budgets
| Mode | Extractor | Health | Nutrition | Fitness | WebResearch | Final |
|---|---|---|---|---|---|---|
| QUICK | 400 | 0 | 0 | 0 | 0 | 400 |
| DEEP | 600 | 500 | 600 | 500 | 0 | 700 |
| EXPERT | 800 | 800 | 800 | 800 | 800 | 1,200 |

---

## Intra-Module Request Flow

### Full Depth Request Lifecycle (DEEP/EXPERT)

```
HTTP Request
    │
    ▼
MultiAgentOrchestrator.process()
    │
    ├─► sanitize_for_prompt(message)          ← Input sanitisation (4-step)
    │
    ├─► load_full_user_context()             ← Single eager query (6 relations)
    │       Returns FullUserContext dataclass
    │
    ├─► create_tracked_task(extractor_queue_worker_loop())
    │       ← Phase 3: deferred extraction (runs AFTER response begins)
    │
    ├─► AgentContext + depth_config built
    │
    ├─► [PHASE 1] HealthMonitorAgent.run()
    │       └─► _is_negated() / _is_third_person_report()   ← Urgent keyword gate
    │       └─► Groq AI → ASSESSMENT_SCHEMA JSON
    │       └─► _build_memory_updates()
    │       └─► apply_memory_updates(agent_name="health_monitor")
    │       └─► AgentRun.status="completed" logged
    │       └─► yield "event: agent_result\ndata: {...}\n\n"  ← SSE for SMA-Eval
    │       db.close()
    │
    ├─► [PHASE 2] asyncio.wait([Task])  ← each in isolated AsyncSession
    │       │
    │       ├─► NutritionAdvisorAgent.run()  ──► Groq AI (Mode A/B schema)
    │       │                                  ├─► calculate_macro_targets() [Mode A]
    │       │                                  ├─► classify_behavioral_pattern() [Mode B]
    │       │                                  └─► MemoryWriteEngine.apply()
    │       │       └─► yield "event: agent_result\ndata: {...}\n\n"
    │       │
    │       ├─► FitnessCoachAgent.run()    ──► Groq AI + SafetyMatrix overrides
    │       │                                  └─► MemoryWriteEngine.apply()
    │       │       └─► yield "event: agent_result\ndata: {...}\n\n"
    │       │
    │       └─► WebResearcherAgent.run() ──► Tavily search OR AI synthesis
    │                                          ├─► _filter_trusted_sources() (15 domains)
    │                                          └─► cache_set() (24h TTL)
    │       └─► yield "event: agent_result\ndata: {...}\n\n"
    │
    ├─► MemoryWriteEngine.commit()             ← Single atomic Phase 2 write
    │
    ├─► _get_highest_priority_card()           ← Priority 1/2/3/5 check
    │       └─► yield "event: card\ndata: {...}\n\n"  ← Confirmation card → STOP
    │
    ├─► _stream_final_response()              ← Groq streaming + save ChatMessage
    │       └─► yield "data: {delta: ...}\n\n"
    │
    └─► extractor_drain_proposals(SCAN pipeline) ← Proposals via SSE
            └─► yield "event: update_proposal\ndata: {...}\n\n"
```

### PHASE 3 — Extraction Queue (Separate Transaction)

```
Orchestrator.process()
    │
    ▼
create_tracked_task(extractor_queue_worker_loop())
    │
    ▼
HTTP response begins

extractor_queue_worker_loop()
    │
    ▼
BRPOP timeout=5s  ◄── blocks until LPUSH task available
    │
    ▼
ExtractorAgent.run()
    ├─► Groq AI → EXTRACTION_SCHEMA JSON
    ├─► build_proposals_from_extraction()
    ├─► MemoryWriteEngine.apply("extractor", memory_updates)
    ├─► extractor_enqueue_proposal()      ← Redis SETEX 600s
    │
    ├─► Create MealLog records
    │    status = MealLogStatus.PENDING
    │    total_calories = sum(item.calories for item in items)
    │    source = MealLogSourceType.chat_extraction
    │
    └─► db.commit()  ← Separate transaction from Phase 1/2
```

### SSE Event Types Emitted by Orchestrator

| Event | Trigger | Consumed by |
|---|---|---|
| `event: depth\ndata: {depth}\n\n` | After AgentContext built | Frontend (loading indicator) |
| `event: agent_result\ndata: {...}\n\n` | After each Phase 1/2 agent completes | SMA-Eval benchmark runner |
| `event: card\ndata: {...}\n\n` | Priority card suggested | Frontend (confirmation UI) |
| `event: update_proposal\ndata: {...}\n\n` | After final AI stream, draining queue | Frontend (profile update cards) |
| `data: {delta: ...}\n\n` | Token streaming | Frontend (chat bubble) |
| `data: {done: true}\n\n` | Stream complete | Frontend (end marker) |

### Extraction Queue Path (POST-commit)

```
extractor_queue_worker_loop()  ──► BRPOP (blocking)
    │
    ├─► ExtractorAgent.run()
    │       ├─► _build_extraction_context(last 2 turns)
    │       ├─► Groq AI → EXTRACTION_SCHEMA JSON
    │       ├─► build_proposals_from_extraction()
    │       ├─► MemoryWriteEngine.apply("extractor", ...)
    │       ├─► extractor_enqueue_proposal()      ← Redis SETEX 600s
    │       └─► upsert_conversation_insights()
    │
    └─► db.commit()
```

---

## Key Implementation Notes

- All AI calls go through `BaseAgent._call_ai()` which wraps `groq_circuit.call()` with `asyncio.timeout(30s)`.
- Tenacity retry: `stop_after_attempt(3)`, `wait_exponential(multiplier=1, min=2, max=30)` — only on `ConnectionError`, `TimeoutError`, `asyncio.TimeoutError`.
- `AgentRun` rows use `await asyncio.shield()` in the `finally` block to guarantee audit logging even on cancellation.
- Profile completeness score: `current_weight_kg×0.15 + height_cm×0.15 + usage_goal×0.20 + health_conditions×0.20 + sleep×0.15 + taste_prefs×0.15` → capped at 1.0.
- `_build_health_context` enforces a ~2000-char hard cap (~500 tokens at 4 chars/token).
- The `FullUserContext` body snapshot uses a **priority rule**: canonical data (`UserProfile`, `NutritionGoal`) overrides AI-extracted data for `weight_kg`.
- Elderly detection (`is_elderly`) is set when `age >= 65` in `detect_sensitive_demographics()` and blocks HIIT/Tabata in the orchestrator routing logic.
- `MINIMUM_CALORIE_FLOOR_FACTOR = 1.0` (from `nutrition_math.py`) means no deficit plan may go below BMR × 1.0.
