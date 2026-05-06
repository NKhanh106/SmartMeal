import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.chatbot.service import (
    create_chat_session,
    get_chat_messages,
    list_chat_sessions,
    save_chat_message,
    send_chat_message,
)
from app.chatbot.prompts import (
    CHATBOT_PROMPT_VERSION,
    CHATBOT_SYSTEM_PROMPT,
    build_chatbot_user_prompt,
)
from app.chatbot.context_builder import build_chatbot_context
from app.core.rate_limiter import limiter
from app.core.config import settings
from app.core.cache import cache_get, cache_set, make_cache_key
from app.db.session import get_db
from app.models.chat import ChatSession
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSendMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
)

router = APIRouter(prefix="/ai/chat", tags=["AI Chatbot"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await create_chat_session(
        db=db,
        user_id=current_user.id,
        title=payload.title,
    )
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions/user", response_model=list[ChatSessionResponse])
async def get_my_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_chat_sessions(db=db, user_id=current_user.id)


@router.get("/sessions/user/{user_id}", response_model=list[ChatSessionResponse])
async def get_user_chat_sessions(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_user_access(current_user, user_id)
    return await list_chat_sessions(db=db, user_id=user_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_for_current_user(db, session_id, current_user)
    return await get_chat_messages(db=db, session_id=session.id)


@router.post("/sessions/{session_id}/messages", response_model=ChatSendMessageResponse)
@limiter.limit("20/minute")
async def send_message(
    session_id: UUID,
    payload: ChatMessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_for_current_user(db, session_id, current_user)
    user_message, assistant_message = await send_chat_message(
        db=db,
        session_id=session.id,
        user_content=payload.content,
    )
    return {
        "user_message": user_message,
        "assistant_message": assistant_message,
    }


@router.post("/sessions/{session_id}/messages/stream")
@limiter.limit("20/minute")
async def send_message_stream(
    request: Request,
    session_id: UUID,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Streaming version — returns text token-by-token via Server-Sent Events.
    Reduces perceived latency from ~5s to instant-feeling response.
    """
    import logging

    logger = logging.getLogger("smartmeal.chatbot.stream")

    session = await _get_session_for_current_user(db, session_id, current_user)

    async def generate():
        try:
            # 1. Save user message to DB
            user_msg = await save_chat_message(
                db=db,
                session_id=session.id,
                role="user",
                content=payload.content,
            )
            await db.commit()

            # 2. Build context with user profile and conversation history
            context = await build_chatbot_context(
                db=db,
                user_id=current_user.id,
                session_id=session.id,
                user_question=payload.content,
            )

            user_prompt = build_chatbot_user_prompt(context)

            # 3. Stream from Groq (Groq has excellent streaming support)
            from groq import AsyncGroq

            client = AsyncGroq(api_key=settings.GROQ_API_KEY)

            full_response = ""
            try:
                async with asyncio.timeout(60):  # 60s max for streaming
                    stream = await client.chat.completions.create(
                        model=settings.GROQ_TEXT_MODEL,
                        messages=[
                            {"role": "system", "content": CHATBOT_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        stream=True,
                        max_tokens=1024,
                        temperature=0.4,
                    )

                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            full_response += delta
                            yield f"data: {json.dumps({'delta': delta})}\n\n"

            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'error': 'timeout', 'detail': 'AI stream timed out after 60s'})}\n\n"
                logger.error("Chatbot stream timeout for session %s", session.id)
                return

            # 4. Save full response to DB after stream completes
            await save_chat_message(
                db=db,
                session_id=session.id,
                role="assistant",
                content=full_response,
                metadata={"prompt_version": CHATBOT_PROMPT_VERSION},
            )
            await db.commit()

            yield f"data: {json.dumps({'done': True, 'message_id': str(user_msg.id)})}\n\n"

        except Exception as e:
            logger.error("Chatbot stream error: %s", e)
            yield f"data: {json.dumps({'error': 'stream_error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Prevent Nginx from buffering SSE
        },
    )


async def _get_session_for_current_user(
    db: AsyncSession,
    session_id: UUID,
    current_user: User,
) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.status != "deleted")
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    ensure_user_access(current_user, session.user_id)
    return session
