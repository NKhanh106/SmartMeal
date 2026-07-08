"""
Base classes and dataclasses for all SmartMeal agents.

This module contains the shared infrastructure used by every specialist agent:
  - AgentContext: shared runtime context passed to every agent
  - AgentResult: standardized output from every agent
  - BaseAgent: abstract base class with AI call, retry, circuit breaker

Each specialist agent imports from app.agents.base (the backwards-compatible re-export
in base.py) so existing import lines like `from app.agents.base import BaseAgent` keep working.
"""

import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from groq import AsyncGroq
from sqlalchemy import update
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.circuit_breaker import groq_circuit
from app.core.config import settings
from app.models import AgentRun
from app.schemas.chat_card import ChatCard
from app.agents.context_loader import FullUserContext
from app.ai.providers.groq_provider import GroqProvider
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("smartmeal.agents")

_groq_client_index: int = 0
_groq_lock = asyncio.Lock()


def _get_groq_client() -> AsyncGroq:
    global _groq_client_index
    keys = settings.GROQ_API_KEYS_LIST
    if not keys:
        raise ValueError("GROQ_API_KEYS is missing or empty")
    key = keys[_groq_client_index % len(keys)]
    _groq_client_index += 1
    return AsyncGroq(api_key=key)


async def get_async_groq_client() -> AsyncGroq:
    """Get an AsyncGroq client with round-robin key rotation."""
    global _groq_client_index
    async with _groq_lock:
        keys = settings.GROQ_API_KEYS_LIST
        if not keys:
            raise ValueError("GROQ_API_KEYS is missing or empty")
        key = keys[_groq_client_index % len(keys)]
        _groq_client_index += 1
    return AsyncGroq(api_key=key)


AI_TIMEOUT_SECONDS = 30


@dataclass
class AgentContext:
    """
    Shared context passed to every agent at runtime.

    Attributes added for depth mode support:
      depth_config: the active DepthConfig for this request (None = legacy default)
    """

    user: Any
    session_id: str
    current_message: str
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    profile: Any = None
    run_id: str = ""
    memory: Any = field(default=None)
    active_goal: Any = None
    depth_config: Any = field(default=None)
    full_context: Any = field(default=None)
    demographic_flags: dict[str, bool] = field(default_factory=dict)


@dataclass
class AgentResult:
    """
    Standardized output from every agent.
    Return this from BaseAgent.run() — the orchestrator uses it to synthesize responses.
    """

    agent_name: str
    success: bool
    insight_type: str
    content: dict[str, Any]
    confidence: float = 0.5
    priority: int = 5
    text_for_orchestrator: str = ""
    memory_updates: dict[str, Any] = field(default_factory=list)
    suggested_card: ChatCard | None = None
    error: str | None = None
    proposals: list = field(default_factory=list)  # UpdateProposal list for write-back confirmation


class BaseAgent(ABC):
    """
    Abstract base for all specialist agents.

    Subclass this and implement `execute(context, db) -> AgentResult`.

    The shared infrastructure handles:
      - run_id generation + AgentRun logging
      - AI calls with token tracking (respects depth_config token budgets)
      - Memory reads via memory_service
      - Guaranteed AgentRun completion logging (normal, exception, cancellation)
    """

    name: str = "base_agent"

    @abstractmethod
    async def execute(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResult:
        ...

    async def run(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResult:
        """
        Wrapper that guarantees AgentRun completion logging.

        IMPORTANT: this method must re-raise CancelledError.
        """
        run_row: AgentRun | None = None
        result: AgentResult | None = None
        start = time.perf_counter()

        try:
            run_row = self._log_start(
                context=context,
                trigger="agent_run",
                input_summary=(context.current_message or "")[:200],
                db=db,
            )
            await db.flush()

            result = await self.execute(context, db)
            return result

        except asyncio.CancelledError:
            result = AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="cancelled",
                content={},
                confidence=0.0,
                priority=10,
                memory_updates={},
                error="Task cancelled",
            )
            raise

        except Exception as exc:
            result = AgentResult(
                agent_name=self.name,
                success=False,
                insight_type="error",
                content={},
                confidence=0.0,
                priority=10,
                memory_updates={},
                error=str(exc),
            )
            raise

        finally:
            if run_row is not None:
                try:
                    await asyncio.shield(
                        self._log_complete(
                            run_row,
                            result,
                            db,
                            latency_ms=int((time.perf_counter() - start) * 1000),
                        )
                    )
                except Exception as log_err:
                    logger.error(
                        "Failed to log agent completion",
                        extra={"agent": self.name, "run_id": run_row.run_id, "error": str(log_err)},
                    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, asyncio.TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _call_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Literal["text", "json"] = "text",
        max_tokens: int = 800,
        model: str | None = None,
    ) -> dict[str, Any] | str:
        """
        Shared AI call via Groq with usage token tracking, retry logic,
        circuit breaker, and hard timeout.

        When context.depth_config is set, token budgets are taken from the
        depth config instead of the default max_tokens parameter.
        """
        if self.context is not None and self.context.depth_config is not None:
            token_map = {
                "extractor":         self.context.depth_config.extractor_tokens,
                "health_monitor":    self.context.depth_config.health_tokens,
                "nutrition_advisor": self.context.depth_config.nutrition_tokens,
                "fitness_coach":     self.context.depth_config.fitness_tokens,
            }
            max_tokens = token_map.get(self.name, max_tokens)

        model_name = model or settings.GROQ_TEXT_MODEL
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.perf_counter()
        last_error: Exception | None = None
        keys = settings.GROQ_API_KEYS_LIST

        for attempt in range(len(keys)):
            client = _get_groq_client()
            current_key_idx = _groq_client_index - 1

            async def _do_create(c=client):
                return await c.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.3,
                )

            try:
                async with asyncio.timeout(AI_TIMEOUT_SECONDS):
                    stream = await groq_circuit.call(_do_create)
                break
            except Exception as exc:
                last_error = exc
                error_str = str(exc).lower()
                is_rate_limit = "rate limit" in error_str or "429" in error_str
                is_too_large = "413" in error_str or "request too large" in error_str

                if is_too_large:
                    # TPM exceeded on a single key — wait briefly and retry the
                    # same call. Rotating the key won't help (limit is per-org),
                    # but a short pause often does because the TPM window is
                    # rolling per minute.
                    wait_s = 2.0 + attempt * 2.0
                    logger.warning(
                        f"[Agent:{self.name}] 413 (TPM exceeded) — sleeping {wait_s:.1f}s "
                        f"before retry (attempt {attempt + 1}/{len(keys)})"
                    )
                    await asyncio.sleep(wait_s)
                    continue

                if is_rate_limit and attempt < len(keys) - 1:
                    logger.warning(
                        f"[Agent:{self.name}] Rate limit on key {current_key_idx % len(keys)}, "
                        f"trying next key (attempt {attempt + 1}/{len(keys)})"
                    )
                    continue
                raise

        if last_error and isinstance(last_error, asyncio.TimeoutError):
            raise TimeoutError(
                f"AI call timed out after {AI_TIMEOUT_SECONDS}s for agent '{self.name}'"
            ) from None
        if last_error:
            raise last_error

        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = stream.usage
        choice = stream.choices[0]
        text = choice.message.content or ""
        finish_reason = getattr(choice, "finish_reason", None)

        prompt_chars = sum(len(m.get("content") or "") for m in messages)
        if not text:
            logger.warning(
                "[%s] Groq returned empty content. finish_reason=%s, "
                "usage=%s, prompt_chars=%d, model=%s, latency_ms=%d",
                self.name, finish_reason,
                {k: getattr(usage, k, None) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
                if usage else None,
                prompt_chars, model_name, latency_ms,
            )

        self._last_usage = {
            "input_tokens": usage.prompt_tokens if usage else None,
            "output_tokens": usage.completion_tokens if usage else None,
            "latency_ms": latency_ms,
            "model": model_name,
        }

        if response_format == "json":
            cleaned = re.sub(
                r"^\s*```json\s*|```\s*$", "", text.strip(), flags=re.MULTILINE
            ).strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"AI did not return valid JSON: {exc}\nOutput: {text}"
                ) from exc

        return text

    _last_usage: dict[str, Any] = field(default_factory=dict, init=False)

    context: AgentContext | None = field(default=None, init=False)

    def _log_start(
        self,
        context: AgentContext,
        trigger: str,
        input_summary: str | None,
        db: AsyncSession,
    ) -> AgentRun:
        self.context = context
        run = AgentRun(
            run_id=str(uuid4()),
            user_id=context.user.id,
            session_id=context.session_id or None,
            agent_name=self.name,
            trigger=trigger,
            status="running",
            input_summary=(input_summary or context.current_message[:200])[:200],
        )
        db.add(run)
        return run

    async def _log_complete(
        self,
        run: AgentRun,
        result: AgentResult | None,
        db: AsyncSession,
        output_summary: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """
        Mark the AgentRun as completed/failed/cancelled.

        NOTE: This method is intentionally resilient: callers may pass result=None
        if the task was cancelled before a result could be constructed.
        """
        status = "cancelled" if result is None else ("failed" if not result.success else "completed")

        update_vals: dict[str, Any] = {
            "status": status,
            "completed_at": datetime.now(timezone.utc),
        }

        if self._last_usage and isinstance(self._last_usage, dict):
            update_vals["input_tokens"] = self._last_usage.get("input_tokens")
            update_vals["output_tokens"] = self._last_usage.get("output_tokens")
            update_vals["latency_ms"] = self._last_usage.get("latency_ms")
            update_vals["extra_data"] = {
                "model": self._last_usage.get("model", settings.GROQ_TEXT_MODEL)
            }
        elif latency_ms is not None:
            update_vals["latency_ms"] = latency_ms

        if result is not None and (not result.success) and result.error:
            update_vals["error_message"] = result.error

        summary = (output_summary or (result.text_for_orchestrator if result else "") or "")[:500]
        if summary:
            update_vals["output_summary"] = summary

        try:
            await db.execute(
                update(AgentRun)
                .where(AgentRun.run_id == run.run_id)
                .values(**update_vals)
            )
            # Flush only; session owner decides commit/rollback.
            await db.flush()
        except Exception as e:
            logger.error(
                "Failed to log agent completion",
                extra={"agent": self.name, "run_id": run.run_id, "error": str(e)},
            )

    async def _load_memory(self, user_id: str, db: AsyncSession) -> Any:
        from app.agents.memory_service import get_or_create_memory
        return await get_or_create_memory(user_id, db)

    async def _update_memory(
        self,
        user_id: str,
        updates: dict[str, Any],
        db: AsyncSession,
    ) -> Any:
        from app.agents.memory_service import apply_memory_updates
        return await apply_memory_updates(user_id, updates, db)

    async def _refresh_context(self, context: AgentContext, db: AsyncSession) -> AgentContext:
        context.memory = await self._load_memory(str(context.user.id), db)
        return context

    def _parse_json_safe(self, raw: str) -> dict[str, Any]:
        try:
            clean = raw.strip()
            for prefix in ("```json", "```JSON", "```"):
                if clean.startswith(prefix):
                    clean = clean[len(prefix):]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {}
