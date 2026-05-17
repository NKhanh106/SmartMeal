from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.multi_agent_orchestrator import MultiAgentOrchestrator
from app.api.deps import ensure_user_access, get_current_user
from app.core.rate_limiter import limiter
from app.chatbot.service import (
    check_stale_session,
    create_chat_session,
    get_chat_messages,
    get_latest_session,
    list_chat_sessions,
    process_card_response_and_stream,
    save_card_message,
    save_chat_message,
    send_chat_message,
    soft_delete_session,
    update_session_title,
)
from app.db.session import get_db
from app.models.chat import ChatSession
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatMessagesPaginatedResponse,
    ChatSendMessageResponse,
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSessionUpdate,
    StaleSessionWarning,
)
from app.schemas.chat_card import ChatCardResponse

router = APIRouter(prefix="/ai/chat", tags=["AI Chatbot"])


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat session (only when user explicitly clicks New Chat)."""
    session = await create_chat_session(
        db=db,
        user_id=current_user.id,
        title=payload.title,
    )
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=ChatSessionListResponse)
async def get_my_chat_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
):
    """List all chat sessions for current user with cursor-based pagination."""
    sessions, has_more, next_cursor = await list_chat_sessions(
        db=db,
        user_id=current_user.id,
        limit=limit,
        cursor=cursor,
    )
    return ChatSessionListResponse(
        total=len(sessions),
        items=[ChatSessionResponse.model_validate(s) for s in sessions],
    )


@router.get("/sessions/latest", response_model=ChatSessionResponse | None)
async def get_latest_chat_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the most recent session for auto-resume on login."""
    session = await get_latest_session(db=db, user_id=current_user.id)
    if session:
        return ChatSessionResponse.model_validate(session)
    return None


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_for_current_user(db, session_id, current_user)
    return ChatSessionResponse.model_validate(session)


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def rename_session(
    session_id: UUID,
    payload: ChatSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename a chat session."""
    session = await update_session_title(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        title=payload.title,
    )
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft delete a chat session."""
    await soft_delete_session(db=db, session_id=session_id, user_id=current_user.id)
    await db.commit()


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagesPaginatedResponse)
async def get_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
    before_id: str | None = Query(default=None, description="Cursor for pagination (message ID)"),
):
    """Get paginated messages for a session. Loads newest first, use before_id for infinite scroll."""
    await _get_session_for_current_user(db, session_id, current_user)

    before_uuid = None
    if before_id:
        try:
            before_uuid = UUID(before_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid before_id format")

    messages, has_more, next_cursor = await get_chat_messages(
        db=db,
        session_id=session_id,
        limit=limit,
        before_id=before_uuid,
    )

    return ChatMessagesPaginatedResponse(
        items=[ChatMessageResponse.from_orm_with_safe_metadata(msg) for msg in messages],
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.get("/sessions/{session_id}/stale", response_model=StaleSessionWarning)
async def check_session_stale(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a session is stale (>24h since last activity)."""
    await _get_session_for_current_user(db, session_id, current_user)
    return await check_stale_session(db=db, session_id=session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatSendMessageResponse)
async def send_message(
    request: Request,
    session_id: UUID,
    payload: ChatMessageCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await _get_session_for_current_user(db, session_id, current_user)
    user_message, assistant_message = await send_chat_message(
        db=db,
        session_id=session.id,
        user_content=payload.content,
        background_tasks=background_tasks,
    )
    return {
        "user_message": ChatMessageResponse.from_orm_with_safe_metadata(user_message),
        "assistant_message": ChatMessageResponse.from_orm_with_safe_metadata(assistant_message),
    }


@router.post("/sessions/{session_id}/messages/stream")
@limiter.limit("30/minute")
async def send_message_stream(
    request: Request,
    session_id: UUID,
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Multi-Agent streaming endpoint — routes through the orchestrator
    which runs specialist agents in parallel and synthesizes a response.
    """
    session = await _get_session_for_current_user(db, session_id, current_user)

    # Save user message first
    await save_chat_message(
        db=db,
        session_id=session.id,
        role="user",
        content=payload.content,
    )
    await db.commit()

    orchestrator = MultiAgentOrchestrator()
    return StreamingResponse(
        orchestrator.process(
            user_message=payload.content,
            session_id=session_id,
            user=current_user,
            db=db
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/sessions/{session_id}/card-response")
@limiter.limit("20/minute")
async def submit_card_response(
    request: Request,
    session_id: UUID,
    response_payload: ChatCardResponse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Receives the user's answer to an interactive card.
    1. Save card_response to the matching card message
    2. Map card response → profile update (goal, weight)
    3. Inject natural-language summary as a user message
    4. Resume AI processing and stream the response
    """
    session = await _get_session_for_current_user(db, session_id, current_user)

    async def generate():
        async for event in process_card_response_and_stream(
            db=db,
            session=session,
            card_response=response_payload,
            user_id=current_user.id,
        ):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
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
