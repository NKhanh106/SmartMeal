import asyncio
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

import sqlalchemy as sa
from fastapi import BackgroundTasks, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.agents.base import AgentContext
from app.core.sanitize import sanitize_for_prompt
from app.agents.web_researcher_agent import (
    WebResearcherAgent,
    needs_low_confidence_research,
    should_trigger_web_research,
)
from app.chatbot.context_builder import build_chatbot_context
from app.chatbot.prompts import (
    CHATBOT_PROMPT_VERSION,
    CHATBOT_SYSTEM_PROMPT,
    build_chatbot_user_prompt,
)
from app.chatbot.utils import build_chat_title
from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession
from app.models.user_profile import UserProfile
from app.schemas.chat import StaleSessionWarning
from app.schemas.chat_card import ChatCard, ChatCardResponse
from app.services.ai_log_service import create_ai_log
from app.services.conversation_insights_service import (
    extract_insights_from_conversation,
    upsert_conversation_insights,
)

logger = logging.getLogger("smartmeal.chatbot")


async def create_chat_session(
    db: AsyncSession,
    user_id: UUID,
    title: str | None = None,
) -> ChatSession:
    now = datetime.now(timezone.utc)
    session = ChatSession(
        user_id=user_id,
        title=title or "Cuoc tro chuyen moi",
        status="active",
        last_activity_at=now,
    )
    db.add(session)
    await db.flush()
    return session


async def list_chat_sessions(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[ChatSession], bool, str | None]:
    """
    Return cursor-paginated chat sessions for a user.
    Returns (sessions, has_more, next_cursor).
    """
    query = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.status != "deleted")
        .order_by(ChatSession.last_message_at.desc().nullslast(), ChatSession.updated_at.desc())
    )

    if cursor:
        cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        query = query.where(
            sa.or_(
                ChatSession.last_message_at < cursor_dt,
                sa.and_(
                    ChatSession.last_message_at == cursor_dt,
                    ChatSession.updated_at < cursor_dt,
                ),
            )
        )

    query = query.limit(limit + 1)
    result = await db.execute(query)
    sessions = list(result.scalars().all())

    has_more = len(sessions) > limit
    if has_more:
        sessions = sessions[:limit]

    next_cursor = None
    if sessions and has_more:
        last = sessions[-1]
        next_cursor = (last.last_message_at or last.updated_at).isoformat()

    return sessions, has_more, next_cursor


async def get_latest_session(
    db: AsyncSession,
    user_id: UUID,
) -> ChatSession | None:
    """Get the most recent session for auto-resume on login."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id, ChatSession.status != "deleted")
        .order_by(ChatSession.last_message_at.desc().nullslast(), ChatSession.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_chat_messages(
    db: AsyncSession,
    session_id: UUID,
    limit: int = 30,
    before_id: UUID | None = None,
) -> tuple[list[ChatMessage], bool, str | None]:
    """
    Return paginated chat messages for a session (newest first for display).
    For infinite scroll upward, use before_id to get older messages.
    Returns (messages, has_more, next_cursor).
    """
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
    )

    if before_id:
        query = query.where(ChatMessage.id < before_id)

    query = query.limit(limit + 1)
    result = await db.execute(query)
    messages = list(result.scalars().all())

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    next_cursor = str(messages[-1].id) if messages else None
    return messages, has_more, next_cursor


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


async def update_session_title(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
    title: str,
) -> ChatSession:
    """Rename a chat session."""
    session = await get_chat_session_or_404(db, session_id)
    if session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this session")
    session.title = title
    await db.flush()
    return session


async def soft_delete_session(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> None:
    """Soft delete a chat session."""
    session = await get_chat_session_or_404(db, session_id)
    if session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this session")
    session.status = "deleted"
    await db.flush()


async def check_stale_session(
    db: AsyncSession,
    session_id: UUID,
    threshold_hours: int = 24,
) -> StaleSessionWarning:
    """Check if a session is stale (>threshold_hours since last activity)."""
    session = await get_chat_session_or_404(db, session_id)
    if not session.last_activity_at:
        return StaleSessionWarning(is_stale=False)

    now = datetime.now(timezone.utc)
    diff = now - session.last_activity_at
    hours_since = diff.total_seconds() / 3600

    if hours_since > threshold_hours:
        days = int(diff.total_seconds() / 86400)
        return StaleSessionWarning(
            is_stale=True,
            days_since_activity=days,
            last_activity_at=session.last_activity_at,
        )

    return StaleSessionWarning(is_stale=False)


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


async def save_card_message(
    db: AsyncSession,
    session_id: UUID,
    card: ChatCard,
    role: str = "assistant",
) -> ChatMessage:
    """Save a card as an assistant message with message_type='card'."""
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=card.title,  # use title as short preview
        message_type="card",
        card=card.model_dump(mode="json"),
    )
    db.add(msg)
    await db.flush()
    return msg


def _build_card_response_text(card: ChatCard, response: ChatCardResponse) -> str:
    """Convert a card response into a natural-language string for injection."""
    if response.selected_ids:
        labels = []
        for idx in response.selected_ids:
            opt = next((o for o in (card.options or []) if o.id == idx), None)
            labels.append(opt.label if opt else idx)
        if len(labels) == 1:
            return f"{card.title}: {labels[0]}"
        return f"{card.title}: {', '.join(labels)}"

    if response.ranked_ids:
        parts = []
        for i, rid in enumerate(response.ranked_ids):
            opt = next((o for o in (card.options or []) if o.id == rid), None)
            parts.append(f"{i + 1}. {opt.label if opt else rid}")
        return f"Thứ tự ưu tiên của tôi: {', '.join(parts)}"

    if response.number_value is not None:
        unit = f" {card.unit}" if card.unit else ""
        return f"{card.title}: {response.number_value}{unit}"

    if response.text_value:
        return f"{card.title}: {response.text_value}"

    if response.confirmed is not None:
        yes_no = "Có" if response.confirmed else "Không"
        ctx = card.subtitle or card.title
        return f"{yes_no}, {ctx}"

    return ""


async def _update_profile_from_card_response(
    db: AsyncSession,
    user_id: UUID,
    card: ChatCard,
    response: ChatCardResponse,
) -> None:
    """
    Update profile fields based on card response.
    CARD_TO_PROFILE_FIELD maps trigger_reason → (profile_field_name, value_extractor).
    """
    mapping: dict[str, tuple[str, str]] = {
        "missing_goal": ("usage_goal", _extract_single_id(response)),
        "missing_weight": ("current_weight_kg", _extract_number(response)),
    }

    trigger = card.trigger_reason
    if trigger not in mapping:
        return

    field_name, raw_value = mapping[trigger]
    if raw_value is None:
        return

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return

    if field_name == "usage_goal":
        setattr(profile, "usage_goal", raw_value)
    elif field_name == "current_weight_kg":
        setattr(profile, "current_weight_kg", float(raw_value))

    await db.flush()


def _extract_single_id(response: ChatCardResponse) -> str | None:
    if response.selected_ids:
        return response.selected_ids[0]
    return None


def _extract_number(response: ChatCardResponse) -> float | None:
    if response.number_value is not None:
        return response.number_value
    if response.selected_ids:
        try:
            return float(response.selected_ids[0])
        except (ValueError, TypeError):
            return None
    return None


async def send_chat_message(
    db: AsyncSession,
    session_id: UUID,
    user_content: str,
    background_tasks: BackgroundTasks | None = None,
):
    """
    Non-streaming chat message handler.

    Commits immediately after saving the user/assistant message pair.
    All heavy processing (passive meal extraction, insight extraction) is
    dispatched to FastAPI BackgroundTasks to keep response latency low.

    Background tasks receive primitive values (UUIDs, strings) so they can
    create their own DB sessions without risking "session is closed" errors.
    """
    session = await get_chat_session_or_404(db, session_id)
    user_id = session.user_id
    now = datetime.now(timezone.utc)

    user_message = await save_chat_message(
        db=db,
        session_id=session_id,
        role="user",
        content=user_content,
    )

    # Sanitize for AI prompts (prevents prompt injection) — raw value preserved in DB
    safe_content = sanitize_for_prompt(user_content)

    if session.title == "Cuoc tro chuyen moi":
        session.title = build_chat_title(safe_content)
    session.last_message_at = now
    session.last_activity_at = now

    context = await build_chatbot_context(
        db=db,
        user_id=user_id,
        session_id=session.id,
        user_question=safe_content,
    )

    user_prompt = build_chatbot_user_prompt(context)
    provider = get_ai_provider(settings.AI_CHAT_PROVIDER)
    start_time = time.perf_counter()
    model_name = (
        settings.GEMINI_MODEL
        if settings.AI_CHAT_PROVIDER == "gemini"
        else settings.GROQ_TEXT_MODEL
    )

    # Check for meal command BEFORE sending to AI
    from app.services.meal_extraction_service import detect_meal_command, process_meal_command

    is_meal_command, food_mention = detect_meal_command(user_content)
    meal_command_logged = False
    meal_command_response = None

    if is_meal_command and food_mention:
        # Process meal command immediately
        meal_log, response = await process_meal_command(db, user_id, food_mention)
        if meal_log:
            meal_command_response = response
            meal_command_logged = True
            logger.info(f"Meal command processed: {food_mention}")

    # ── Web research check ─────────────────────────────────────────────────
    # Run in parallel with AI response when triggered (non-blocking)
    web_research_triggered = (
        should_trigger_web_research(user_content)
        or needs_low_confidence_research(user_content)
    )

    async def run_web_research() -> str | None:
        """Execute web research in background and return findings text, or None."""
        if not web_research_triggered:
            return None
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.user import User

            async with AsyncSessionLocal() as research_db:
                # Fetch the User object for the agent context
                user_result = await research_db.execute(
                    select(User).where(User.id == user_id)
                )
                researcher_user = user_result.scalar_one_or_none()
                if not researcher_user:
                    return None

                research_context = AgentContext(
                    user=researcher_user,
                    session_id=str(session_id),
                    current_message=user_content,
                )

                researcher = WebResearcherAgent()
                result = await asyncio.wait_for(
                    researcher.run(research_context, research_db),
                    timeout=8.0,
                )
                if result.success and result.text_for_orchestrator:
                    return result.text_for_orchestrator
                return None
        except asyncio.TimeoutError:
            logger.warning("Web research timed out (>8s) for session %s", session_id)
            return None
        except Exception as exc:
            logger.error("Web research failed for session %s: %s", session_id, exc)
            return None

    try:
        # Fire-and-forget: web research runs in background
        # Results are saved to agent_insights and available on next message turn
        asyncio.create_task(run_web_research())

        answer = await run_in_threadpool(
            provider.generate_text,
            system_prompt=CHATBOT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.4,
        )

        # Prepend meal command confirmation if applicable
        if meal_command_response:
            answer = f"{meal_command_response}\n\n{answer}"

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

        metadata = {
            "ai_log_id": str(ai_log.id),
            "provider": settings.AI_CHAT_PROVIDER,
            "prompt_version": CHATBOT_PROMPT_VERSION,
        }

        # Add meal extraction metadata if applicable
        if meal_command_logged:
            metadata["meal_command"] = True

        assistant_message = await save_chat_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=answer,
            metadata=metadata,
            ai_analysis_log_id=ai_log.id,
        )
        session.last_activity_at = datetime.now(timezone.utc)

        # Dispatch background tasks before commit — they receive primitive values, not db session
        if background_tasks is not None:
            # Passive meal extraction (only when no explicit meal command was used)
            if not meal_command_logged:
                background_tasks.add_task(
                    _bg_passive_meal_extraction,
                    user_id=user_id,
                    user_message=user_content,
                    ai_response=answer,
                )
            # Insight extraction — builds its own DB session
            recent_for_insight = [
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": answer},
            ]
            more_msgs_result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(4)
            )
            more_msgs = list(reversed(more_msgs_result.scalars().all()))
            for msg in more_msgs:
                recent_for_insight.insert(0, {"role": msg.role, "content": msg.content})
            background_tasks.add_task(
                _bg_extract_insights,
                user_id=user_id,
                session_id=session_id,
                recent_messages=recent_for_insight,
            )
            # ExtractorAgent: runs after EVERY message to extract structured facts → UserMemory
            background_tasks.add_task(
                _bg_extractor_agent,
                user_id=user_id,
                session_id=session_id,
                user_message=user_content,
                ai_response=answer,
            )

        # Commit session update and user/assistant messages first
        await db.commit()
        await db.refresh(user_message)
        await db.refresh(assistant_message)

        # Return immediately — background tasks handle passive extraction and insight
        return user_message, assistant_message

    except (ValueError, asyncio.TimeoutError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tro ly AI hien khong phan hoi. Vui long thu lai sau.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("[send_chat_message] Unexpected error for user %s session %s: %s", user_id, session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Da xay ra loi khi xu ly tin nhan.",
        ) from exc


# ── Background task handlers (create own DB sessions) ─────────────────────────

async def _bg_passive_meal_extraction(
    user_id: UUID,
    user_message: str,
    ai_response: str,
) -> None:
    """
    Background task: run passive meal extraction with its own DB session.
    FastAPI BackgroundTasks guarantees task completion even if the client disconnects.
    """
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            from app.services.meal_extraction_service import extract_meals_from_message

            await extract_meals_from_message(
                db=db,
                user_id=user_id,
                user_message=user_message,
                ai_response=ai_response,
            )
            await db.commit()
            logger.info(f"[BG] Passive meal extraction done for user {user_id}")
    except Exception as e:
        logger.error(f"[BG] Passive meal extraction failed for user {user_id}: {e}")


async def _bg_extract_insights(
    user_id: UUID,
    session_id: UUID,
    recent_messages: list[dict],
) -> None:
    """
    Background task: extract and upsert conversation insights with its own DB session.
    FastAPI BackgroundTasks guarantees task completion even if the client disconnects.
    """
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            from app.services.conversation_insights_service import (
                extract_insights_from_conversation,
                upsert_conversation_insights,
            )

            insights_result = await extract_insights_from_conversation(
                db=db,
                user_id=user_id,
                session_id=session_id,
                recent_messages=recent_messages,
            )
            if insights_result.insights:
                await upsert_conversation_insights(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    insights=insights_result.insights,
                )
            await db.commit()
            logger.info(f"[BG] Insight extraction done for user {user_id} session {session_id}")
    except Exception as e:
        logger.error(f"[BG] Insight extraction failed for user {user_id} session {session_id}: {e}")


async def _bg_extractor_agent(
    user_id: UUID,
    session_id: UUID,
    user_message: str,
    ai_response: str,
) -> None:
    """
    Background task: run ExtractorAgent after EVERY message to extract structured facts → UserMemory.
    FastAPI BackgroundTasks guarantees task completion even if the client disconnects.
    """
    from app.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            from app.agents.extractor_agent import ExtractorAgent
            from app.agents.memory_service import get_or_create_memory
            from app.models.user import User
            from sqlalchemy import select

            # Load user and session for agent context
            user_result = await db.execute(select(User).where(User.id == user_id))
            researcher_user = user_result.scalar_one_or_none()
            if not researcher_user:
                return

            memory = await get_or_create_memory(user_id, db)

            # Build conversation history context (last 4 messages)
            history_result = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(6)
            )
            msgs = list(reversed(history_result.scalars().all()))
            conversation_history = [
                {"role": m.role, "content": m.content}
                for m in msgs
            ]

            from app.agents.base import AgentContext

            context = AgentContext(
                user=researcher_user,
                session_id=str(session_id),
                current_message=safe_content,
                conversation_history=conversation_history,
                memory=memory,
            )

            extractor = ExtractorAgent()
            result = await extractor.run(context, db)

            await db.commit()
            logger.info(
                f"[BG] ExtractorAgent done for user {user_id} session {session_id} "
                f"— success={result.success} confidence={result.confidence}"
            )
    except Exception as e:
        logger.error(f"[BG] ExtractorAgent failed for user {user_id} session {session_id}: {e}", exc_info=True)


# ─── Card streaming functions ────────────────────────────────────────────────────

# Tool definition the AI can call to emit a card
ASK_USER_TOOL = {
    "name": "ask_user",
    "description": (
        "Use this tool when you need specific information from the user to give "
        "accurate advice. Do NOT use for general conversation. Use when: "
        "(1) you need a number (weight, age, portion size), "
        "(2) you need to choose between clearly distinct options, "
        "(3) you need to confirm before taking an action like logging a meal. "
        "Do NOT use more than once per response."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "card_type": {
                "type": "string",
                "enum": ["single_select", "multi_select", "rank", "number_input", "confirm"],
                "description": "Type of input to collect",
            },
            "title": {
                "type": "string",
                "description": "The question to ask the user. Max 60 characters. Vietnamese.",
            },
            "subtitle": {
                "type": "string",
                "description": "Optional hint or context. Max 100 characters.",
            },
            "options": {
                "type": "array",
                "description": "Required for single_select, multi_select, rank",
                "items": {
                    "type": "object",
                    "properties": {
                        "id":    {"type": "string"},
                        "label": {"type": "string"},
                        "icon":  {"type": "string", "description": "Single emoji"},
                    },
                    "required": ["id", "label"],
                },
            },
            "unit":        {"type": "string", "description": "For number_input only"},
            "min_value":   {"type": "number", "description": "For number_input only"},
            "max_value":   {"type": "number", "description": "For number_input only"},
            "placeholder": {"type": "string", "description": "For number_input only"},
            "min_selections": {"type": "integer", "description": "For multi_select"},
            "max_selections": {"type": "integer", "description": "For multi_select"},
        },
        "required": ["card_type", "title"],
    },
}


def _build_card_from_tool_input(tool_input: dict) -> ChatCard:
    """Convert AI tool call input into a ChatCard."""
    import uuid

    options = None
    if tool_input.get("options"):
        options = [
            {"id": o["id"], "label": o["label"], "icon": o.get("icon")}
            for o in tool_input["options"]
        ]

    return ChatCard(
        card_id=str(uuid.uuid4()),
        card_type=tool_input["card_type"],
        title=tool_input["title"],
        subtitle=tool_input.get("subtitle"),
        options=options,
        min_value=tool_input.get("min_value"),
        max_value=tool_input.get("max_value"),
        unit=tool_input.get("unit"),
        placeholder=tool_input.get("placeholder"),
        min_selections=tool_input.get("min_selections"),
        max_selections=tool_input.get("max_selections"),
        trigger_reason="ai_request",
        skippable=True,
    )


async def process_streaming_message(
    db: AsyncSession,
    session: ChatSession,
    user_content: str,
    user_id: UUID,
) -> AsyncGenerator[str, None]:
    """
    Main entry point for streaming a chat message.
    Handles: hard-rule cards, normal AI streaming, AI-driven tool calls.
    Yields SSE strings.
    """
    import asyncio
    import json

    from groq import AsyncGroq

    logger_stream = logging.getLogger("smartmeal.chatbot.stream")

    # 1. Save user message
    user_msg = await save_chat_message(
        db=db,
        session_id=session.id,
        role="user",
        content=user_content,
    )
    await db.commit()

    # 2. Sanitize for AI prompts (prevents prompt injection)
    safe_content = sanitize_for_prompt(user_content)

    # 3. Update session title on first real message
    if session.title == "Cuoc tro chuyen moi":
        session.title = build_chat_title(safe_content)
    session.last_message_at = datetime.now(timezone.utc)
    session.last_activity_at = datetime.now(timezone.utc)

    # 4. Build context
    context = await build_chatbot_context(
        db=db,
        user_id=user_id,
        session_id=session.id,
        user_question=safe_content,
    )
    user_prompt = build_chatbot_user_prompt(context)

    # 5. Check hard-rule triggers (profile already loaded in context)
    from app.chatbot.card_triggers import check_hard_rule_triggers

    fired_triggers: dict[str, bool] = dict(session.fired_triggers or {})
    hard_card, trigger_reason = check_hard_rule_triggers(
        user_message=safe_content,
        profile=context.get("_profile_object"),
        fired_triggers=fired_triggers,
    )

    if hard_card:
        # Mark trigger as fired in session
        fired_triggers[trigger_reason] = True
        session.fired_triggers = fired_triggers
        await db.flush()

        # Save card message to DB
        await save_card_message(db=db, session_id=session.id, card=hard_card)
        await db.commit()

        # Yield card as SSE event
        yield f"event: card\ndata: {hard_card.model_dump_json()}\n\n"
        return  # Do NOT call AI — wait for card response

    # 5. Call AI with Groq streaming
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    full_response = ""

    try:
        async with asyncio.timeout(60):
            # Build messages for Groq with system prompt + user prompt
            # We also include the card tool definition
            messages = [
                {"role": "system", "content": CHATBOT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            stream = await client.chat.completions.create(
                model=settings.GROQ_TEXT_MODEL,
                messages=messages,
                tools=[ASK_USER_TOOL],
                stream=True,
                max_tokens=1024,
                temperature=0.4,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta
                # Check for tool call
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.function.name == "ask_user":
                            try:
                                tool_input = json.loads(tc.function.arguments)
                                card = _build_card_from_tool_input(tool_input)

                                # Save card message
                                await save_card_message(db=db, session_id=session.id, card=card)
                                await db.commit()

                                # Yield card SSE event
                                yield f"event: card\ndata: {card.model_dump_json()}\n\n"
                                return  # Pause — wait for card response
                            except (json.JSONDecodeError, KeyError):
                                logger_stream.warning("Failed to parse ask_user tool call: %s", tc.function.arguments)
                                continue

                # Text delta
                content_delta = delta.content or ""
                if content_delta:
                    full_response += content_delta
                    yield f"data: {json.dumps({'delta': content_delta})}\n\n"

    except asyncio.TimeoutError:
        yield f"data: {json.dumps({'error': 'timeout', 'detail': 'AI stream timed out after 60s'})}\n\n"
        logger_stream.error("Chatbot stream timeout for session %s", session.id)
        return

    # 6. Save assistant response to DB
    await save_chat_message(
        db=db,
        session_id=session.id,
        role="assistant",
        content=full_response,
        metadata={"prompt_version": CHATBOT_PROMPT_VERSION},
    )
    await db.commit()

    yield f"data: {json.dumps({'done': True, 'message_id': str(user_msg.id)})}\n\n"


async def process_card_response_and_stream(
    db: AsyncSession,
    session: ChatSession,
    card_response: ChatCardResponse,
    user_id: UUID,
) -> AsyncGenerator[str, None]:
    """
    Handle a card response:
    1. Find and update the matching card message
    2. Update profile if applicable
    3. Inject natural-language summary as a user message
    4. Resume AI streaming
    """
    import asyncio
    import json

    from groq import AsyncGroq

    logger_stream = logging.getLogger("smartmeal.chatbot.stream")

    # 1. Find the matching card message (most recent card message in this session)
    result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session.id,
            ChatMessage.role == "assistant",
            ChatMessage.message_type == "card",
            ChatMessage.card_response == None,  # not yet answered
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    card_msg = result.scalar_one_or_none()

    if not card_msg:
        logger_stream.warning("No matching card message found for card_response in session %s", session.id)
        yield f"data: {json.dumps({'error': 'card_not_found', 'detail': 'Card message not found'})}\n\n"
        return

    # Reconstruct the ChatCard from stored data
    card_data = card_msg.card or {}
    try:
        original_card = ChatCard.model_validate(card_data)
    except Exception:
        logger_stream.warning("Failed to deserialize card data for message %s", card_msg.id)
        original_card = None

    # 2. Save card_response to the card message
    card_msg.card_response = card_response.model_dump(mode="json")
    await db.flush()

    # 3. Update profile if applicable
    if original_card:
        await _update_profile_from_card_response(db, user_id, original_card, card_response)
        await db.commit()

    # 4. Build injected text and save as user message
    if original_card:
        injected_text = _build_card_response_text(original_card, card_response)
    else:
        injected_text = f"Card response: {card_response.model_dump_json()}"

    await save_chat_message(
        db=db,
        session_id=session.id,
        role="user",
        content=injected_text,
        metadata={"card_id": card_response.card_id, "message_type": "card_response"},
    )

    # Also save as a card_response message type
    cr_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=injected_text,
        message_type="card_response",
        card_response=card_response.model_dump(mode="json"),
    )
    db.add(cr_msg)
    await db.flush()

    session.last_message_at = datetime.now(timezone.utc)
    session.last_activity_at = datetime.now(timezone.utc)
    await db.commit()

    # 5. Resume AI with updated context
    context = await build_chatbot_context(
        db=db,
        user_id=user_id,
        session_id=session.id,
        user_question=injected_text,
    )
    user_prompt = build_chatbot_user_prompt(context)

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    full_response = ""

    try:
        async with asyncio.timeout(60):
            messages = [
                {"role": "system", "content": CHATBOT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            stream = await client.chat.completions.create(
                model=settings.GROQ_TEXT_MODEL,
                messages=messages,
                tools=[ASK_USER_TOOL],
                stream=True,
                max_tokens=1024,
                temperature=0.4,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta

                # Handle tool call
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.function.name == "ask_user":
                            try:
                                tool_input = json.loads(tc.function.arguments)
                                new_card = _build_card_from_tool_input(tool_input)
                                await save_card_message(db=db, session_id=session.id, card=new_card)
                                await db.commit()
                                yield f"event: card\ndata: {new_card.model_dump_json()}\n\n"
                                return
                            except (json.JSONDecodeError, KeyError):
                                continue

                content_delta = delta.content or ""
                if content_delta:
                    full_response += content_delta
                    yield f"data: {json.dumps({'delta': content_delta})}\n\n"

    except asyncio.TimeoutError:
        yield f"data: {json.dumps({'error': 'timeout', 'detail': 'AI stream timed out after 60s'})}\n\n"
        logger_stream.error("Card response stream timeout for session %s", session.id)
        return

    # 6. Save final AI response
    await save_chat_message(
        db=db,
        session_id=session.id,
        role="assistant",
        content=full_response,
        metadata={"prompt_version": CHATBOT_PROMPT_VERSION, "resumed_from_card": True},
    )
    await db.commit()

    yield f"data: {json.dumps({'done': True, 'resumed_from_card': True})}\n\n"
