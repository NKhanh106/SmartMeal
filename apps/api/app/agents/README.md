# `app/agents/` — Multi-Agent System

## Module Overview & Domain Boundaries

This folder houses the entire multi-agent intelligence layer of SmartMeal's 2-Phase chatbot pipeline. It governs:

- **Phase 1 — Extraction & Safety Gate**: `ExtractorAgent` silently extracts structured facts from every user message → `UserMemory`; `HealthMonitorAgent` performs urgent-keyword triage and health-state assessment before any specialist response is emitted.
- **Phase 2 — Specialist Advisory**: `NutritionAdvisorAgent`, `FitnessCoachAgent`, and `WebResearcherAgent` each generate domain-specific recommendations in parallel.
- **Orchestration**: `MultiAgentOrchestrator` routes requests, manages phase ordering, enforces depth-mode token budgets, and synthesises final responses.
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
| `fitness_coach_agent.py` | `FitnessCoachAgent` | `SafetyMatrix`, `get_memory_context_for_agent`, `output_guardrails` | Injury-safety gate (`apply_safety_overrides`) before LLM; forced `rest`/`light_activity` overrides for illness severity; regex substring block matching for exercise names |
| `health_monitor_agent.py` | `HealthMonitorAgent` | URGENT_KEYWORDS, NEGATION_PATTERNS, `_is_negated`, `_is_third_person_report` | Rule-based urgent triage (8 keyword phrases) + negation + third-person filtering; `ASSESSMENT_SCHEMA` JSON output; `_resolve_matching_health_events` recovery auto-resolution |
| `memory_service.py` | `MemoryWriteEngine`, `apply_memory_updates()`, `apply_memory_updates_with_retry()`, `MEMORY_OWNERSHIP` | `UserMemory` model, optimistic lock (extraction_version), Redis queue | Field ownership map (Phase 1 HARD rule: each field has exactly 1 canonical writer); `get_or_create_memory` uses `SELECT FOR UPDATE`; retry with ±30% jitter backoff |
| `multi_agent_orchestrator.py` | `MultiAgentOrchestrator`, `_make_health_fallback()` | All agents, `groq_circuit`, `load_full_user_context`, `MemoryWriteEngine`, `depth_config` | Keyword-based routing; Phase 1 `HealthMonitor` always runs first; Redis extractor queue (`LPUSH`/drain); anti-loop clarification tracking (3 Redis keys per session); SSE event types: `depth`, `card`, `update_proposal`, `delta`, `done` |
| `nutrition_advisor_agent.py` | `NutritionAdvisorAgent` | `calculate_macro_targets`, `VAGUE_NUTRITION_PATTERNS`, `BEHAVIORAL_EATING_PATTERNS` | Two-path AI schema (direct advice vs clarification card); Mode B behavioral eating classifier (6 categories, 12 objective-reason suppressors); `MODE_A_TOOL`: `Mifflin-St Jeor` injection before LLM prompt; allergen verification filter |
| `output_guardrails.py` | `append_medical_disclaimer()`, `filter_prohibited_phrases()`, `PROHIBITED_PHRASES` | — | Deterministic out-of-band enforcement; C-1: medical disclaimers per domain; C-3: 20 judgmental-phrase replacements |
| `proposal_builder.py` | `build_proposals_from_extraction()` | `UpdateProposal`, `UpdateTarget`, `FullUserContext` | Converts AI extraction dict → `UpdateProposal` list; `confidence ≥ 0.7` gate; meal-type inference by hour-of-day |
| `prompt_builder.py` | `build_health_monitor_context()`, `build_nutrition_advisor_context()`, `build_fitness_coach_context()`, `build_orchestrator_summary()` | `FullUserContext` dataclasses | Per-agent context string builders; 12 adherence-ratio thresholds; CONDITION_RULES mapping; injury-safety rule string builders |
| `safety_matrix.py` | `SafetyMatrix`, `apply_safety_overrides()`, `_REGION_MATRIX` | `_CLEARANCE_TO_REGION` | 6 body-region matrices (back, shoulder, knee, wrist, hip, cardio-limited); 4-tier severity check with mitigating-qualifier suppression; `forced_workout_type` propagation |
| `web_researcher_agent.py` | `WebResearcherAgent` | `TavilyClient`, `groq_circuit`, rate-limit helpers | Tavily-first, AI-synthesis fallback; 3 searches/day/user rate limit via `AgentRun` count; 15-domain trusted-source whitelist; `SOURCE_QUALITY` tier metadata; SHA256 cache key (daily, per-user) |

---

## Local Invariants & Production Logic Rules

### Phase 1 / Phase 2 Separation
- **Phase 1** (`HealthMonitor`): Runs in the initial `AsyncSession` **before** `db.close()`. Its writes commit atomically with the session.
- **Phase 2** (`NutritionAdvisor`, `FitnessCoach`, `WebResearcher`): Each runs in an **isolated session** from `session_factory` inside `asyncio.Task`. All Phase 2 writes are routed through **one** `MemoryWriteEngine` instance committed after all agents complete.
- **ExtractorAgent**: Runs via Redis queue (`LPUSH`/BRPOP) **after** the HTTP response commits. Proposals are drained via SSE after the final AI response.

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

### Biomedical Validation Floor/Ceiling (data_writers)
| Field | Floor | Ceiling |
|---|---|---|
| Body weight | 20.0 kg | 300.0 kg |
| Daily calories | 1,000 kcal | 6,000 kcal |
| Protein | — | 300 g |
| Fat | — | 200 g |
| Carbohydrate | — | 1,500 g (carb target) |
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
    ├─► sanitize_for_prompt(message)          ← Input sanitisation
    │
    ├─► load_full_user_context()               ← Single eager query (6 relations)
    │       Returns FullUserContext dataclass
    │
    ├─► extractor_enqueue(LPUSH to Redis)      ← Deferred extraction queue
    │
    ├─► AgentContext + depth_config built
    │
    ├─► [PHASE 1] HealthMonitorAgent.run()
    │       └─► _is_negated() / _is_third_person_report()   ← Urgent keyword gate
    │       └─► Groq AI → ASSESSMENT_SCHEMA JSON
    │       └─► _build_memory_updates()
    │       └─► apply_memory_updates(agent_name="health_monitor")
    │       └─► AgentRun.status="completed" logged
    │       db.close()
    │
    ├─► [PHASE 2] asyncio.wait([Task])
    │       │
    │       ├─► NutritionAdvisorAgent.run()  ──► Groq AI (Mode A/B schema)
    │       │                                  ├─► calculate_macro_targets() [Mode A]
    │       │                                  ├─► classify_behavioral_pattern() [Mode B]
    │       │                                  └─► MemoryWriteEngine.apply()
    │       │
    │       ├─► FitnessCoachAgent.run()    ──► Groq AI + SafetyMatrix overrides
    │       │                                  └─► MemoryWriteEngine.apply()
    │       │
    │       └─► WebResearcherAgent.run() ──► Tavily search OR AI synthesis
    │                                          ├─► _filter_trusted_sources() (15 domains)
    │                                          └─► cache_set() (24h TTL)
    │
    ├─► MemoryWriteEngine.commit()             ← Single atomic Phase 2 write
    │
    ├─► _get_highest_priority_card()           ← Priority 1/2/3/5 check
    │
    ├─► _stream_final_response()              ← Groq streaming + save ChatMessage
    │
    └─► extractor_drain_proposals(SCAN pipeline) ← Proposals via SSE
```

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
