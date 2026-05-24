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

### AI Chatbot (`/chat`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/chat/sessions` | List chat sessions | Required |
| POST | `/chat/sessions` | Create new session | Required |
| GET | `/chat/sessions/{id}/messages` | Get session messages | Required |
| POST | `/chat/sessions/{id}/messages` | Send message | Required |
| GET | `/chat/sessions/{id}/messages/stream` | SSE stream response | Required |

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
| `/chat/*/messages/stream` | 30/min per user |
| All other endpoints | 100/min per user |

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1640000000
```

## SSE Streaming Format

The chat streaming endpoint (`GET /chat/sessions/{id}/messages/stream`) uses Server-Sent Events (SSE).

### Event Types

```
event: card
data: {"type":"single_select","title":"Bạn muốn giảm bao nhiêu kg?","options":[...]}

data: Xin chào! Hãy cho tôi biết...

data: Tiếp theo, tôi khuyên bạn...

data: [DONE]

data: [ERROR] Đã có lỗi xảy ra
```

**Card events** fire when the system needs clarification. Multiple agents may suggest cards; the orchestrator returns the highest-priority one. Card types: `single_select`, `multi_select`, `rank`, `number_input`, `confirm`.

**Text deltas** are streamed as `data:` lines with incremental AI text.

**Stream completion** is signaled by `data: [DONE]`.

**Errors** are signaled by `data: [ERROR] <message>`.
