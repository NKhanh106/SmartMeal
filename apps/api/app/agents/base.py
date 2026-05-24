"""
Base class for all SmartMeal agents.

Provides:
- Standardized AgentContext / AgentResult dataclasses
- Abstract BaseAgent with shared _call_ai, _log_start, _log_complete methods
- Token usage tracking and AgentRun logging for all agents

Each specialist agent inherits from BaseAgent and implements the `run()` method.
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
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.ai.circuit_breaker import groq_circuit
from app.core.config import settings
from app.models import AgentRun
from app.schemas.chat_card import ChatCard
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("smartmeal.agents")

# Shared Groq client — reuse connection pool across all agents
_groq_client: AsyncGroq | None = None


def _get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    return _groq_client


AI_TIMEOUT_SECONDS = 30  # Hard timeout on any single AI call


# ── Dataclasses ─────────────────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """Shared context passed to every agent at runtime."""

    user: Any  # User model instance
    session_id: str
    current_message: str
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    profile: Any = None  # UserProfile object
    run_id: str = ""
    memory: Any = field(default=None)  # UserMemory object, set by orchestrator
    active_goal: Any = None  # NutritionGoal object, set by orchestrator


@dataclass
class AgentResult:
    """
    Standardized output from every agent.
    Return this from BaseAgent.run() — the orchestrator uses it to synthesize responses.
    """

    agent_name: str
    success: bool
    insight_type: str
    content: dict[str, Any]  # agent-specific structured data
    confidence: float = 0.5  # 0.0 – 1.0
    priority: int = 5  # 1 urgent → 10 low
    text_for_orchestrator: str = ""  # plain text summary for orchestrator
    memory_updates: dict[str, Any] = field(default_factory=dict)  # fields to write to UserMemory
    suggested_card: ChatCard | None = None
    error: str | None = None


# ── Base Agent ─────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base for all specialist agents.

    Subclass this and implement `run(context, db) -> AgentResult`.

    The shared infrastructure handles:
    - run_id generation + AgentRun logging
    - AI calls with token tracking
    - Memory reads via memory_service
    """

    name: str = "base_agent"

    @abstractmethod
    async def run(
        self,
        context: AgentContext,
        db: AsyncSession,
    ) -> AgentResult:
        """
        Execute this agent and return a structured AgentResult.
        """
        ...

    # ── AI Call ─────────────────────────────────────────────────────────────────

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

        Returns raw text if response_format == "text",
        or a parsed dict if response_format == "json".
        """
        model_name = model or settings.GROQ_TEXT_MODEL
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.perf_counter()

        async def _do_create():
            client = _get_groq_client()
            return await client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,
            )

        try:
            async with asyncio.timeout(AI_TIMEOUT_SECONDS):
                stream = await groq_circuit.call(_do_create)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"AI call timed out after {AI_TIMEOUT_SECONDS}s for agent '{self.name}'"
            ) from None

        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = stream.usage
        choice = stream.choices[0]
        text = choice.message.content or ""

        # Store token stats for logging
        self._last_usage = {
            "input_tokens": usage.prompt_tokens if usage else None,
            "output_tokens": usage.completion_tokens if usage else None,
            "latency_ms": latency_ms,
            "model": model_name,
        }

        if response_format == "json":
            # Strip markdown code fences that some models return wrapping JSON
            cleaned = re.sub(r"^\s*```json\s*|```\s*$", "", text.strip(), flags=re.MULTILINE).strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"AI did not return valid JSON: {exc}\nOutput: {text}"
                ) from exc

        return text

    # Internal storage for token stats (set by _call_ai)
    _last_usage: dict[str, Any] = field(default_factory=dict, init=False)

    # ── Run Logging ─────────────────────────────────────────────────────────────

    def _log_start(
        self,
        context: AgentContext,
        trigger: str,
        input_summary: str | None,
        db: AsyncSession,
    ) -> AgentRun:
        """
        Create an AgentRun record with status='running' and flush to DB.
        Call at the START of your agent's run() method.
        """
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
        return run  # caller must await db.commit()

    async def _log_complete(
        self,
        run: AgentRun,
        result: AgentResult,
        db: AsyncSession,
        output_summary: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """
        Update an AgentRun record to 'completed' or 'failed'.
        Call in a finally block at the END of your agent's run() method.
        """
        update_vals: dict[str, Any] = {
            "status": "failed" if not result.success else "completed",
            "completed_at": datetime.now(timezone.utc),
        }

        if self._last_usage:
            update_vals["input_tokens"] = self._last_usage.get("input_tokens")
            update_vals["output_tokens"] = self._last_usage.get("output_tokens")
            update_vals["latency_ms"] = self._last_usage.get("latency_ms")
            update_vals["extra_data"] = {
                "model": self._last_usage.get("model", settings.GROQ_TEXT_MODEL)
            }
        elif latency_ms is not None:
            update_vals["latency_ms"] = latency_ms

        if not result.success and result.error:
            update_vals["error_message"] = result.error

        summary = (output_summary or result.text_for_orchestrator or "")[:500]
        if summary:
            update_vals["output_summary"] = summary

        await db.execute(
            update(AgentRun)
            .where(AgentRun.run_id == run.run_id)
            .values(**update_vals)
        )
        await db.commit()

    # ── Memory Helpers ──────────────────────────────────────────────────────────

    async def _load_memory(self, user_id: str, db: AsyncSession) -> Any:
        """Get or create UserMemory for the current user."""
        from app.agents.memory_service import get_or_create_memory
        return await get_or_create_memory(user_id, db)

    async def _update_memory(
        self,
        user_id: str,
        updates: dict[str, Any],
        db: AsyncSession,
    ) -> Any:
        """Merge updates into UserMemory."""
        from app.agents.memory_service import apply_memory_updates
        return await apply_memory_updates(user_id, updates, db)

    async def _refresh_context(self, context: AgentContext, db: AsyncSession) -> AgentContext:
        """Reload memory into context (useful after updates)."""
        context.memory = await self._load_memory(str(context.user.id), db)
        return context

    def _parse_json_safe(self, raw: str) -> dict[str, Any]:
        """
        Safely parse AI JSON response, stripping markdown code fences.
        Returns empty structure on failure so agents degrade gracefully.
        """
        try:
            clean = raw.strip()
            # Remove markdown code fences
            for prefix in ("```json", "```JSON", "```"):
                if clean.startswith(prefix):
                    clean = clean[len(prefix):]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {}
