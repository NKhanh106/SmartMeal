"""
Conversation Insights Service.

Sau mỗi tin nhắn AI, trích xuất thông tin cốt lõi từ cuộc trò chuyện
và lưu vào bảng conversation_insights.

Các thông tin được trích xuất:
- Sở thích ăn uống (thích món nào, không thích món nào, ăn chay, ...)
- Ràng buộc sức khỏe (dị ứng, bệnh lý, hạn chế ăn gì)
- Ghi chú tập luyện (tần suất, loại hình, hạn chế)
- Thay đổi mục tiêu
- Thông tin tổng quát

Deduplication: cùng (user_id, key) → upsert.

Performance:
- AI calls are wrapped with 10s timeout to prevent hanging on slow providers.
- Upsert uses batch fetch (not N+1) after flush for efficiency.
"""

import asyncio
import json
import logging
import time
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.chatbot.prompts import build_insight_extraction_prompt
from app.core.config import settings
from app.models.conversation_insight import ConversationInsight
from app.schemas.chat import ExtractedInsightItem, ExtractedInsightsOutput
from app.services.ai_log_service import create_ai_log

logger = logging.getLogger(__name__)

_INSIGHT_EXTRACTION_PROMPT_VERSION = "insight_extraction_v1"
_INSIGHT_EXTRACTION_TIMEOUT_SECONDS = 10


async def extract_insights_from_conversation(
    db: AsyncSession,
    user_id: UUID,
    session_id: UUID,
    recent_messages: list[dict],
) -> ExtractedInsightsOutput:
    """
    Gọi AI để trích xuất thông tin cốt lõi từ cuộc trò chuyện.

    Args:
        db: DB session
        user_id: ID của người dùng
        session_id: ID của phiên chat
        recent_messages: Danh sách tin nhắn gần đây,
                         mỗi item có dạng {"role": "user"|"assistant", "content": str}

    Returns:
        ExtractedInsightsOutput với danh sách insights trích xuất được.
        Nếu fail → trả về empty list (không break chat).
    """
    if not recent_messages:
        return ExtractedInsightsOutput(insights=[], has_new_information=False)

    prompt = build_insight_extraction_prompt(recent_messages)
    provider = get_ai_provider(settings.AI_CHAT_PROVIDER)
    start_time = time.perf_counter()
    model_name = (
        settings.GEMINI_MODEL
        if settings.AI_CHAT_PROVIDER == "gemini"
        else settings.GROQ_TEXT_MODEL
    )

    try:
        # Dùng generate_text vì đây là text-to-text, không phải vision
        # Wrap with asyncio.wait_for to add timeout (prevents slow AI provider from hanging)
        raw_response = await asyncio.wait_for(
            run_in_threadpool(
                provider.generate_text,
                system_prompt=(
                    "Ban la AI tro giup SmartMeal. Tra loi JSON hop le theo schema duoc yeu cau. "
                    "Chi tra ve JSON, khong giai thich gi them."
                ),
                user_prompt=prompt,
                temperature=0.1,
            ),
            timeout=_INSIGHT_EXTRACTION_TIMEOUT_SECONDS,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Parse JSON response
        import json
        try:
            parsed = json.loads(raw_response)
            result = ExtractedInsightsOutput.model_validate(parsed)
        except (json.JSONDecodeError, ValueError) as parse_err:
            logger.warning(
                "Failed to parse insight extraction JSON for user %s session %s: %s. Raw: %s",
                user_id,
                session_id,
                parse_err,
                raw_response[:200],
            )
            result = ExtractedInsightsOutput(insights=[], has_new_information=False)

        await create_ai_log(
            db=db,
            user_id=user_id,
            task_type="insight_extraction",
            provider_name=settings.AI_CHAT_PROVIDER,
            model_name=model_name,
            prompt_version=_INSIGHT_EXTRACTION_PROMPT_VERSION,
            input_summary=f"session_id={session_id}, messages_count={len(recent_messages)}",
            raw_response={"text": raw_response[:2000]},
            status="success",
            latency_ms=latency_ms,
        )
        await db.commit()
        return result

    except Exception as exc:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        await create_ai_log(
            db=db,
            user_id=user_id,
            task_type="insight_extraction",
            provider_name=settings.AI_CHAT_PROVIDER,
            model_name=model_name,
            prompt_version=_INSIGHT_EXTRACTION_PROMPT_VERSION,
            input_summary=f"session_id={session_id}, messages_count={len(recent_messages)}",
            raw_response=None,
            status="failed",
            error_message=str(exc),
            latency_ms=latency_ms,
        )
        await db.commit()

        logger.warning(
            "Failed to extract insights for user %s session %s: %s",
            user_id,
            session_id,
            exc,
        )
        # Không raise — insight extraction là optional, không break chat
        return ExtractedInsightsOutput(insights=[], has_new_information=False)


async def upsert_conversation_insights(
    db: AsyncSession,
    user_id: UUID,
    session_id: UUID,
    insights: list[ExtractedInsightItem],
) -> list[ConversationInsight]:
    """
    Upsert insights vào DB.

    Với mỗi insight:
    - Nếu (user_id, key) đã tồn tại → UPDATE value, summary, updated_at
    - Nếu chưa → INSERT

    Dùng PostgreSQL upsert (ON CONFLICT DO UPDATE) để đảm bảo atomicity.
    """
    if not insights:
        return []

    # Batch upsert: execute all inserts first, then fetch in one query (fixes N+1)
    for item in insights:
        stmt = pg_insert(ConversationInsight).values(
            user_id=user_id,
            session_id=session_id,
            insight_type=item.insight_type,
            key=item.key,
            value=item.value,
            summary=item.summary,
            is_active=True,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "key"],
            set_={
                "session_id": session_id,
                "insight_type": item.insight_type,
                "value": item.value,
                "summary": item.summary,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        await db.execute(stmt)

    # Flush all upserts, then batch fetch all records at once (instead of N+1 fetches)
    await db.flush()

    insight_keys = [item.key for item in insights]
    result = await db.execute(
        select(ConversationInsight).where(
            ConversationInsight.user_id == user_id,
            ConversationInsight.key.in_(insight_keys),
        )
    )
    results = list(result.scalars().all())

    await db.commit()
    logger.info(
        "Upserted %d insights for user %s session %s",
        len(insights),
        user_id,
        session_id,
    )
    return results


async def get_active_insights(
    db: AsyncSession,
    user_id: UUID,
) -> list[ConversationInsight]:
    """
    Lấy tất cả insights đang active của 1 user.
    Dùng để bổ sung vào chatbot context.
    """
    result = await db.execute(
        select(ConversationInsight)
        .where(
            ConversationInsight.user_id == user_id,
            ConversationInsight.is_active.is_(True),
        )
        .order_by(ConversationInsight.updated_at.desc())
    )
    return list(result.scalars().all())


async def deactivate_insight(
    db: AsyncSession,
    insight_id: UUID,
    user_id: UUID,
) -> bool:
    """
    Soft-delete một insight (set is_active=False).
    Chỉ user sở hữu mới được xóa.
    """
    result = await db.execute(
        select(ConversationInsight).where(
            ConversationInsight.id == insight_id,
            ConversationInsight.user_id == user_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return False

    record.is_active = False
    await db.commit()
    return True
