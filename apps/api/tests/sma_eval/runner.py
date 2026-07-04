"""
SMA-Eval v1 — SmartMeal Multi-Agent Evaluation Runner

Thực thi benchmark toàn diện cho hệ thống Multi-Agent:
  1. SSE_Token_Aggregator — gom token từ luồng streaming real-time
  2. DB_Assertion_Loop   — polling PostgreSQL sau khi background worker hoàn tất
  3. SMARunner            — orchestrates full test lifecycle
  4. Ablation Study      — BASELINE / PARTIAL / FULL pipeline modes
  5. CLI                  — python -m tests.sma_eval.runner --config full --test-ids A-ALLERGEN-001

Exit codes
─────────
  0  — all tests passed
  1  — at least one test failed
  2  — infra breakdown (connection pool exhausted / network error)
  3  — invalid CLI arguments

Usage
──────
  # Run full suite
  python -m tests.sma_eval.runner --config full

  # Ablation studies
  python -m tests.sma_eval.runner --config baseline --test-ids A-ALLERGEN-001 B-CONFLICT-001
  python -m tests.sma_eval.runner --config partial --ablation-block health_monitor

  # Tier-only
  python -m tests.sma_eval.runner --config full --tier C
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator

# ── path setup ──────────────────────────────────────────────────────────────────
import sys as _sys
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parents[2]
_sys.path.insert(0, str(_ROOT)); del _sys

from app.core.config import settings
from app.models.enums import MealLogStatus
from app.models.meal import MealLog
from app.services.nutrition_math import calculate_bmr, calculate_tdee

import httpx
from httpx import ASGITransport, AsyncClient

# ────────────────────────────────────────────────────────────────────────────────

log = logging.getLogger("sma_eval.runner")


# ══════════════════════════════════════════════════════════════════════════════
# helpers — SSE agent result reconstruction
# ══════════════════════════════════════════════════════════════════════════════

def _build_agent_results_from_sse(
    raw_results: dict[str, dict],
) -> dict[str, "AgentResult"]:
    """
    Convert parsed agent_result SSE payloads into AgentResult objects
    compatible with the SMAMetricSuite.evaluate() signature.

    AgentResult fields pulled from SSE payload:
      agent_name  → from payload["agent"]
      success    → from payload["success"]
      insight_type → from payload["insight_type"]
      content    → from payload["content"]  (dict)
      confidence → from payload.get("confidence", 0.5)
      priority   → from payload.get("priority", 5)
      text_for_orchestrator → from payload.get("text_for_orchestrator", "")
      error      → from payload.get("error")
    """
    from app.agents.base import AgentResult

    results: dict[str, AgentResult] = {}
    for agent_name, payload in raw_results.items():
        if not payload:
            continue
        results[agent_name] = AgentResult(
            agent_name=str(agent_name),
            success=bool(payload.get("success", True)),
            insight_type=str(payload.get("insight_type", "")),
            content=payload.get("content") or {},
            confidence=float(payload.get("confidence", 0.5)),
            priority=int(payload.get("priority", 5)),
            text_for_orchestrator=str(payload.get("text_for_orchestrator", "")),
            error=str(payload.get("error")) if payload.get("error") else None,
        )
    return results


# ══════════════════════════════════════════════════════════════════════════════
# Ablation configuration
# ══════════════════════════════════════════════════════════════════════════════

class AblationConfig(str, Enum):
    """
    Ablation modes cho benchmark.

    BASELINE — Single-Agent direct path
        Bypasses Multi-Agent Orchestrator entirely.
        Uses the direct /api/v1/nutrition/meal-suggest endpoint (if available)
        or a mock single-agent that calls Groq directly.
        Purpose: measure the "bot gánh đơn lẻ" ceiling.

    PARTIAL — Multi-Agent với triệt tiêu thành phần
        Runs full Multi-Agent pipeline but disables one or more components:
          - ablate_health_monitor=True  → skip HealthMonitor in Phase 1
          - ablate_background_worker=True → ExtractorQueue worker never runs
          - ablate_nutrition=True       → skip NutritionAdvisor in Phase 2
        Purpose: measure marginal contribution of each agent.

    FULL — Toàn bộ Hybrid Pipeline hiện tại
        Full Multi-Agent pipeline with all components active.
        Purpose: measure real-world performance.
    """
    BASELINE = "baseline"
    PARTIAL = "partial"
    FULL    = "full"


@dataclass
class AblationParams:
    """Tham số kiểm soát ablation study."""
    config: AblationConfig
    ablate_health_monitor: bool = False
    ablate_background_worker: bool = False
    ablate_nutrition: bool = False
    ablate_fitness: bool = False

    @classmethod
    def from_cli(cls, config_str: str, **kwargs) -> "AblationParams":
        config = AblationConfig(config_str)

        if config == AblationConfig.BASELINE:
            return cls(config=config, ablate_health_monitor=True,
                       ablate_background_worker=True,
                       ablate_nutrition=True, ablate_fitness=True)

        if config == AblationConfig.PARTIAL:
            return cls(
                config=config,
                ablate_health_monitor=kwargs.get("ablate_health_monitor", False),
                ablate_background_worker=kwargs.get("ablate_background_worker", False),
                ablate_nutrition=kwargs.get("ablate_nutrition", False),
                ablate_fitness=kwargs.get("ablate_fitness", False),
            )

        return cls(config=config)


# ══════════════════════════════════════════════════════════════════════════════
# SSE token aggregator
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SSEEvent:
    """Một event thô được parse từ luồng SSE."""
    event_type: str   # "depth" | "card" | "update_proposal" | "agent_result" | "data"
    raw_data: str     # raw string sau "data: "
    parsed: dict | None = None  # JSON parse nếu có
    delta: str | None = None    # text delta (cho type="data")
    done: bool = False
    error: str | None = None
    agent_name: str | None = None  # populated when event_type == "agent_result"


class SSE_Token_Aggregator:
    """
    Gom luồng SSE text stream thành:
      (a) Chuỗi văn bản hoàn chỉnh (final_response)
      (b) Danh sách SSEEvent đầy đủ cho debugging
      (c) Dict per-agent results {agent_name: parsed_payload}

    Luồng parse:
      raw bytes → decode → tách lines → parse "event:" và "data:" → emit SSEEvent

    SSE format hệ thống SmartMeal:
      event: depth\n
      data: quick\n\n

      event: card\n
      data: {"card_id": "...", ...}\n\n

      event: agent_result\n
      data: {"agent": "nutrition", "success": true, "content": {...}, ...}\n\n

      data: {"delta": "Xin chào", "done": false}\n\n
      data: {"done": true}\n\n
    """

    def __init__(self):
        self._buffer = ""
        self._events: list[SSEEvent] = []
        self._full_text: list[str] = []
        self._done = False
        # Per-agent structured results extracted from agent_result events
        self._agent_results: dict[str, dict] = {}

    async def feed_stream(
        self, response: httpx.Response,
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        Feed raw streaming response body. Yields SSEEvent as they are parsed.
        Accumulates full text internally.
        """
        async for line in response.aiter_lines():
            if not line:
                # Blank line → SSE event boundary
                if self._buffer:
                    event = self._parse_buffer(self._buffer)
                    if event is not None:
                        self._events.append(event)
                        if event.delta:
                            self._full_text.append(event.delta)
                        if event.done:
                            self._done = True
                        yield event
                    self._buffer = ""
                continue

            if line.startswith("event:"):
                self._buffer = line + "\n"
            elif line.startswith("data:"):
                self._buffer += line + "\n"

        # Flush remaining buffer
        if self._buffer:
            event = self._parse_buffer(self._buffer)
            if event is not None:
                self._events.append(event)
                if event.delta:
                    self._full_text.append(event.delta)
                if event.done:
                    self._done = True
                yield event

    def _parse_buffer(self, raw: str) -> SSEEvent | None:
        """Parse a complete SSE event from accumulated lines."""
        lines = raw.strip("\n").split("\n")
        event_type = "data"
        raw_data = ""

        for line in lines:
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                raw_data = line[len("data:"):].strip()

        if not raw_data:
            return None

        parsed: dict[str, Any] | None = None
        delta: str | None = None
        done = False
        error: str | None = None
        agent_name: str | None = None

        # Attempt JSON parse
        try:
            parsed = json.loads(raw_data)
            if isinstance(parsed, dict):
                delta = parsed.get("delta", "") if parsed.get("delta") else None
                done = bool(parsed.get("done", False))
                if "error" in parsed:
                    error = str(parsed["error"])
                # ── agent_result event: extract agent key ──────────────────────
                if event_type == "agent_result":
                    agent_name = parsed.get("agent")
                    if agent_name:
                        self._agent_results[agent_name] = parsed
        except json.JSONDecodeError:
            # Plain text data (e.g. the depth event)
            parsed = {"raw": raw_data}

        return SSEEvent(
            event_type=event_type,
            raw_data=raw_data,
            parsed=parsed,
            delta=delta,
            done=done,
            error=error,
            agent_name=agent_name,
        )

    @property
    def final_response(self) -> str:
        """Toàn bộ văn bản ghép lại từ các delta token."""
        return "".join(self._full_text)

    @property
    def all_events(self) -> list[SSEEvent]:
        return self._events

    @property
    def is_done(self) -> bool:
        return self._done

    @property
    def event_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self._events:
            counts[e.event_type] = counts.get(e.event_type, 0) + 1
        return counts

    @property
    def agent_results(self) -> dict[str, dict]:
        """
        Dict of per-agent structured results extracted from SSE agent_result events.

        Keys: "health", "nutrition", "fitness", "research" (whatever the orchestrator emitted).
        Values: parsed JSON payload from the event.

        Usage in SMA-Eval runner:
            aggregator = SSE_Token_Aggregator()
            async for _ in aggregator.feed_stream(response):
                pass
            agent_results = aggregator.agent_results  # dict[str, dict]
            # → {"nutrition": {"agent": "nutrition", "success": true, "content": {...}}, ...}
        """
        return self._agent_results


# ══════════════════════════════════════════════════════════════════════════════
# DB assertion loop
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DBAssertionResult:
    """Kết quả của vòng polling DB."""
    success: bool
    meal_logs_found: int = 0
    pending_logs_found: int = 0
    attempts: int = 0
    final_status: str = "not_checked"
    error: str | None = None
    poll_durations_ms: list[int] = field(default_factory=list)


class InfraBreakdownError(Exception):
    """
    Raised when the infrastructure is down:
      - Connection pool exhausted
      - Redis unavailable
      - Network timeout
      - Database unreachable
    """
    pass


class DB_Assertion_Loop:
    """
    Polls PostgreSQL meal_logs sau khi background ExtractorAgent hoàn tất.

    Assertion criteria:
      1. Tìm ít nhất 1 record MealLog mới được tạo bởi session_id
         với status = PENDING/COMPLETED và source = 'chat_extraction'.
      2. Payload bắt buộc phải chứa dữ liệu dinh dưỡng thực tế:
           total_calories > 0  HOẶC
           total_protein_g > 0  HOẶC
           total_carb_g > 0  HOẶC
           total_fat_g > 0
         Bản ghi PENDING nhưng calorie = 0 / null → coi như chưa xử lý xong,
         tiếp tục vòng lặp polling.
      3. Bản ghi COMPLETED với payload rỗng → cũng coi là assertion FAILED.

    Polling strategy:
      - Poll interval: 1.5 giây giữa các lần thử
      - Tối đa 3 lần thử (tổng chờ tối đa 4.5 giây)
      - Nếu tất cả 3 lần đều fail → FAIL
      - Nếu background worker bị triệt tiêu (ablation) → skip assertion và trả về SKIPPED

    Có thể raise InfraBreakdownError nếu DB không trả lời do lỗi kết nối.
    """

    DEFAULT_INTERVAL_S  = 1.5
    DEFAULT_MAX_ATTEMPTS = 3

    def __init__(
        self,
        db_session_factory,       # async_sessionmaker
        session_id: str,
        user_id: str,
        ablate_worker: bool = False,
        interval_s: float = DEFAULT_INTERVAL_S,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ):
        self._session_factory = db_session_factory
        self._session_id = session_id
        self._user_id = user_id
        self._ablate_worker = ablate_worker
        self._interval_s = interval_s
        self._max_attempts = max_attempts
        self._start_time: float = 0.0

    def _has_valid_payload(self, log) -> bool:
        """Kiểm tra MealLog có chứa dữ liệu dinh dưỡng thực tế hay chỉ là bản ghi rỗng."""
        calories = getattr(log, "total_calories", None)
        protein  = getattr(log, "total_protein_g", None)
        carb     = getattr(log, "total_carb_g", None)
        fat      = getattr(log, "total_fat_g", None)

        # Ít nhất 1 trong 4 trường phải > 0 và not null
        return any(
            v is not None and v > 0
            for v in (calories, protein, carb, fat)
        )

    async def run(self) -> DBAssertionResult:
        # ── Ablation skip: background worker disabled ─────────────────────────
        if self._ablate_worker:
            log.info(
                "[DB_Assertion] Skipped — background worker ablation active "
                "(session_id=%s)", self._session_id
            )
            return DBAssertionResult(
                success=True,
                final_status="skipped_ablation",
                attempts=0,
            )

        self._start_time = time.monotonic()
        poll_durations: list[int] = []
        last_error: str | None = None

        for attempt in range(1, self._max_attempts + 1):
            attempt_start = time.monotonic()

            try:
                async with self._session_factory() as session:
                    from sqlalchemy import select, and_
                    from app.models.meal import MealLog

                    stmt = select(MealLog).where(
                        and_(
                            MealLog.user_id.__eq__(self._user_id),
                            MealLog.source.name == "chat_extraction",
                        )
                    ).order_by(MealLog.created_at.desc())

                    result = await session.execute(stmt)
                    logs = result.scalars().all()

                    # Filter: chỉ lấy logs gần đây nhất (trong vòng 120s sau test start)
                    cutoff = datetime.now().timestamp() - 120
                    recent = [
                        log for log in logs
                        if log.created_at and log.created_at.timestamp() > cutoff
                    ]

                    elapsed_ms = int((time.monotonic() - attempt_start) * 1000)
                    poll_durations.append(elapsed_ms)

                    # ── Classify logs ──────────────────────────────────────────────
                    pending_with_payload: list = []
                    pending_empty: list = []
                    completed_with_payload: list = []

                    for meal_log in recent:
                        if meal_log.status == MealLogStatus.PENDING:
                            if self._has_valid_payload(meal_log):
                                pending_with_payload.append(meal_log)
                            else:
                                pending_empty.append(meal_log)
                        elif meal_log.status == MealLogStatus.COMPLETED:
                            if self._has_valid_payload(meal_log):
                                completed_with_payload.append(meal_log)

                    log.info(
                        "[DB_Assertion] Attempt %d/%d: %d recent, "
                        "%d pending+valid, %d pending+empty, %d completed+valid "
                        "(session_id=%s, elapsed=%.1fs)",
                        attempt, self._max_attempts,
                        len(recent),
                        len(pending_with_payload),
                        len(pending_empty),
                        len(completed_with_payload),
                        self._session_id[:8],
                        time.monotonic() - self._start_time,
                    )

                    # ── Payload validation: fail-fast on empty stubs ─────────────────
                    if pending_empty:
                        log.warning(
                            "[DB_Assertion] Found %d PENDING records with empty payload "
                            "(calories=0/null). Worker may have crashed or returned null. "
                            "Continuing to poll... (session_id=%s)",
                            len(pending_empty), self._session_id[:8]
                        )
                        if attempt < self._max_attempts:
                            await asyncio.sleep(self._interval_s)
                            continue

                    # ── Primary: PENDING record with valid payload ─────────────────
                    if pending_with_payload:
                        return DBAssertionResult(
                            success=True,
                            meal_logs_found=len(recent),
                            pending_logs_found=len(pending_with_payload),
                            attempts=attempt,
                            final_status="found_pending_with_valid_payload",
                            poll_durations_ms=poll_durations,
                        )

                    # ── Secondary: COMPLETED record with valid payload ──────────────
                    if completed_with_payload:
                        return DBAssertionResult(
                            success=True,
                            meal_logs_found=len(recent),
                            pending_logs_found=0,
                            attempts=attempt,
                            final_status="found_completed_with_valid_payload",
                            poll_durations_ms=poll_durations,
                        )

                    # ── Nothing found → continue polling ───────────────────────────
                    if attempt < self._max_attempts:
                        await asyncio.sleep(self._interval_s)

            except Exception as e:
                last_error = str(e)
                elapsed_ms = int((time.monotonic() - attempt_start) * 1000)
                poll_durations.append(elapsed_ms)

                # ── Infra breakdown detection ──────────────────────────────────
                err_str = str(e).lower()
                pool_exhausted = any(
                    kw in err_str
                    for kw in [
                        "connection pool", "pool exhausted", "pool timeout",
                        "too many connections", "pgbouncer", "connection refused",
                        "cannot connect to database",
                    ]
                )
                if pool_exhausted:
                    raise InfraBreakdownError(
                        f"[DB_Assertion] CONNECTION POOL EXHAUSTED "
                        f"(attempt {attempt}/{self._max_attempts}): {e}"
                    ) from e

                log.warning(
                    "[DB_Assertion] Attempt %d/%d failed (session_id=%s): %s",
                    attempt, self._max_attempts,
                    self._session_id[:8], e
                )
                if attempt < self._max_attempts:
                    await asyncio.sleep(self._interval_s)

        # ── Exhausted all attempts ───────────────────────────────────────────
        total_ms = int((time.monotonic() - self._start_time) * 1000)
        log.error(
            "[DB_Assertion] FAILED after %d attempts (session_id=%s, total=%.1fs): %s",
            self._max_attempts, self._session_id[:8],
            total_ms / 1000, last_error
        )
        return DBAssertionResult(
            success=False,
            meal_logs_found=0,
            pending_logs_found=0,
            attempts=self._max_attempts,
            final_status="timeout_no_valid_logs",
            poll_durations_ms=poll_durations,
            error=last_error,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test run result schemas
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TestRunResult:
    """Kết quả của một test case duy nhất."""
    test_id: str
    tier: str
    status: str           # "passed" | "failed" | "infra_breakdown" | "error" | "skipped"
    overall_score: float  # 0.0 – 1.0
    tier_scores: dict[str, float]
    final_response: str
    event_counts: dict[str, int]
    db_assertion: DBAssertionResult | None
    infra_breakdown: bool = False
    infra_error: str | None = None
    duration_ms: int = 0
    error_message: str | None = None
    routing: str | None = None  # expected_routing từ dataset
    agent_results_summary: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """Báo cáo tổng hợp toàn bộ benchmark run."""
    config: str
    ablation_params: AblationParams
    total_tests: int
    passed: int
    failed: int
    infra_breakdowns: int
    skipped: int
    overall_score_avg: float
    tier_breakdown: dict[str, dict[str, int | float]]
    results: list[TestRunResult]
    duration_seconds: float
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "ablation": {
                "config": self.ablation_params.config.value,
                "ablate_health_monitor": self.ablation_params.ablate_health_monitor,
                "ablate_background_worker": self.ablation_params.ablate_background_worker,
                "ablate_nutrition": self.ablation_params.ablate_nutrition,
                "ablate_fitness": self.ablation_params.ablate_fitness,
            },
            "summary": {
                "total": self.total_tests,
                "passed": self.passed,
                "failed": self.failed,
                "infra_breakdown": self.infra_breakdowns,
                "skipped": self.skipped,
                "pass_rate": round(self.passed / self.total_tests, 4) if self.total_tests else 0,
                "overall_score_avg": round(self.overall_score_avg, 4),
            },
            "tier_breakdown": self.tier_breakdown,
            "duration_seconds": round(self.duration_seconds, 2),
            "timestamp": self.timestamp,
            "results": [
                {
                    "test_id": r.test_id,
                    "tier": r.tier,
                    "status": r.status,
                    "overall_score": round(r.overall_score, 4),
                    "tier_scores": {k: round(v, 4) for k, v in r.tier_scores.items()},
                    "routing": r.routing,
                    "duration_ms": r.duration_ms,
                    "db_assertion": {
                        "success": r.db_assertion.success if r.db_assertion else None,
                        "pending_logs": r.db_assertion.pending_logs_found if r.db_assertion else None,
                        "final_status": r.db_assertion.final_status if r.db_assertion else None,
                        "attempts": r.db_assertion.attempts if r.db_assertion else None,
                    } if r.db_assertion else None,
                    "infra_breakdown": r.infra_breakdown,
                    "error": r.error_message,
                }
                for r in self.results
            ],
        }


# ══════════════════════════════════════════════════════════════════════════════
# SMARunner
# ══════════════════════════════════════════════════════════════════════════════

class SMARunner:
    """
    Main benchmark runner. Coordinates the full test pipeline:

      1. Create ChatSession + authenticate
      2. Load test case from dataset.json
      3. Call SSE streaming endpoint
      4. Aggregate tokens with SSE_Token_Aggregator
      5. Run metrics with SMAMetricSuite
      6. Poll DB with DB_Assertion_Loop
      7. Collect and return TestRunResult

    Ablation modes:
      - BASELINE: bypasses orchestrator → single-agent path
      - PARTIAL: runs multi-agent with component isolation
      - FULL: full pipeline (default)
    """

    STREAM_ENDPOINT = "/api/v1/ai/chat/sessions/{session_id}/messages/stream"
    SESSION_ENDPOINT = "/api/v1/ai/chat/sessions"
    LOGIN_ENDPOINT = "/api/v1/auth/login"
    REGISTER_ENDPOINT = "/api/v1/auth/register"

    def __init__(
        self,
        base_url: str,
        dataset: dict[str, Any],
        ablation: AblationParams,
        db_session_factory,
        metrics_suite,         # SMAMetricSuite instance
        timeout_per_test_s: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._dataset = dataset
        self._ablation = ablation
        self._db_factory = db_session_factory
        self._metrics = metrics_suite
        self._timeout_s = timeout_per_test_s
        self._client: AsyncClient | None = None

    async def _ensure_client(self, auth_token: str) -> AsyncClient:
        # httpx rejects "Bearer " (empty token) as an illegal header value, so
        # only attach Authorization once a real token exists.
        headers = (
            {"Authorization": f"Bearer {auth_token}"} if auth_token else {}
        )
        if self._client is None:
            self._client = AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=httpx.Timeout(self._timeout_s, connect=10.0),
            )
        else:
            if auth_token:
                self._client.headers["Authorization"] = f"Bearer {auth_token}"
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _login(self, client: AsyncClient, email: str, password: str) -> str:
        """OAuth2 password flow → returns access token."""
        resp = await client.post(
            self.LOGIN_ENDPOINT,
            data={"username": email, "password": password},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Login failed ({resp.status_code}): {resp.text}")
        return resp.json()["access_token"]

    async def _create_session(self, client: AsyncClient, title: str = "SMA-Eval Run") -> str:
        """Tạo ChatSession mới → returns session_id string."""
        resp = await client.post(
            self.SESSION_ENDPOINT,
            json={"title": title},
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Session creation failed ({resp.status_code}): {resp.text}")
        return resp.json()["id"]

    def _resolve_test_cases(
        self,
        test_ids: list[str] | None,
        tier: str | None,
    ) -> list[dict[str, Any]]:
        """Load test cases from dataset, filtered by test_ids and/or tier."""
        all_tiers = [
            self._dataset.get("tier_a_hard_constraints", {}).get("test_cases", []),
            self._dataset.get("tier_b_reasoning_consistency", {}).get("test_cases", []),
            self._dataset.get("tier_c_infrastructure_stress", {}).get("test_cases", []),
        ]

        cases: list[dict[str, Any]] = []
        for tier_cases in all_tiers:
            for tc in tier_cases:
                if test_ids and tc.get("test_id") not in test_ids:
                    continue
                if tier and tc.get("tier") != tier:
                    continue
                cases.append(tc)

        if test_ids:
            missing = set(test_ids) - {tc["test_id"] for tc in cases}
            if missing:
                log.warning("[Runner] Unknown test_ids: %s", missing)

        return cases

    async def _send_message_stream(
        self,
        client: AsyncClient,
        session_id: str,
        message: str,
        depth: str = "deep",
    ) -> SSE_Token_Aggregator:
        """
        Gọi SSE streaming endpoint, trả về SSE_Token_Aggregator
        đã được feed toàn bộ luồng.

        Raises InfraBreakdownError nếu phát hiện connection pool exhausted.
        """
        endpoint = self.STREAM_ENDPOINT.format(session_id=session_id)

        try:
            async with client.stream(
                "POST",
                endpoint,
                json={"content": message, "depth": depth},
                timeout=httpx.Timeout(self._timeout_s, connect=10.0),
            ) as response:
                if response.status_code == 503:
                    raise InfraBreakdownError(
                        f"[Stream] 503 Service Unavailable — likely connection pool exhausted "
                        f"(session_id={session_id[:8]})"
                    )
                if response.status_code == 429:
                    raise InfraBreakdownError(
                        f"[Stream] 429 Rate Limited (session_id={session_id[:8]})"
                    )
                if response.status_code != 200:
                    text = await response.aread()
                    raise RuntimeError(
                        f"[Stream] HTTP {response.status_code}: {text[:500]}"
                    )

                aggregator = SSE_Token_Aggregator()
                async for _ in aggregator.feed_stream(response):
                    pass
                return aggregator

        except httpx.PoolTimeout as e:
            raise InfraBreakdownError(
                f"[Stream] Connection pool timeout: {e}"
            ) from e
        except httpx.ConnectError as e:
            raise InfraBreakdownError(
                f"[Stream] Connection error: {e}"
            ) from e

    async def _run_baseline(
        self,
        client: AsyncClient,
        session_id: str,
        message: str,
        user_profile: dict[str, Any],
    ) -> tuple[str, dict[str, Any], dict[str, Any]]:
        """
        BASELINE mode: single-agent direct path.

        Bypasses Multi-Agent Orchestrator. Sends message via a lightweight
        single-agent path (POST /api/v1/nutrition/meal-suggest if available,
        else a simplified direct Groq call).

        Returns (final_response, empty_agent_results, {}).
        """
        log.info("[Runner/BASELINE] Using single-agent direct path")

        # Try to use the /api/v1/nutrition/meal-suggest endpoint as baseline
        # if it exists. Fall back to a mock single-agent call.
        resp = await client.post(
            "/api/v1/nutrition/meal-suggest",
            json={
                "message": message,
                "user_id": str(user_profile.get("user_id", "")),
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

        if resp.status_code == 200:
            data = resp.json()
            # Try to extract text from the response
            response_text = data.get("suggestion", "") or data.get("message", "") or data.get("content", "")
            if response_text:
                return response_text, {}, {}
            # Fall through to mock

        # Mock baseline: call Groq directly with minimal context
        mock_response = await self._mock_single_agent_response(message, user_profile)
        return mock_response, {}, {}

    async def _mock_single_agent_response(
        self,
        message: str,
        user_profile: dict[str, Any],
    ) -> str:
        """Mock single-agent response for BASELINE mode (when no direct endpoint exists)."""
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.GROQ_API_KEY or "")
            gender_str = user_profile.get("gender", "nam")
            age = user_profile.get("age", 30)
            weight = user_profile.get("current_weight_kg", 70)
            height = user_profile.get("height_cm", 170)
            allergies = user_profile.get("allergies", {})
            active_allergens = [k for k, v in (allergies or {}).items() if v]

            bmr = calculate_bmr(weight, height, age, gender_str)

            system_prompt = (
                f"You are a single-agent nutrition assistant (BASELINE mode). "
                f"User has BMR={bmr:.0f} kcal. Allergies: {active_allergens}. "
                "Provide direct nutrition advice. Respond in Vietnamese. "
                "Keep it concise (max 200 words)."
            )
            resp = await client.chat.completions.create(
                model=settings.GROQ_TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                max_tokens=300,
                temperature=0.3,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            log.warning("[Runner/BASELINE] Single-agent call failed: %s", e)
            return f"[BASELINE] {message[:100]}"

    async def run_single_test(
        self,
        test_case: dict[str, Any],
        auth_token: str,
    ) -> TestRunResult:
        """
        Thực thi một test case duy nhất.

        Pipeline:
          1. Resolve BMR/TDEE từ profile data
          2. Create session
          3. Send message (BASELINE / PARTIAL / FULL mode)
          4. Aggregate SSE tokens
          5. Run metrics
          6. Poll DB for PENDING MealLogs
          7. Return TestRunResult
        """
        test_id = test_case["test_id"]
        tier = test_case["tier"]
        message = test_case["input_message"]
        user_profile = test_case.get("user_profile", {})
        expected_routing = test_case.get("expected_routing")
        start_time = time.monotonic()

        log.info(
            "[Runner] Starting test %s (tier=%s, routing=%s, mode=%s)",
            test_id, tier, expected_routing, self._ablation.config.value
        )

        try:
            client = await self._ensure_client(auth_token)
            session_id = await self._create_session(client, title=f"SMA-Eval {test_id}")

            # ── Compute BMR / TDEE ──────────────────────────────────────────
            bmr, tdee = self._compute_bmr_tdee(user_profile)

            # ── Send message (mode-dependent) ─────────────────────────────────
            if self._ablation.config == AblationConfig.BASELINE:
                final_response, agent_results_summary, event_counts = \
                    await self._run_baseline(client, session_id, message, user_profile)
                aggregator: SSE_Token_Aggregator | None = None
            else:
                aggregator = await self._send_message_stream(
                    client, session_id, message
                )
                final_response = aggregator.final_response
                event_counts = aggregator.event_counts
                agent_results_summary = {}

            duration_ms = int((time.monotonic() - start_time) * 1000)

            # ── Run metrics ─────────────────────────────────────────────────
            # Reconstruct AgentResult objects from SSE agent_result events
            # so InterAgentConsistencyMetric and TaskDecompositionQualityMetric can run.
            resolved_agent_results: dict[str, Any] = {}
            if aggregator is not None and hasattr(aggregator, "agent_results"):
                raw = aggregator.agent_results
                if raw:
                    resolved_agent_results = _build_agent_results_from_sse(raw)
                    log.info(
                        "[Runner] Extracted %d agent results from SSE: %s",
                        len(resolved_agent_results), list(resolved_agent_results.keys())
                    )

            metric_result = await self._metrics.evaluate(
                test_case=test_case,
                agent_results=resolved_agent_results,
                final_response=final_response,
                user_profile=user_profile,
                bmr=bmr,
                tdee=tdee,
            )

            # ── DB assertion loop ────────────────────────────────────────────
            db_result: DBAssertionResult | None = None
            if tier != "C":  # TIER C burst tests don't create meal logs
                db_assertion = DB_Assertion_Loop(
                    db_session_factory=self._db_factory,
                    session_id=session_id,
                    user_id=str(user_profile.get("user_id", "")),
                    ablate_worker=self._ablation.ablate_background_worker,
                )
                db_result = await db_assertion.run()

            return TestRunResult(
                test_id=test_id,
                tier=tier,
                status="passed" if metric_result.overall_score >= 0.8 else "failed",
                overall_score=metric_result.overall_score,
                tier_scores={
                    "NUTRITION_SAFETY": metric_result.nutrition_safety_score,
                    "DOMAIN_QUALITY": metric_result.domain_quality_score,
                    "MULTI_AGENT_PERFORMANCE": metric_result.multi_agent_score,
                },
                final_response=final_response[:500],  # truncate for report
                event_counts=event_counts or {},
                db_assertion=db_result,
                infra_breakdown=False,
                duration_ms=duration_ms,
                routing=expected_routing,
                agent_results_summary=agent_results_summary,
            )

        except InfraBreakdownError as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.error("[Runner] INFRA BREAKDOWN in test %s: %s", test_id, e)
            return TestRunResult(
                test_id=test_id,
                tier=tier,
                status="infra_breakdown",
                overall_score=0.0,
                tier_scores={},
                final_response="",
                event_counts={},
                db_assertion=None,
                infra_breakdown=True,
                infra_error=str(e),
                duration_ms=duration_ms,
                error_message=f"Infra breakdown: {e}",
                routing=expected_routing,
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log.exception("[Runner] Test %s raised exception: %s", test_id, e)
            return TestRunResult(
                test_id=test_id,
                tier=tier,
                status="error",
                overall_score=0.0,
                tier_scores={},
                final_response="",
                event_counts={},
                db_assertion=None,
                infra_breakdown=False,
                duration_ms=duration_ms,
                error_message=str(e),
                routing=expected_routing,
            )

    def _compute_bmr_tdee(
        self, user_profile: dict[str, Any]
    ) -> tuple[float, float]:
        """Compute BMR/TDEE từ user_profile dict (giống logic trong conftest)."""
        gender_str = user_profile.get("gender", "nam")
        age = user_profile.get("age", 30)
        weight = float(user_profile.get("current_weight_kg", 70))
        height = float(user_profile.get("height_cm", 170))
        activity_str = user_profile.get("activity_level", "it_van_dong")

        activity_map = {
            "it_van_dong": 1.2,
            "van_dong_nhe": 1.375,
            "van_dong_vua": 1.55,
            "van_dong_nhieu": 1.725,
            "van_dong_rat_nhieu": 1.9,
        }
        multiplier = activity_map.get(activity_str, 1.2)

        bmr = calculate_bmr(weight, height, age, gender_str)
        tdee = bmr * multiplier
        return bmr, tdee

    async def run_benchmark(
        self,
        test_ids: list[str] | None = None,
        tier: str | None = None,
    ) -> BenchmarkReport:
        """
        Chạy toàn bộ benchmark suite.

        Args:
          test_ids: danh sách test_id cụ thể (None = chạy tất cả)
          tier:    "A" | "B" | "C" để lọc (None = tất cả)
        """
        import json as _json

        cases = self._resolve_test_cases(test_ids, tier)
        if not cases:
            raise ValueError(f"No test cases found for ids={test_ids}, tier={tier}")

        overall_start = time.monotonic()
        log.info(
            "[Runner] Starting benchmark: config=%s, cases=%d, tier=%s",
            self._ablation.config.value, len(cases), tier or "ALL"
        )

        # ── Bootstrap: create SMA-Eval test user and get token ───────────────
        bootstrap_user = await self._bootstrap_user()
        auth_token = await self._login(
            await self._ensure_client(""),
            bootstrap_user["email"],
            bootstrap_user["password"],
        )
        # Replace client with authenticated client
        self._client = None
        await self._ensure_client(auth_token)

        results: list[TestRunResult] = []
        for case in cases:
            result = await self.run_single_test(case, auth_token)
            results.append(result)

        overall_duration = time.monotonic() - overall_start

        # ── Cleanup test user ───────────────────────────────────────────────
        await self._cleanup_user(bootstrap_user["user_id"])
        await self.close()

        # ── Aggregate report ─────────────────────────────────────────────────
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        infra_bd = sum(1 for r in results if r.status == "infra_breakdown")
        skipped = sum(1 for r in results if r.status == "skipped")
        score_avg = (
            sum(r.overall_score for r in results) / len(results)
            if results else 0.0
        )

        # Tier breakdown
        tier_stats: dict[str, dict[str, Any]] = {}
        for t in ("A", "B", "C"):
            tier_results = [r for r in results if r.tier == t]
            if tier_results:
                tier_stats[t] = {
                    "total": len(tier_results),
                    "passed": sum(1 for r in tier_results if r.status == "passed"),
                    "failed": sum(1 for r in tier_results if r.status == "failed"),
                    "score_avg": round(
                        sum(r.overall_score for r in tier_results) / len(tier_results), 4
                    ),
                }

        report = BenchmarkReport(
            config=self._ablation.config.value,
            ablation_params=self._ablation,
            total_tests=len(results),
            passed=passed,
            failed=failed,
            infra_breakdowns=infra_bd,
            skipped=skipped,
            overall_score_avg=score_avg,
            tier_breakdown=tier_stats,
            results=results,
            duration_seconds=overall_duration,
            timestamp=datetime.now().isoformat(),
        )

        log.info(
            "[Runner] Benchmark complete: %d/%d passed, "
            "score_avg=%.4f, duration=%.1fs",
            passed, len(results), score_avg, overall_duration
        )

        return report

    # ── Bootstrap helpers ────────────────────────────────────────────────────

    async def _bootstrap_user(self) -> dict[str, str]:
        """
        Tạo tạm một user để chạy benchmark bằng cách gọi API register
        (không phải SQL thẳng) — đảm bảo user nằm cùng database với
        API process đang chạy.
        """
        from uuid import uuid4

        plain_password = f"sma_pw_{uuid4().hex[:8]}"
        email = f"sma-runner-{uuid4().hex[:8]}@benchmark.example.com"

        unauth_client = await self._ensure_client("")
        resp = await unauth_client.post(
            self.REGISTER_ENDPOINT,
            json={
                "email": email,
                "password": plain_password,
                "full_name": "SMA Runner User",
            },
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"User registration failed ({resp.status_code}): {resp.text}"
            )
        body = resp.json()
        user_id = body.get("id") or body.get("user", {}).get("id")
        if not user_id:
            raise RuntimeError(f"Register response missing user id: {body}")

        return {
            "email": email,
            "user_id": str(user_id),
            "password": plain_password,
        }

    async def _cleanup_user(self, user_id: str) -> None:
        """Xóa bootstrap user sau khi benchmark xong."""
        from uuid import UUID
        try:
            async with self._db_factory() as session:
                from sqlalchemy import text
                await session.execute(text(
                    "DELETE FROM meal_items WHERE meal_log_id IN "
                    "(SELECT id FROM meal_logs WHERE user_id = :uid)"
                ), {"uid": user_id})
                await session.execute(text(
                    "DELETE FROM meal_logs WHERE user_id = :uid"
                ), {"uid": user_id})
                await session.execute(text(
                    "DELETE FROM nutrition_goals WHERE user_id = :uid"
                ), {"uid": user_id})
                await session.execute(text(
                    "DELETE FROM user_memory WHERE user_id = :uid"
                ), {"uid": user_id})
                await session.execute(text(
                    "DELETE FROM user_profiles WHERE user_id = :uid"
                ), {"uid": user_id})
                await session.execute(text(
                    "DELETE FROM users WHERE id = :uid"
                ), {"uid": user_id})
                await session.commit()
        except Exception as e:
            log.warning("[Runner] Cleanup failed for user %s: %s", user_id[:8], e)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m tests.sma_eval.runner",
        description="SMA-Eval v1 Benchmark Runner — SmartMeal Multi-Agent Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ablation configs:
  baseline  Bypass Multi-Agent → single-agent direct path
  partial   Multi-Agent with component isolation (use --ablation-* flags)
  full      Full Hybrid Pipeline (default)

Examples:
  python -m tests.sma_eval.runner --config full
  python -m tests.sma_eval.runner --config baseline --test-ids A-ALLERGEN-001 B-CONFLICT-001
  python -m tests.sma_eval.runner --config partial --ablation-block health_monitor --tier A
  python -m tests.sma_eval.runner --config full --tier C --output results.json
        """,
    )
    p.add_argument(
        "--config",
        choices=["baseline", "partial", "full"],
        default="full",
        help="Ablation configuration mode (default: full)",
    )
    p.add_argument(
        "--test-ids",
        nargs="*",
        metavar="ID",
        help="Specific test IDs to run (e.g. A-ALLERGEN-001 B-CONFLICT-001). "
             "If omitted, runs all matching tests.",
    )
    p.add_argument(
        "--tier",
        choices=["A", "B", "C"],
        help="Filter tests by tier only",
    )
    p.add_argument(
        "--ablation-block",
        action="append",
        dest="ablation_blocks",
        choices=["health_monitor", "background_worker", "nutrition", "fitness"],
        help="[PARTIAL mode] Block specific agent/component. "
             "Can be specified multiple times.",
    )
    p.add_argument(
        "--ablation-health-monitor",
        action="store_true",
        dest="ablate_health_monitor",
        help="[PARTIAL mode] Block HealthMonitor agent",
    )
    p.add_argument(
        "--ablation-background-worker",
        action="store_true",
        dest="ablate_background_worker",
        help="[PARTIAL mode] Block background ExtractorAgent worker",
    )
    p.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    p.add_argument(
        "--output", "-o",
        dest="output_file",
        help="Write JSON report to file",
    )
    p.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v INFO, -vv DEBUG)",
    )
    return p


async def _main():
    parser = _build_argparser()
    args = parser.parse_args()

    # ── Logging setup ─────────────────────────────────────────────────────
    level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}.get(
        args.verbose, logging.DEBUG
    )
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Load dataset ──────────────────────────────────────────────────────
    dataset_path = _Path(__file__).parent / "dataset.json"
    if not dataset_path.exists():
        parser.error(f"dataset.json not found at {dataset_path}")
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    # ── Resolve ablation params ───────────────────────────────────────────
    ablation_blocks = set(args.ablation_blocks or [])
    ablation = AblationParams(
        config=AblationConfig(args.config),
        ablate_health_monitor=(
            args.ablate_health_monitor or "health_monitor" in ablation_blocks
        ),
        ablate_background_worker=(
            args.ablate_background_worker or "background_worker" in ablation_blocks
        ),
    )
    if args.config == "partial" and not any([
        ablation.ablate_health_monitor, ablation.ablate_background_worker,
        ablation.ablate_nutrition, ablation.ablate_fitness,
    ]):
        print(
            "[WARNING] PARTIAL mode with no components blocked. "
            "Use --ablation-block or individual --ablation-* flags. "
            "Run with --config full for full pipeline.",
            file=sys.stderr
        )

    # ── DB session factory ────────────────────────────────────────────────
    from app.core.config import settings as _settings
    if not _settings.TEST_DATABASE_URL:
        print(
            "ERROR: TEST_DATABASE_URL not configured. "
            "Set it in your environment or .env file.",
            file=sys.stderr
        )
        sys.exit(3)

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    db_engine = create_async_engine(
        _settings.TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=4,
        max_overflow=8,
        connect_args={
            "server_settings": {"application_name": "sma_eval_runner"},
            "statement_cache_size": 0,
            "max_cached_statement_lifetime": 0,
        },
    )
    db_factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        autoflush=False,
    )

    # ── Metrics suite ─────────────────────────────────────────────────────
    from tests.sma_eval.metrics import SMAMetricSuite
    metrics = SMAMetricSuite()

    # ── Build runner ──────────────────────────────────────────────────────
    runner = SMARunner(
        base_url=args.base_url,
        dataset=dataset,
        ablation=ablation,
        db_session_factory=db_factory,
        metrics_suite=metrics,
    )

    # ── Run benchmark ─────────────────────────────────────────────────────
    try:
        report = await runner.run_benchmark(
            test_ids=args.test_ids,
            tier=args.tier,
        )
    except InfraBreakdownError as e:
        print(f"\n[EXIT] INFRA BREAKDOWN: {e}", file=sys.stderr)
        await runner.close()
        await db_engine.dispose()
        sys.exit(2)
    except Exception as e:
        print(f"\n[EXIT] FATAL: {e}", file=sys.stderr)
        await runner.close()
        await db_engine.dispose()
        sys.exit(3)
    finally:
        await db_engine.dispose()

    # ── Output ────────────────────────────────────────────────────────────
    report_dict = report.to_dict()

    if args.output_file:
        output_path = _Path(args.output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
        print(f"\n[OK] Report written to {output_path}")
    else:
        print(json.dumps(report_dict, ensure_ascii=False, indent=2))

    # ── Exit code ─────────────────────────────────────────────────────────
    if report.infra_breakdowns > 0:
        sys.exit(2)
    if report.failed > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(_main())
