"""
Admin endpoints for system monitoring and debugging.
Requires admin role — all endpoints are gated by require_admin dependency.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.agent_run import AgentRun
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ─── Agent Stats ───────────────────────────────────────────────────────────────

@router.get("/agents/stats")
async def get_agent_stats(
    hours: int = Query(default=24, ge=1, le=168),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Aggregate agent performance statistics from agent_runs table.

    Returns per-agent breakdown:
    - Run counts (total, completed, failed, skipped)
    - Average latency (ms)
    - Token usage (input + output)
    - Failure rate (%)

    Also returns recent failures and trigger distribution.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # ── Per-agent aggregates ───────────────────────────────────────────────
    agent_stats_query = (
        select(
            AgentRun.agent_name,
            func.count(AgentRun.id).label("total_runs"),
            func.count(AgentRun.id)
            .filter(AgentRun.status == "completed")
            .label("completed_runs"),
            func.count(AgentRun.id)
            .filter(AgentRun.status == "failed")
            .label("failed_runs"),
            func.count(AgentRun.id)
            .filter(AgentRun.status == "skipped")
            .label("skipped_runs"),
            func.avg(AgentRun.latency_ms)
            .filter(AgentRun.latency_ms.isnot(None))
            .label("avg_latency_ms"),
            func.max(AgentRun.latency_ms)
            .label("max_latency_ms"),
            func.sum(AgentRun.input_tokens)
            .label("total_input_tokens"),
            func.sum(AgentRun.output_tokens)
            .label("total_output_tokens"),
            func.count(AgentRun.id)
            .filter(AgentRun.status == "failed")
            .label("failure_count"),
        )
        .where(AgentRun.created_at >= cutoff)
        .group_by(AgentRun.agent_name)
        .order_by(func.count(AgentRun.id).desc())
    )

    result = await db.execute(agent_stats_query)
    raw_rows = result.all()

    # Build per-agent stats
    agent_rows = []
    for row in raw_rows:
        total = int(row.total_runs or 0)
        completed = int(row.completed_runs or 0)
        failed = int(row.failed_runs or 0)
        skipped = int(row.skipped_runs or 0)

        failure_rate = round((failed / total * 100), 2) if total > 0 else 0.0
        avg_latency = round(float(row.avg_latency_ms or 0))
        max_latency = int(row.max_latency_ms or 0)
        total_input_tokens = int(row.total_input_tokens or 0)
        total_output_tokens = int(row.total_output_tokens or 0)
        total_tokens = total_input_tokens + total_output_tokens

        # Format token count for display (e.g. "128k")
        def format_tokens(n: int) -> str:
            if n >= 1_000_000:
                return f"{n / 1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n / 1_000:.0f}k"
            return str(n)

        agent_rows.append({
            "agent_name": row.agent_name,
            "total_runs": total,
            "completed_runs": completed,
            "failed_runs": failed,
            "skipped_runs": skipped,
            "failure_rate_pct": failure_rate,
            "avg_latency_ms": avg_latency,
            "max_latency_ms": max_latency,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens_formatted": format_tokens(total_tokens),
        })

    # ── Recent failures (last 10) ────────────────────────────────────────
    failures_query = (
        select(
            AgentRun.run_id,
            AgentRun.agent_name,
            AgentRun.trigger,
            AgentRun.user_id,
            AgentRun.error_message,
            AgentRun.created_at,
            AgentRun.latency_ms,
        )
        .where(
            AgentRun.status == "failed",
            AgentRun.created_at >= cutoff,
        )
        .order_by(AgentRun.created_at.desc())
        .limit(10)
    )
    failures_result = await db.execute(failures_query)
    failure_rows = failures_result.all()

    recent_failures = []
    for f in failure_rows:
        recent_failures.append({
            "run_id": f.run_id,
            "agent_name": f.agent_name,
            "trigger": f.trigger,
            "user_id": str(f.user_id),
            "error_message": (f.error_message or "")[:200],
            "latency_ms": f.latency_ms,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })

    # ── Trigger distribution ─────────────────────────────────────────────
    trigger_query = (
        select(
            AgentRun.trigger,
            func.count(AgentRun.id).label("count"),
        )
        .where(
            AgentRun.created_at >= cutoff,
        )
        .group_by(AgentRun.trigger)
        .order_by(func.count(AgentRun.id).desc())
    )
    trigger_result = await db.execute(trigger_query)
    trigger_rows = trigger_result.all()

    total_triggers = sum(int(r.count) for r in trigger_rows) or 1
    trigger_distribution = []
    for r in trigger_rows:
        count = int(r.count)
        trigger_distribution.append({
            "trigger": r.trigger,
            "count": count,
            "pct": round(count / total_triggers * 100, 1),
        })

    # ── Orchestrator summary ──────────────────────────────────────────────
    orchestrator_row = next((a for a in agent_rows if a["agent_name"] == "orchestrator"), None)
    orchestrator_total = orchestrator_row["total_runs"] if orchestrator_row else 0

    return {
        "period_hours": hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_runs": sum(a["total_runs"] for a in agent_rows),
        "orchestrator_runs": orchestrator_total,
        "agents": agent_rows,
        "trigger_distribution": trigger_distribution,
        "recent_failures": recent_failures,
        "failure_summary": {
            "total": sum(int(f["failed_runs"]) for f in agent_rows),
            "by_agent": {
                f["agent_name"]: f["failed_runs"]
                for f in agent_rows
                if f["failed_runs"] > 0
            },
        },
    }


# ─── Agent Runs ────────────────────────────────────────────────────────────────

@router.get("/agents/runs")
async def get_agent_runs(
    agent_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    List agent runs with optional filtering.
    Admin-only debug endpoint.
    """
    query = select(AgentRun).order_by(AgentRun.created_at.desc())

    if agent_name:
        query = query.where(AgentRun.agent_name == agent_name)
    if status:
        query = query.where(AgentRun.status == status)

    count_query = select(func.count(AgentRun.id))
    if agent_name:
        count_query = count_query.where(AgentRun.agent_name == agent_name)
    if status:
        count_query = count_query.where(AgentRun.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    items = [
        {
            "run_id": r.run_id,
            "agent_name": r.agent_name,
            "user_id": str(r.user_id),
            "session_id": str(r.session_id) if r.session_id else None,
            "trigger": r.trigger,
            "status": r.status,
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "input_summary": (r.input_summary or "")[:100],
            "output_summary": (r.output_summary or "")[:200],
            "error_message": (r.error_message or "")[:200],
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in rows
    ]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/agents/runs/{run_id}")
async def get_agent_run_detail(
    run_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed info for a single agent run."""
    result = await db.execute(
        select(AgentRun).where(AgentRun.run_id == run_id)
    )
    run = result.scalar_one_or_none()

    if not run:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Agent run not found.")

    return {
        "run_id": run.run_id,
        "agent_name": run.agent_name,
        "user_id": str(run.user_id),
        "session_id": str(run.session_id) if run.session_id else None,
        "trigger": run.trigger,
        "status": run.status,
        "latency_ms": run.latency_ms,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "input_summary": run.input_summary,
        "output_summary": run.output_summary,
        "error_message": run.error_message,
        "extra_data": run.extra_data,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
