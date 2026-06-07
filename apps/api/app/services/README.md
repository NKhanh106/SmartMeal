# `app/services/` — Business Logic & Algorithmic Domain Layer

## Module Overview & Domain Boundaries

This folder implements the **business logic** of SmartMeal — the deterministic algorithms, data transformation pipelines, and domain-specific computations that sit between the API routes (controllers) and the database layer. It is the authoritative location for:

- **Nutrition mathematics**: BMR/TDEE/Macro calculations (Mifflin-St Jeor), deterministic and pure-Python.
- **Meal lifecycle management**: Creating meal logs, recalculating totals, managing meal items.
- **Daily recommendation generation**: AI-powered daily plan generation with cache stampede protection and dual-provider fallback.
- **Food matching pipeline**: Multi-stage fuzzy matching from raw food name to database records.
- **Meal extraction from chat**: AI-assisted passive and explicit meal command processing.
- **Dashboard aggregation**: Daily and weekly nutrition progress summaries.
- **Learning feedback loop**: Recording food corrections and inferring user preferences.
- **Conversation insight extraction**: AI-extracted key-value facts from chat history.
- **Constraint validation**: Rule-based validation of AI-generated recommendations.
- **Workout plan CRUD**: Full lifecycle management of workout plans and items.
- **Progress log CRUD**: Body measurement tracking.
- **AI call logging**: Structured audit trail for every AI provider invocation.

---

## File Registry & Critical Path Map

| File Path | Authoritative Component / Class | Inbound Dependencies | Core Technical Responsibility |
|---|---|---|---|
| `ai_log_service.py` | `create_ai_log()` | `AILog` model | Audit trail for AI calls; truncates raw responses to 500 chars to prevent DB bloat |
| `conversation_insights_service.py` | `extract_insights_from_conversation()`, `upsert_conversation_insights()`, `get_active_insights()` | `ConversationInsight` model, `AI_CHAT_PROVIDER` | AI-extracts key-value insights from chat; 10 s timeout wraps AI call; PostgreSQL upsert on `(user_id, key)` |
| `daily_recommendation_service.py` | `generate_daily_recommendation()`, `_regenerate_daily_plan()`, `upsert_daily_recommendation()`, `invalidate_user_plan_cache()` | `DailyRecommendation` model, `get_ai_provider`, `CacheLock`, `gemini_circuit`/`groq_circuit` | Cache-aside daily plan generation with stampede protection; primary/fallback AI provider routing; Redis SCAN for cache invalidation |
| `dashboard_service.py` | `get_daily_dashboard()`, `get_weekly_dashboard()`, `calculate_progress()`, `get_day_range()` | `MealLog`, `NutritionGoal`, `ZoneInfo` | Timezone-aware (Asia/Ho_Chi_Minh) dashboard aggregation; `Decimal` arithmetic; `selectinload(MealLog.items)` eager loading |
| `food_mapping_service.py` | `match_food_name()`, `score_candidates()`, `normalize_vietnamese()`, `tokenize()` | `FoodNutrition` model, `rapidfuzz`/`unidecode` | 5-stage fuzzy matching pipeline: exact ILIKE → normalized Vietnamese → Levenshtein + Jaccard scoring → learned correction; `MIN_MATCH_SCORE = 0.55`, `PARTIAL_MATCH_SCORE = 0.40` |
| `food_nutrition_service.py` | `calculate_nutrition_by_weight()` | `FoodNutrition` model | Per-item nutrition extrapolation: `value_per_100g × (weight_g / 100)`; optional fiber, sugar, sodium |
| `learning_service.py` | `record_food_correction()`, `get_learned_correction()`, `infer_user_preferences()`, `upsert_user_preferences()` | `FoodCorrection`, `UserPreferenceLearned` models | Feedback loop: records corrections, infers preferences from meal history (min 10 meals); confidence = `min(1.0, meals / 30)` |
| `meal_extraction_service.py` | `extract_meals_from_message()`, `process_meal_command()`, `detect_meal_command()` | `MealLog`/`MealItem` models, `AI_CHAT_PROVIDER` | Passive extraction (AI from chat) + active command parsing (regex); batch duplicate check; unit-to-gram mapping; `infer_meal_type_from_time()` by hour bucket |
| `meal_service.py` | `create_meal_log_with_items()`, `recalculate_meal_totals()`, `calculate_item_nutrition()` | `MealLog`/`MealItem`/`FoodNutrition` models | N+1 prevention via batch food fetch; `Decimal` arithmetic; negative clamp on totals (D-5 fix); flush-per-item cascade |
| `nutrition_math.py` | `calculate_macro_targets()`, `calculate_bmr()`, `calculate_tdee()`, `calculate_macros()` | — (pure Python) | **Mifflin-St Jeor**: `BMR = 10W + 6.25H - 5A + s`; golden-ratio macro split: protein = 2 g/kg, fat = 25%, carb = remainder; dynamic upper bounds; deficit clamped to `max(BMR, 1000)` |
| `nutrition_service.py` | `calculate_nutrition_targets()`, `calculate_bmr()`, `calculate_tdee()`, `_get_health_adjustments()` | `UserProfile`, `NutritionGoal` models | BMR/TDEE with health-condition macro adjustments; safe calorie floor (male ≥ 1500, female ≥ 1200); `BMI = W / H²` |
| `planner_constraint_engine.py` | `PlannerConstraints`, `validate_recommendation()`, `build_constraints_from_profile_and_goal()` | `UserProfile`, `NutritionGoal`, `DietTypeEnum` | Rule-based validation of AI output: calorie floor = `max(1200, daily_cal × 0.75)`, ceiling = `daily_cal × 1.15`; auto-corrects violations; yesterday-overconsumption tracking |
| `progress_log_service.py` | `create_or_update_progress_log()`, `get_user_progress_logs()`, `get_latest_progress_log()` | `ProgressLog` model | Upsert per `(user_id, log_date)`; date-keyed deduplication |
| `workout_service.py` | `create_workout_plan()`, `get_active_workout_plan()`, `add_workout_item()`, `update_workout_item()` | `WorkoutPlan`/`WorkoutItem` models | Exactly one active plan per user (deactivate-other-on-activate); `selectinload(WorkoutPlan.items)`; `is_active` toggle with cascade deactivation |

---

## Local Invariants & Production Logic Rules

### Mifflin-St Jeor Equation (`nutrition_math.py`)

```
BMR = 10 × weight_kg + 6.25 × height_cm − 5 × age + s

where s = +5   (male / nam / m)
      s = −161 (female / nam / nu)
```

### TDEE Activity Multipliers

| Activity Level | Multiplier |
|---|---|
| Sedentary | 1.200 |
| Light | 1.375 |
| Moderate | 1.550 |
| Active | 1.725 |
| Very Active | 1.900 |

### Goal Adjustment Constants

| Goal | Adjustment |
|---|---|
| Deficit | −500 kcal (clamped to `max(BMR, 1000)`) |
| Surplus | +300 kcal |
| Maintain | TDEE (no change) |

### Macro Split — Golden-Ratio, Vietnamese/Asian Tuned

```
Protein_g  = weight_kg × 2.0 g/kg
Fat_kcal   = target_calories × 0.25
Fat_g      = Fat_kcal / 9
Carb_kcal  = target_calories − Protein_kcal − Fat_kcal
Carb_g     = max(Carb_kcal, 0) / 4
```

### Upper Sanity Bounds (`nutrition_math.py`)

| Field | Upper Bound | Dynamic Override |
|---|---|---|
| `target_calories` | 6,000 kcal | `max(6000, BMR × 1.5)` for hyper-obesity |
| `protein_g` | 300 g/day | — |
| `fat_g` | 200 g/day | — |
| `carb_g` | 900 g/day | — |

### Food Matching Score Thresholds

| Score | Status | Action |
|---|---|---|
| ≥ 0.55 | `matched` | Use as primary match |
| 0.40–0.54 | `partial` | Offer as alternative |
| < 0.40 | `not_found` | No match returned |

### Food Matching Score Formula

```
combined_score = (max(lev_primary, lev_vi, lev_en) × 0.6) + (jaccard × 0.4)

Boost rules:
  - Verified food:  ×1.05
  - Exact normalized substring: +0.1
  - Capped at 1.0
```

### Weight Unit Mapping (`meal_extraction_service.py`)

| Unit | Grams |
|---|---|
| `bowl` | 300 g |
| `plate` | 400 g |
| `piece` | 50 g |
| `slice` | 30 g |
| `serving` | 150 g (default) |
| `cup` | 240 g |
| `glass` | 250 g |
| `can` | 330 g |
| `bottle` | 500 g |
| `spoon / tbsp / tsp` | 15 / 15 / 5 g |
| `kg / l` | 1000 g |

### Dashboard Timezone Handling

- All queries use `Asia/Ho_Chi_Minh` (`+07:00`) as canonical timezone.
- `get_day_range(date)`: midnight local → next-day midnight local → UTC bounds.
- `selectinload(MealLog.items)` eager loads prevent N+1 on meal item reads.
- `Decimal` precision maintained throughout; rounded to 2 decimal places at display boundary.

### Planner Constraint Floors & Ceilings

```
calorie_min = max(1200, daily_cal × 0.75)    ← never below 1200 or 75% of target
calorie_max = daily_cal × 1.15                 ← never above 115% of target

If yesterday exceeded target:
  calorie_max = min(calorie_max, daily_cal × 1.05)

Protein per kg:
  tang_co  → 2.0 g/kg
  giam_can → 2.2 g/kg
  giu_can  → 1.8 g/kg

Protein range: ±20% of target
Carb range:   −30% / +30% of target
Fat range:    ±20% of target
```

### AI Call Logging Truncation

- `raw_response` field capped at **500 characters** (`MAX_RAW_RESPONSE_LEN = 500`).
- Full JSON blobs are never stored; only a debug summary.

### Learning Service Confidence

```
preference_confidence = min(1.0, meals_analyzed / 30)
correction_consistency = min(1.0, correction_count / 3)
```

### Conversation Insight Timeout

- AI insight extraction wrapped in `asyncio.wait_for(timeout=10s)`.
- On timeout: logs warning, returns `ExtractedInsightsOutput(insights=[], has_new_information=False)`.
- Never propagates to break the chat response.

---

## Intra-Module Request Flow

### Meal Log Creation Flow

```
API Route (POST /meal-logs)
    │
    ▼
create_meal_log_with_items()
    │
    ├─► Validate NutritionGoal (user ownership)
    │
    ├─► Batch-fetch all FoodNutrition by ID list  ← N+1 prevention
    │
    ├─► For each item payload:
    │    ├─► calculate_item_nutrition(food, weight_g)  ← Decimal ratio math
    │    ├─► Create MealItem ORM object
    │    └─► db.add()  (no commit yet — flush only)
    │
    ├─► Sum all item nutrition → MealLog totals
    │
    └─► db.flush() → return MealLog
         │
         ▼
    API Route calls db.commit()
```

### Daily Plan Generation Flow

```
GET /daily-recommendations
    │
    ▼
generate_daily_recommendation()
    │
    ├─► cache_get(cache_key) → HIT:
    │    ├─► _trigger_early_expiry_refresh()  (if TTL < 10% of 43,200 s)
    │    └─► get_recommendation_by_date()  ──► DB → return
    │
    └─► cache_get() → MISS:
         ├─► get_or_regenerate_with_lock()
         │    │
         │    ├─► Redis SET NX (TTL=60 s, 3 jittered retries)
         │    │    ├─► Lock acquired → double-check cache
         │    │    │    ├─► HIT  → return cached
         │    │    │    └─► MISS → _regenerate_daily_plan()
         │    │    └─► Lock timeout → regenerate WITHOUT caching
         │    │
         │    └─► cache_set(cache_key, result, TTL=43,200)
         │
         ├─► _regenerate_daily_plan():
         │    ├─► build_daily_planner_context()  (profile, goal, dashboard)
         │    ├─► Primary AI call (gemini or groq, per settings)
         │    ├─► On failure → fallback to other provider
         │    ├─► create_ai_log()  (truncated raw_response ≤ 500 chars)
         │    ├─► upsert_daily_recommendation()  (DB upsert by user+date)
         │    └─► db.commit() → return
         │
         └─► get_recommendation_by_date()  ──► DB → return
```

### Food Matching Pipeline (`match_food_name`)

```
match_food_name(food_name)
    │
    ▼
normalize_vietnamese(food_name)  ──► "com tam suon bi cha"
    │
    ├─► Stage 1: search_food_exact()  ──► ILIKE on food_name, food_name_vi, food_name_en
    │    └─► Candidates found?
    │         ├─► YES → score_candidates() → Levenshtein + Jaccard weighted scoring
    │         └─► NO  → Stage 3: fetch 500 verified foods → score_candidates()
    │
    ├─► Top candidate score ≥ 0.55?  → match_status = "matched"
    ├─► Top candidate score ≥ 0.40?  → match_status = "partial"
    └─► Otherwise                       match_status = "not_found"

score_candidates():
    lev_primary = Levenshtein(search_norm, food_norm)
    lev_vi      = Levenshtein(search_norm, food_vi_norm)
    lev_en      = Levenshtein(search_norm, food_en_norm)
    lev_best    = max(lev_primary, lev_vi, lev_en)

    jaccard     = Jaccard(search_tokens, food_tokens)

    combined    = (lev_best × 0.6) + (jaccard × 0.4)
    if verified: combined = min(1.0, combined × 1.05)
    if substring: combined = min(1.0, combined + 0.1)
```
