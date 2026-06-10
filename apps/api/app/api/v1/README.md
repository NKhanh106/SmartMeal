# API Endpoints (v1)

REST API for SmartMeal. All endpoints require JWT authentication unless marked public.

Base URL: `/api/v1`

## Authentication

Authentication uses Bearer JWT tokens. Access tokens expire after 24 hours, refresh tokens after 7 days.

```
POST /auth/login        → { access_token, refresh_token, token_type }
POST /auth/refresh      → { access_token, ... } (using refresh_token)
POST /auth/register     → { user, ... }
POST /auth/logout       → { message }
```

All protected endpoints require the header:
```
Authorization: Bearer <access_token>
```

Refresh tokens use rotation — each refresh issues a new pair and invalidates the old refresh token.

## Endpoint Reference

### Auth (`/auth`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/auth/register` | Create new account | Public |
| POST | `/auth/login` | Login, get tokens | Public |
| POST | `/auth/refresh` | Refresh access token | Public |
| POST | `/auth/logout` | Invalidate tokens | Required |

### User Profiles (`/profiles`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/profiles/me` | Get current user profile | Required |
| PUT | `/profiles/me` | Update profile | Required |
| PUT | `/profiles/me/health-conditions` | Update health conditions | Required |
| PUT | `/profiles/me/preferences` | Update preferences | Required |

### Meal Logs (`/meal-logs`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/meal-logs` | List meal logs | Required |
| POST | `/meal-logs` | Create meal log | Required |
| GET | `/meal-logs/{id}` | Get meal log | Required |
| PUT | `/meal-logs/{id}` | Update meal log | Required |
| DELETE | `/meal-logs/{id}` | Delete meal log | Required |
| GET | `/meal-logs/today` | Today's meals | Required |

Source field tracks how the meal was logged: `manual` (user entry), `chat_extraction` (AI extracted from chat), `chat_command` (AI logged via command).

### Nutrition Goals (`/nutrition-goals`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/nutrition-goals/active` | Get active goal | Required |
| POST | `/nutrition-goals` | Create goal | Required |
| PUT | `/nutrition-goals/{id}` | Update goal | Required |

### Nutrition Pending State (`/nutrition/pending`)

Meals extracted by the AI are stored as `PENDING` records and must be confirmed by the user.

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/nutrition/pending` | List pending meal logs awaiting user confirmation | Required |
| PATCH | `/nutrition/pending/{id}/confirm` | Confirm a pending meal (applies BMR floor + negative clamp + recalculates totals) | Required |

**PENDING State Lifecycle:**
1. `create_tracked_task(extractor_queue_worker_loop())` runs `ExtractorAgent` (Phase 3, Redis BRPOP queue) after HTTP response begins.
2. `ExtractorAgent` writes `MealLog` with `status=PENDING`, `total_calories=sum_of_items`, `source=chat_extraction`.
3. Frontend polls `GET /nutrition/pending` to surface `MealConfirmationCard` (with quantity stepper, macro grid).
4. User edits food items (quantity +/-) and clicks **"✓ Xác nhận lưu"**.
5. `PATCH /nutrition/pending/{id}/confirm` acquires `SELECT FOR UPDATE` row lock, applies per-item negative clamp (calories/protein/carb/fat ≥ 0), enforces BMR floor (total ≥ BMR × 1.0), recalculates totals, sets `status=APPROVED`.

**BMR Floor (D-2 / D-3):**
The `confirm_pending_meal_log()` service function queries all APPROVED meals for the same user on the same date and rejects the confirmation if the projected daily total would fall below `1.0 × BMR`. This prevents under-eating which is dangerous for sustained weight loss.

**Negative Clamp (D-5):**
Before summing, each field (`calories`, `protein_g`, `carb_g`, `fat_g`) is clamped to `max(value, 0.0)`. This prevents a single malicious item from inflating totals or bypassing the floor check.

### Dashboard (`/dashboard`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/dashboard/daily?date=` | Daily nutrition summary | Required |
| GET | `/dashboard/weekly?end_date=` | 7-day nutrition summary | Required |

### Food Nutrition (`/food-nutrition`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/food-nutrition/search?q=` | Search USDA food database | Required |
| GET | `/food-nutrition/{id}` | Get food details | Required |

### Workout Plans (`/workout-plans`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/workout-plans` | List workout plans | Required |
| POST | `/workout-plans` | Create plan | Required |
| GET | `/workout-plans/{id}` | Get plan | Required |
| PUT | `/workout-plans/{id}` | Update plan | Required |

### Progress Logs (`/progress-logs`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/progress-logs` | List progress entries | Required |
| POST | `/progress-logs` | Create entry | Required |

### AI Chatbot (`/ai/chat`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/ai/chat/sessions` | List chat sessions | Required |
| POST | `/ai/chat/sessions` | Create new session | Required |
| GET | `/ai/chat/sessions/{id}/messages` | Get session messages | Required |
| POST | `/ai/chat/sessions/{id}/messages` | Send message | Required |
| POST | `/ai/chat/sessions/{id}/messages/stream` | SSE stream response | Required |

### AI Daily Planner (`/ai/daily-planner`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/ai/daily-planner/generate` | Generate daily plan | Required |

### AI Meal Update (`/ai/meal-update`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/ai/meal-update` | Suggest meal modifications | Required |

### Uploads (`/uploads`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/uploads/image` | Upload food image | Required |
| DELETE | `/uploads/{id}` | Delete uploaded image | Required |

### Admin Agents (`/admin/agents`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/admin/agents/runs?user_id=` | Agent run history | Admin |
| GET | `/admin/agents/stats` | Aggregate agent stats | Admin |

## Response Format

### Success

```json
{
  "id": "uuid",
  "email": "user@example.com"
}
```

### Error

```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE"
}
```

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/auth/login` | 10/min per IP |
| `/auth/register` | 5/min per IP |
| `/ai/chat/sessions/*/messages/stream` | 30/min per user |
| All other endpoints | 100/min per user |

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1640000000
```

## SSE Streaming Format

The chat streaming endpoint (`POST /ai/chat/sessions/{id}/messages/stream`) uses Server-Sent Events (SSE).

### Event Types

| Event | Format | Description |
|---|---|---|
| `event: depth` | `event: depth\ndata: {depth}\n\n` | Depth mode indicator (quick/deep/expert) |
| `event: agent_result` | `event: agent_result\ndata: {...}\n\n` | Per-agent structured output (health, nutrition, fitness, research) — consumed by SMA-Eval benchmark |
| `event: card` | `event: card\ndata: {...}\n\n` | Interactive confirmation card (priority 1–5) |
| `event: update_proposal` | `event: update_proposal\ndata: {...}\n\n` | Profile update proposal from ExtractorAgent Phase 3 |
| `data: {delta}` | `data: {"delta": "..."}\n\n` | Incremental AI text token |
| `data: {done}` | `data: {"done": true}\n\n` | Stream completion marker |
| `data: {error}` | `data: {"error": "..."}\n\n` | Error signal |

### Example SSE Stream

```
event: depth
data: deep

event: agent_result
data: {"agent": "health", "success": true, "content": {...}, "confidence": 0.85, "priority": 1}

event: agent_result
data: {"agent": "nutrition", "success": true, "content": {...}, "confidence": 0.92, "priority": 5}

event: card
data: {"card_id": "confirm", "title": "Xác nhận nhật ký ăn uống", ...}

data: {"delta": "Xin chào! Hãy cho tôi biết thêm về bữa sáng của bạn nhé..."}

data: {"done": true}
```

**Card priority:** Priority 1 (urgent health warning) > Priority 2 (mandatory profile) > Priority 3 (concerning health) > Priority 5 (clarification). The orchestrator returns the highest-priority card and halts the stream.

## Interactive Meal Confirmation Card (Frontend)

After the backend confirms a PENDING meal, the frontend renders a `MealConfirmationCard` component with the following behavior:

| UI Element | Behavior |
|---|---|
| Header | Shows meal type (bữa sáng/trưa/tối/an vặt) with emoji and AI confidence badge |
| Food item list | Each item shows name, per-unit macros, +/- quantity stepper |
| Macro grid | Real-time totals: Calories (kcal), Protein (g), Carbs (g), Fat (g) — recalculates on every quantity change |
| Confirm button | Calls `PATCH /nutrition/pending/{id}/confirm` with final `updated_data` |
| Cancel button | Returns to idle phase without any API call |
| Error banner | Shows HTTP error detail if confirm fails (e.g., BMR floor violation) |

Frontend polling: `useMealConfirmation` hook polls `GET /nutrition/pending` every 2s, max 5 attempts. State machine: `idle → loading → has_data → confirming → confirmed → idle`.
