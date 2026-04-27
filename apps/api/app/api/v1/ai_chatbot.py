from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_user_access, get_current_user
from app.chatbot.service import (
    create_chat_session,
    get_chat_messages,
    list_chat_sessions,
    send_chat_message,
)
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
async def send_message(
    session_id: UUID,
    payload: ChatMessageCreate,
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
