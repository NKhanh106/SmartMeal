# `app/chatbot/` — Conversational AI Interface Layer

## Module Overview & Domain Boundaries

This folder implements the **conversational AI layer** of SmartMeal — the interface between the user-facing chatbot (web frontend) and the multi-agent backend. It governs:

- **Chat session lifecycle**: creation, pagination, soft-delete, title management.
- **Message persistence**: storing user/assistant messages with role and type discrimination.
- **Context assembly**: aggregating all user data into a structured prompt context for the AI.
- **Hard-rule card triggers**: deterministic profile-gated cards that fire before AI is consulted.
- **Streaming responses**: SSE-based streaming with AI-driven tool calls (`ask_user` card tool).
- **Card interaction flow**: handling card responses, profile updates, and AI resumption.
- **Prompt construction**: system prompts, user prompt templates, insight extraction prompts.
- **Chat title generation**: automatic session titling from first user message.

The chatbot does **not** own meal extraction or memory writing directly — those are dispatched as background tasks to the `ExtractorAgent` after every message turn.

---

## File Registry & Critical Path Map

| File Path | Authoritative Component / Class | Inbound Dependencies | Core Technical Responsibility |
|---|---|---|---|
| `service.py` | `send_chat_message()`, `process_streaming_message()`, `process_card_response_and_stream()`, `ASK_USER_TOOL` | `get_ai_provider`, `WebResearcherAgent`, `sanitize_for_prompt`, `build_chatbot_context` | Core chat handler (non-streaming + streaming); SSE yield; Groq `AsyncGroq` streaming; `ask_user` tool for AI-driven cards; session/msg persistence; `fired_triggers` state on session; `asyncio.timeout(60)` on all streams |
| `context_builder.py` | `build_chatbot_context()`, `build_health_context()`, `DEFAULT_CHATBOT_CONTEXT_POLICY` | `dashboard_service`, `conversation_insights_service`, `selectinload`, `sanitize_for_prompt` | Aggregates profile, goal, dashboards, meals, recommendations, insights, chat history into a single dict; sanitises every free-text field before prompt injection; 30-field profile serialisation |
| `prompts.py` | `CHATBOT_SYSTEM_PROMPT`, `build_chatbot_user_prompt()`, `INSIGHT_EXTRACTION_SYSTEM_PROMPT`, `build_insight_extraction_prompt()` | `json` stdlib | System prompt (Vietnamese); user prompt wrapping context as JSON (`json.dumps(ensure_ascii=False)`); insight extraction prompts |
| `card_triggers.py` | `check_hard_rule_triggers()`, `_is_nutrition_question()`, `_has_health_keywords()`, `_has_plan_keywords()` | `UserProfile`, `ChatCard` schema | 4 hard-rule triggers checked before AI: `missing_profile`, `missing_goal`, `missing_health_conditions`, `missing_weight`; `fired_triggers` prevents repeat; keyword lists per rule |
| `utils.py` | `build_chat_title()` | — | Auto-generates session titles from first message; max 6 words / 40 chars |
| `context_policy.py` | `ChatbotContextPolicy`, `DEFAULT_CHATBOT_CONTEXT_POLICY` | — | Token budget policy: `max_recent_meals=5`, `max_chat_history_messages=8`, `include_weekly_dashboard=True` |

---

## Local Invariants & Production Logic Rules

### Chat Session Pagination

- Cursor-based pagination on `last_message_at` / `updated_at` tie-break.
- Page size: `limit + 1` to detect `has_more`.
- Excludes `status = "deleted"` sessions.

### Hard-Rule Card Trigger Sequence

```
process_streaming_message()
    │
    ▼
check_hard_rule_triggers(user_message, profile, fired_triggers)
    │
    ├─► Rule 1: profile is None → "missing_profile" confirm card
    ├─► Rule 2: usage_goal is None + _is_nutrition_question() → goal select card
    ├─► Rule 3: health_conditions is None + _has_health_keywords() → health confirm card
    ├─► Rule 4: current_weight_kg is None + _has_plan_keywords() → weight number input card
    │
    └─► No match → proceed to Groq AI streaming
```

### Keyword Lists for Hard Rules

| Rule | Keywords |
|---|---|
| `_is_nutrition_question` | `ăn`, `uống`, `dinh dưỡng`, `thực đơn`, `calo`, `protein`, `giảm`, `tăng`, `chế độ`, `bữa`, `món`, `thực phẩm`, `gym` |
| `_has_health_keywords` | `tiểu đường`, `huyết áp`, `gout`, `thận`, `gan`, `dị ứng`, `bệnh`, `thuốc`, `điều trị`, `kiêng` |
| `_has_plan_keywords` | `thực đơn`, `kế hoạch ăn`, `calories`, `macro`, `bữa ăn cho` |

### AI-Driven Card Tool Schema (`ask_user`)

```json
{
  "name": "ask_user",
  "input_schema": {
    "card_type": "single_select | multi_select | rank | number_input | confirm",
    "title": "string (max 60 chars, Vietnamese)",
    "subtitle": "string (max 100 chars, optional)",
    "options": "[{id, label, icon}]",
    "unit": "string (number_input only)",
    "min_value": "number (number_input only)",
    "max_value": "number (number_input only)"
  }
}
```

Constraint: max **1 card per response**. On card fire, stream stops and waits for card response.

### Context Policy Limits

| Field | Default | Purpose |
|---|---|---|
| `max_recent_meals` | 5 | Recent meal logs in context |
| `max_chat_history_messages` | 8 | Chat history messages |
| `include_weekly_dashboard` | `True` | 7-day nutrition summary |
| `include_daily_recommendation` | `True` | Latest AI daily plan |
| `include_progress_logs` | `False` | Body measurements |

### Sanitisation Points in Context

Every free-text field passes through `sanitize_for_prompt()` before entering the AI prompt:

- All `UserProfile` free-text fields (nested JSONB values included).
- All `ConversationInsight` `summary` and `value` fields.
- All `ChatMessage.content` from history.
- The current `user_question` at entry point.

### Stream Timeout

All `AsyncGroq` streaming calls are wrapped in `asyncio.timeout(60)` — 60-second hard limit per turn.

### Card Response → Profile Field Mapping

| `trigger_reason` | Profile Field | Extractor |
|---|---|---|
| `missing_goal` | `usage_goal` | `selected_ids[0]` |
| `missing_weight` | `current_weight_kg` | `number_value` or `selected_ids[0]` as float |

### DB Session Safety in Streaming Responses

The `process_card_response_and_stream` path uses an outer `try/finally` to guarantee `_close_stream_db()` on every exit:

- Normal completion
- `asyncio.TimeoutError`
- `json.JSONDecodeError` on tool call
- Any exception

On abnormal SSE disconnect mid-stream, the session is rolled back before being returned to the pool, preventing poison state.

---

## Intra-Module Request Flow

### Streaming Chat Message Flow (Normal Path)

```
POST /chatbot/stream
    │
    ▼
process_streaming_message()
    │
    ├─► save_chat_message(role="user") → db.commit()
    │
    ├─► sanitize_for_prompt(user_content)
    │
    ├─► build_chatbot_context()
    │    ├─► select UserProfile
    │    ├─► select NutritionGoal (active)
    │    ├─► get_daily_dashboard()  (Asia/Ho_Chi_Minh)
    │    ├─► get_weekly_dashboard() (if policy.include)
    │    ├─► select MealLog (last N, with selectinload)
    │    ├─► select DailyRecommendation (latest)
    │    ├─► select ChatMessage (last N for history)
    │    └─► get_active_insights()
    │         └─► sanitize_for_prompt on every text field
    │
    ├─► check_hard_rule_triggers()  ──► Card fires?
    │    └─► YES: save_card_message → db.commit() → yield SSE card → RETURN
    │
    ├─► Groq AsyncGroq streaming (max_tokens=1024, temp=0.4)
    │    │
    │    ├─► Tool call (ask_user)?
    │    │    ├─► _build_card_from_tool_input()
    │    │    ├─► save_card_message() → db.commit()
    │    │    └─► yield SSE card → RETURN
    │    │
    │    └─► Text delta → yield SSE delta
    │
    ├─► save_chat_message(role="assistant", full_response)
    │    └─► db.commit()
    │
    ├─► yield done SSE
    │
    └─► background_tasks.add_task(_bg_extractor_agent)
```

### Card Response Flow

```
POST /chatbot/card-response
    │
    ▼
process_card_response_and_stream()
    │
    ├─► Find matching ChatMessage (role=assistant, type=card, no response yet)
    │
    ├─► card_msg.card_response = card_response.model_dump()
    │    └─► db.flush()
    │
    ├─► _update_profile_from_card_response()
    │    └─► setattr(profile, field, value)
    │         └─► db.commit()
    │
    ├─► _build_card_response_text()  ──► "Có, Mục tiêu: Giảm cân"
    │
    ├─► save_chat_message(role=user, type=card_response)
    │    └─► db.commit()
    │
    ├─► await db.close()  ← close original session before streaming
    │
    ├─► Groq AsyncGroq streaming (new session via _get_stream_db())
    │
    └─► Outer try/finally:
         └─► _close_stream_db()  ← ALWAYS runs on every exit path
              └─► rollback() → close()
```

### Background Extractor Task Flow

```
BackgroundTasks.add_task(_bg_extractor_agent, ...)
    │
    ▼
_bg_extractor_agent(user_id, session_id, user_message, ai_response)
    │
    ├─► AsyncSessionLocal() (new session, self-contained)
    │
    ├─► select User
    ├─► get_or_create_memory(user_id)
    │
    ├─► select ChatMessage (last 6, reversed) → conversation_history
    │
    ├─► AgentContext(user, session_id, current_message, history, memory)
    │
    ├─► ExtractorAgent.run() → result
    │    └─► Writes ConversationInsight + UserMemory via MemoryWriteEngine
    │
    └─► db.commit()
```
