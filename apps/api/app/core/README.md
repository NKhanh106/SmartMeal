# Core Infrastructure

Supporting modules used across the entire API. These are the foundation everything runs on.

## Modules

### config.py — Settings Management

Pydantic `BaseSettings` reads all configuration from environment variables. Supports `.env` file loading via `python-dotenv`.

Key settings:

```python
DATABASE_URL: PostgreSQL connection string (URL-encoded password supported)
REDIS_URL: redis:// connection string
SECRET_KEY: JWT signing key (must be 32+ chars in production)
GROQ_API_KEY: Groq API key
GEMINI_API_KEY: Google Gemini API key
ENVIRONMENT: development | production
AI_PROVIDER: gemini | groq  (which provider to use for meal-related AI)
DEFAULT_AI_PROVIDER: groq  (chat + general AI)
VISION_AI_PROVIDER: gemini  (image analysis)
```

In production, `SECRET_KEY` must be at least 32 characters. The app raises a warning if it's shorter.

### security.py — Authentication

JWT access + refresh token implementation:

```python
create_access_token(data: dict)  → signed JWT (24h default)
create_refresh_token(user_id)     → signed JWT (7d)
verify_password(plain, hashed)    → bool (bcrypt)
hash_password(plain)             → str
get_password_hash()              → str (for registration)
```

Brute-force protection: tracks failed login attempts per email in Redis. After 5 failures within 5 minutes, the account is locked for 5 minutes. Successful login clears the counter.

### brute_force.py — Login Protection

Redis-backed failed attempt tracking.

```python
record_failed_login(email: str)  → increments counter, sets 5-min TTL
check_login_attempts(email: str) → bool (True = locked out)
clear_failed_logins(email: str) → called on successful login
```

### rate_limiter.py — Request Rate Limiting

SlowAPI integration with Redis-backed storage for distributed rate limiting.

```python
limiter = Limiter(key_func=get_real_ip)
```

`get_real_ip` handles the `X-Forwarded-For` header for deployments behind proxies. Rate limits are defined per-endpoint in route decorators:

```python
@router.post("/login", dependencies=[Depends(rate_limit("10/minute"))])
```

### circuit_breaker.py — AI Provider Resilience

State machine preventing cascade failures when AI providers are down.

```
CLOSED ──(5 failures)──→ OPEN ──(60s)──→ HALF_OPEN ──(success)──→ CLOSED
                              │
                              └───(failure)──→ OPEN (reset timer)
```

When OPEN, AI calls return an error immediately without making the network request. After 60 seconds, the breaker moves to HALF_OPEN and allows one test request. If it succeeds, the breaker closes; if it fails, it opens again.

### cache.py — Redis Caching

```python
@cache_response(ttl=3600, prefix="chat")
async def get_cached_response(...):
    ...
```

Cache TTLs by data type:
- AI chat responses: 1 hour
- Daily meal plans: 12 hours
- Food recognition: 24 hours
- User profiles: 30 minutes

Graceful degradation: if Redis is unavailable, the app continues without caching and logs a warning. No errors are raised.

```python
await cache_close()  # Called on shutdown
```

### errors.py — Standardized Error Responses

Factory methods for consistent HTTP error responses:

```python
AppError.bad_request("Invalid input", code="INVALID_CALORIES")
AppError.not_found("Meal log not found")
AppError.forbidden("Admin access required")
AppError.unauthorized("Invalid or expired token")
```

All map to appropriate HTTP status codes with a consistent JSON shape.

### sanitize.py — Input Sanitization

Prompt injection prevention for AI inputs. Detects and removes:

- Markdown code blocks (prevents prompt injection via formatted input)
- HTML tags
- Excessive whitespace
- Control characters

Applied at the orchestrator entry point before any AI call. Vietnamese text is handled correctly (Unicode-aware).

### token_budget.py — AI Token Management

Vietnamese-aware token estimation (approximately 3 characters per token for Vietnamese text, vs 4 for English):

```python
estimate_tokens(text: str) → int

def build_context_within_budget(
    sections: list[tuple[label, content, priority]],
    max_tokens: int
) → str:
    # Fills budget with highest-priority sections first
    # Drops lowest-priority sections if over budget
```

Used by the orchestrator to build the synthesis context within the AI model's context window.

### audit_log.py — Audit Trail

Structured logging of sensitive operations (login, logout, profile changes). Logs include user ID, action, IP address, and timestamp in JSON format.

### logging_config.py — Production Logging

Sets up structured JSON logging for production (`ENVIRONMENT=production`). Includes request ID middleware for tracing.
