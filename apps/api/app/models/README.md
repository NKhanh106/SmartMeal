# Database Models

SQLAlchemy 2.0 async ORM models for SmartMeal. PostgreSQL 16 with JSONB for flexible health/nutrition data.

## Technology

### SQLAlchemy 2.0 Async

All models use the SQLAlchemy 2.0 declarative style with `Mapped[]` type annotations. Async sessions (`AsyncSession`) are used throughout for non-blocking database operations, which is critical for FastAPI's concurrent request handling.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

async with AsyncSessionLocal() as session:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
```

Relationships are loaded with `selectinload` to avoid N+1 queries:

```python
result = await session.execute(
    select(MealLog).options(selectinload(MealLog.items))
    .where(MealLog.user_id == user_id)
)
```

### PostgreSQL JSONB

PostgreSQL JSONB columns store health conditions, body snapshots, and health events because these schemas evolve frequently and don't fit cleanly into a fixed relational schema.

```python
# Example: health_conditions stored as JSONB
health_conditions: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

# GIN index for efficient JSONB querying
Index("ix_user_memory_health_events", "health_events", postgresql_using="gin")
```

Deep-merge is required when updating JSONB columns — simple `.update()` would replace the entire JSON object rather than merging individual fields. The `memory_service.py` handles this with recursive dict merging.

## Schema Overview

```
User (1) ──────────────── (1) UserProfile
  │                              │ usage_goal, activity_level
  │                              │ health_conditions (JSONB)
  │                              │ taste_preferences (JSONB)
  │
  ├── (many) NutritionGoal
  ├── (many) MealLog ──── (many) MealItem
  ├── (many) WorkoutPlan ── (many) WorkoutItem
  ├── (many) ProgressLog
  ├── (many) ChatSession ── (many) ChatMessage
  │                              │ card (JSONB)
  │                              │ card_response (JSONB)
  │                              │ message_type
  ├── (1) UserMemory
  │         body_snapshot (JSONB)
  │         health_events (JSONB[])
  │         nutrition_memory (JSONB)
  │         fitness_memory (JSONB)
  │         key_facts (JSONB[])
  │
  ├── (many) AgentRun
  ├── (many) AgentInsight
  └── (many) DailyRecommendation
```

## Model Reference

### `User`

Core authentication table.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `email` | String | Unique, indexed |
| `hashed_password` | String | bcrypt hashed |
| `full_name` | String | |
| `role` | Enum | `user`, `admin` |
| `is_active` | Boolean | Soft delete flag |
| `last_activity_at` | DateTime | Updated on each API call |

### `UserProfile`

Extended user data for nutrition and fitness. One per user.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | UUID FK | References User |
| `gender` | Enum | `male`, `female`, `other` |
| `date_of_birth` | Date | Used for BMR calculation |
| `height_cm` | Float | |
| `current_weight_kg` | Float | |
| `current_body_fat_percent` | Float | Optional |
| `activity_level` | Enum | sedentary → very_active |
| `diet_type` | Enum | balanced, low_carb, high_protein, etc. |
| `usage_goal` | Enum | weight_loss, muscle_gain, maintenance, etc. |
| `allergies` | JSONB | List of `{allergen, severity}` objects |
| `health_conditions` | JSONB | List of `{condition, severity}` objects |
| `medications` | JSONB | List of `{name, frequency}` objects |
| `taste_preferences` | JSONB | `{spicy: 1-5, sweet: 1-5, ...}` |
| `cuisine_preferences` | JSONB | List of cuisine names |
| `sleep_duration_hours` | Float | |
| `sleep_quality` | Enum | poor, fair, good, excellent |
| `stress_level` | Integer | 1-10 |

### `MealLog`

A meal entry for a specific date and meal type.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `user_id` | UUID FK | |
| `meal_type` | Enum | breakfast, lunch, dinner, snack |
| `meal_time` | DateTime | When the meal was eaten |
| `total_calories` | Float | Calculated from items |
| `total_protein_g` | Float | |
| `total_carb_g` | Float | |
| `total_fat_g` | Float | |
| `source` | Enum | `manual`, `chat_extraction`, `chat_command` |
| `items` | Relationship | One-to-many → MealItem |

### `MealItem`

Individual food item within a meal log.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `meal_log_id` | UUID FK | |
| `food_name` | String | Name from food database or user entry |
| `food_id` | UUID FK | References FoodNutrition (nullable) |
| `serving_size_g` | Float | |
| `calories` | Float | |
| `protein_g` | Float | |
| `carb_g` | Float | |
| `fat_g` | Float | |

### `UserMemory`

One row per user — stores the persistent AI context. All knowledge the AI has about the user.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | UUID PK FK | |
| `body_snapshot` | JSONB | Current physical state |
| `health_events` | JSONB[] | Append-only event log |
| `nutrition_memory` | JSONB | Eating patterns |
| `fitness_memory` | JSONB | Workout history |
| `key_facts` | JSONB[] | Stable facts (upserted) |
| `conversation_summary` | Text | Rolling summary |
| `last_extraction_at` | DateTime | When extractor last ran |

### `ChatSession`

A chat conversation session.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `user_id` | UUID FK | |
| `title` | String | Auto-generated or user-provided |
| `created_at` | DateTime | |

### `ChatMessage`

Individual message within a chat session.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `session_id` | UUID FK | |
| `role` | Enum | `user`, `assistant` |
| `content` | Text | Message content |
| `message_type` | Enum | `text`, `card`, `system` |
| `card` | JSONB | Card data (if message_type=card) |
| `card_response` | JSONB | User's response to the card |
| `token_count` | Integer | Estimated tokens used |

### `NutritionGoal`

Daily macro targets for a user.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `user_id` | UUID FK | |
| `goal_type` | Enum | `cutting`, `maintaining`, `bulking` |
| `daily_calorie_target` | Float | |
| `protein_target_g` | Float | |
| `carb_target_g` | Float | |
| `fat_target_g` | Float | |
| `is_active` | Boolean | Only one active goal at a time |

### `WorkoutPlan` / `WorkoutItem`

Workout plan with individual exercise items.

### `Exercise`

Exercise library — seeded from a pre-defined list. Used for autocomplete and exercise database.

### `ProgressLog`

Weight and measurement tracking over time.

### `AgentRun`

Audit log for every agent execution. Tracks agent name, user, duration, token usage, and success/failure.

### `DailyRecommendation`

AI-generated daily meal and workout suggestions. Refreshed periodically.

## Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply pending migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Check current version
alembic current

# Show migration history
alembic history
```

**Never delete migration files.** Deleting migrations breaks the migration history in environments where those migrations have already been applied. If a migration is incorrect, create a new one to fix the issue.
