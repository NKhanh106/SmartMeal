import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.chatbot.context_builder import build_chatbot_context
from app.chatbot.prompts import (
    CHATBOT_PROMPT_VERSION,
    CHATBOT_SYSTEM_PROMPT,
    build_chatbot_user_prompt,
)
from app.chatbot.utils import build_chat_title
from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession
from app.services.ai_log_service import create_ai_log


async def create_chat_session(
    db: AsyncSession,
    user_id: UUID,
    title: str | None = None,
) -> ChatSession:
    session = ChatSession(
        user_id=user_id,
        title=title or "Cuoc tro chuyen moi",
        status="active",
    )
    db.add(session)
    await db.flush()
    return session


async def list_chat_sessions(
    db: AsyncSession,
    user_id: UUID,
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.status != "deleted")
        .order_by(ChatSession.last_message_at.desc().nullslast(), ChatSession.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_chat_messages(
    db: AsyncSession,
    session_id: UUID,
) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


async def get_chat_session_or_404(
    db: AsyncSession,
    session_id: UUID,
) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.status != "deleted")
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )
    return session


async def save_chat_message(
    db: AsyncSession,
    session_id: UUID,
    role: str,
    content: str,
    metadata: dict | None = None,
    ai_analysis_log_id: UUID | None = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        ai_analysis_log_id=ai_analysis_log_id,
        role=role,
        content=content,
        meta_data=metadata,
    )
    db.add(msg)
    await db.flush()
    return msg


async def send_chat_message(
    db: AsyncSession,
    session_id: UUID,
    user_content: str,
):
    session = await get_chat_session_or_404(db, session_id)
    user_id = session.user_id
    now = datetime.now(timezone.utc)

    user_message = await save_chat_message(
        db=db,
        session_id=session_id,
        role="user",
        content=user_content,
    )

    if session.title == "Cuoc tro chuyen moi":
        session.title = build_chat_title(user_content)
    session.last_message_at = now

    context = await build_chatbot_context(
        db=db,
        user_id=user_id,
        session_id=session.id,
        user_question=user_content,
    )

    user_prompt = build_chatbot_user_prompt(context)
    provider = get_ai_provider(settings.AI_CHAT_PROVIDER)
    start_time = time.perf_counter()
    model_name = (
        settings.GEMINI_MODEL
        if settings.AI_CHAT_PROVIDER == "gemini"
        else settings.GROQ_TEXT_MODEL
    )

    try:
        answer = await run_in_threadpool(
            provider.generate_text,
            system_prompt=CHATBOT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.4,
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        ai_log = await create_ai_log(
            db=db,
            user_id=user_id,
            task_type="chatbot",
            provider_name=settings.AI_CHAT_PROVIDER,
            model_name=model_name,
            prompt_version=CHATBOT_PROMPT_VERSION,
            input_summary=f"provider={settings.AI_CHAT_PROVIDER}, session_id={session_id}",
            raw_response={
                "answer": answer,
                "context_keys": list(context.keys()),
            },
            status="success",
            latency_ms=latency_ms,
        )

        assistant_message = await save_chat_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=answer,
            metadata={
                "ai_log_id": str(ai_log.id),
                "provider": settings.AI_CHAT_PROVIDER,
                "prompt_version": CHATBOT_PROMPT_VERSION,
            },
            ai_analysis_log_id=ai_log.id,
        )
        session.last_message_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user_message)
        await db.refresh(assistant_message)
        return user_message, assistant_message

    except Exception as exc:
        await db.rollback()

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        await create_ai_log(
            db=db,
            user_id=user_id,
            task_type="chatbot",
            provider_name=settings.AI_CHAT_PROVIDER,
            model_name=model_name,
            prompt_version=CHATBOT_PROMPT_VERSION,
            input_summary=f"provider={settings.AI_CHAT_PROVIDER}, session_id={session_id}",
            raw_response=None,
            status="failed",
            error_message=str(exc),
            latency_ms=latency_ms,
        )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tro ly AI hien khong phan hoi. Vui long thu lai sau.",
        )
