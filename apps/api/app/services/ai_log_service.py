from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_log import AILog


MAX_RAW_RESPONSE_LEN = 500


async def create_ai_log(
    db: AsyncSession,
    user_id: UUID | None,
    task_type: str,
    model_name: str | None,
    prompt_version: str | None,
    input_summary: str,
    status: str,
    latency_ms: int,
    raw_response: dict | None = None,
    error_message: str | None = None,
    provider_name: str | None = None,
) -> AILog:
    # Store only a debug summary of the raw response (max 500 chars).
    # Full JSON blobs cause DB bloat (KB per record).
    truncated_response: str | None = None
    if raw_response:
        serialized = str(raw_response)
        truncated_response = serialized[:MAX_RAW_RESPONSE_LEN]

    log = AILog(
        user_id=user_id,
        task_type=task_type,
        provider_name=provider_name,
        model_name=model_name,
        prompt_version=prompt_version,
        input_summary=input_summary,
        raw_response=truncated_response,  # type: ignore — column is TEXT, not JSONB
        status=status,
        error_message=error_message,
        latency_ms=latency_ms,
    )
    db.add(log)
    await db.flush()
    return log
