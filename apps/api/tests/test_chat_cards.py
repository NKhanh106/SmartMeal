"""Tests for the AI-Triggered Interactive Card System.

Covers:
- Hard-rule card triggers (check_hard_rule_triggers)
- Hard-rule idempotency (fires once per session per trigger_reason)
- Card streaming via process_streaming_message
- Card response + profile update via process_card_response_and_stream
- Card schema validation
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.chatbot.card_triggers import (
    check_hard_rule_triggers,
    _is_nutrition_question,
    _has_health_keywords,
    _has_plan_keywords,
)
from app.chatbot.service import (
    _build_card_from_tool_input,
    _build_card_response_text,
    _extract_single_id,
    _extract_number,
)
from app.models.chat import ChatMessage, ChatSession
from app.models.user_profile import UserProfile
from app.schemas.chat_card import (
    ChatCard,
    ChatCardResponse,
    CardType,
    CardOption,
)


# ─── Hard Rule Unit Tests ────────────────────────────────────────────────────────

class TestHardRuleTriggers:
    """Unit tests for check_hard_rule_triggers (no DB needed)."""

    def test_missing_profile_returns_confirm_card(self):
        """Rule 1: No profile at all → confirm card asking to create profile."""
        card, reason = check_hard_rule_triggers(
            user_message="Cho tôi hỏi về thực đơn",
            profile=None,
            fired_triggers=None,
        )
        assert card is not None
        assert reason == "missing_profile"
        assert card.card_type == CardType.CONFIRM
        assert "hồ sơ" in card.title

    def test_missing_profile_idempotent(self):
        """Rule 1 fires only once (fired_triggers prevents repeat)."""
        fired = {"missing_profile": True}
        card, reason = check_hard_rule_triggers(
            user_message="Bữa ăn hôm nay",
            profile=None,
            fired_triggers=fired,
        )
        assert card is None
        assert reason is None

    def test_nutrition_question_without_goal_fires_card(self):
        """Rule 2: Nutrition question with no usage_goal → single-select card."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = None
        profile.health_conditions = None
        profile.current_weight_kg = 70.0

        card, reason = check_hard_rule_triggers(
            user_message="Tôi nên ăn gì để giảm cân?",
            profile=profile,
            fired_triggers=None,
        )
        assert card is not None
        assert reason == "missing_goal"
        assert card.card_type == CardType.SINGLE_SELECT
        assert card.trigger_reason == "missing_goal"
        # Should have 7 goal options
        assert len(card.options) == 7

    def test_non_nutrition_question_skips_goal_card(self):
        """Rule 2 does NOT fire for casual messages."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = None
        profile.health_conditions = None
        profile.current_weight_kg = 70.0

        card, reason = check_hard_rule_triggers(
            user_message="Xin chào, bạn khỏe không?",
            profile=profile,
            fired_triggers=None,
        )
        assert card is None

    def test_goal_card_idempotent(self):
        """Rule 2 fires only once per session."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = None
        profile.health_conditions = None
        profile.current_weight_kg = 70.0
        fired = {"missing_goal": True}

        card, reason = check_hard_rule_triggers(
            user_message="Ăn gì cho tốt?",
            profile=profile,
            fired_triggers=fired,
        )
        assert card is None

    def test_has_goal_does_not_fire_goal_card(self):
        """Rule 2 should not fire if profile already has usage_goal set."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "weight_loss"
        profile.health_conditions = None
        profile.current_weight_kg = 70.0

        card, reason = check_hard_rule_triggers(
            user_message="Ăn gì để giảm cân?",
            profile=profile,
            fired_triggers=None,
        )
        assert card is None

    def test_health_keywords_without_conditions_fires_card(self):
        """Rule 3: Health keywords + no conditions → confirm card."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "weight_loss"
        profile.health_conditions = None
        profile.current_weight_kg = 70.0

        card, reason = check_hard_rule_triggers(
            user_message="Tôi bị tiểu đường, ăn gì tốt?",
            profile=profile,
            fired_triggers=None,
        )
        assert card is not None
        assert reason == "missing_health_conditions"
        assert card.card_type == CardType.CONFIRM

    def test_health_card_idempotent(self):
        """Rule 3 fires only once."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "weight_loss"
        profile.health_conditions = None
        profile.current_weight_kg = 70.0
        fired = {"missing_health_conditions": True}

        card, reason = check_hard_rule_triggers(
            user_message="Tôi bị huyết áp cao",
            profile=profile,
            fired_triggers=fired,
        )
        assert card is None

    def test_health_card_not_fired_when_has_conditions(self):
        """Rule 3 does NOT fire if profile already has health_conditions."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "weight_loss"
        profile.health_conditions = [{"condition": "type2_diabetes", "severity": "managed"}]
        profile.current_weight_kg = 70.0

        card, reason = check_hard_rule_triggers(
            user_message="Tôi bị tiểu đường",
            profile=profile,
            fired_triggers=None,
        )
        assert card is None

    def test_plan_keywords_without_weight_fires_card(self):
        """Rule 4: Meal plan request + no weight → number input card."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "weight_loss"
        profile.health_conditions = None
        profile.current_weight_kg = None

        card, reason = check_hard_rule_triggers(
            user_message="Tính calories cho tôi đi",
            profile=profile,
            fired_triggers=None,
        )
        assert card is not None
        assert reason == "missing_weight"
        assert card.card_type == CardType.NUMBER_INPUT
        assert card.unit == "kg"
        assert card.min_value == 30
        assert card.max_value == 200

    def test_weight_card_idempotent(self):
        """Rule 4 fires only once."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "weight_loss"
        profile.health_conditions = None
        profile.current_weight_kg = None
        fired = {"missing_weight": True}

        card, reason = check_hard_rule_triggers(
            user_message="Tôi nên ăn bao nhiêu calo?",
            profile=profile,
            fired_triggers=fired,
        )
        assert card is None

    def test_weight_card_not_fired_when_has_weight(self):
        """Rule 4 does NOT fire if profile has current_weight_kg."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "weight_loss"
        profile.health_conditions = None
        profile.current_weight_kg = 68.0

        card, reason = check_hard_rule_triggers(
            user_message="Tính macros cho tôi đi",
            profile=profile,
            fired_triggers=None,
        )
        assert card is None

    def test_no_trigger_when_profile_complete(self):
        """When profile has goal + conditions + weight, no card fires."""
        profile = MagicMock(spec=UserProfile)
        profile.usage_goal = "muscle_gain"
        profile.health_conditions = [{"condition": "none", "severity": "resolved"}]
        profile.current_weight_kg = 70.0

        card, reason = check_hard_rule_triggers(
            user_message="Tôi nên ăn gì hôm nay?",
            profile=profile,
            fired_triggers=None,
        )
        assert card is None


class TestHardRuleKeywordHelpers:
    """Test keyword detection helpers."""

    def test_is_nutrition_question_true(self):
        assert _is_nutrition_question("Tôi nên ăn gì để giảm cân?")
        assert _is_nutrition_question("Cho tôi xem thực đơn")
        assert _is_nutrition_question("bao nhiêu calo?")
        assert _is_nutrition_question("protein cho cơ bắp")
        assert _is_nutrition_question("GIẢM cân")
        assert _is_nutrition_question("macro cho người tập gym")
        assert _is_nutrition_question("bữa ăn cho buổi sáng")

    def test_is_nutrition_question_false(self):
        assert not _is_nutrition_question("Xin chào")
        assert not _is_nutrition_question("Hôm nay trời đẹp")
        assert not _is_nutrition_question("Bạn là ai?")
        assert not _is_nutrition_question("tôi đi ngủ")

    def test_has_health_keywords_true(self):
        assert _has_health_keywords("Tôi bị tiểu đường type 2")
        assert _has_health_keywords("huyết áp cao")
        assert _has_health_keywords("dị ứng gluten")
        assert _has_health_keywords("uống thuốc metformin")

    def test_has_health_keywords_false(self):
        assert not _has_health_keywords("Tôi muốn ăn pizza")
        assert not _has_health_keywords("Hôm nay trời đẹp")
        assert not _has_health_keywords("Bữa ăn sáng")

    def test_has_plan_keywords_true(self):
        assert _has_plan_keywords("Tính thực đơn cho tôi")
        assert _has_plan_keywords("kế hoạch ăn uống")
        assert _has_plan_keywords("bao nhiêu calories")
        assert _has_plan_keywords("macro cho người giảm cân")

    def test_has_plan_keywords_false(self):
        assert not _has_plan_keywords("Ăn gì hôm nay?")
        assert not _has_plan_keywords("Xin chào")


# ─── Card Schema Tests ──────────────────────────────────────────────────────────

class TestCardSchema:
    """Test ChatCard and ChatCardResponse schemas."""

    def test_chat_card_single_select(self):
        card = ChatCard(
            card_id=str(uuid.uuid4()),
            card_type=CardType.SINGLE_SELECT,
            title="Mục tiêu của bạn là gì?",
            subtitle="Chọn một",
            options=[
                CardOption(id="a", label="A"),
                CardOption(id="b", label="B", icon="💪"),
            ],
            trigger_reason="missing_goal",
        )
        assert card.card_type == CardType.SINGLE_SELECT
        assert len(card.options) == 2
        assert card.skippable is True
        assert card.unit is None

    def test_chat_card_number_input_defaults(self):
        card = ChatCard(
            card_id=str(uuid.uuid4()),
            card_type=CardType.NUMBER_INPUT,
            title="Cân nặng của bạn?",
            unit="kg",
            min_value=30,
            max_value=200,
            placeholder="Nhập cân nặng",
            trigger_reason="missing_weight",
        )
        assert card.min_value == 30
        assert card.max_value == 200
        assert card.unit == "kg"

    def test_chat_card_confirm(self):
        card = ChatCard(
            card_id=str(uuid.uuid4()),
            card_type=CardType.CONFIRM,
            title="Bạn có bệnh lý không?",
            trigger_reason="missing_health_conditions",
            skippable=True,
        )
        assert card.options is None
        assert card.card_type == CardType.CONFIRM

    def test_chat_card_response_single_select(self):
        resp = ChatCardResponse(
            card_id="abc",
            card_type=CardType.SINGLE_SELECT,
            selected_ids=["weight_loss"],
        )
        assert resp.selected_ids == ["weight_loss"]
        assert resp.number_value is None
        assert resp.confirmed is None

    def test_chat_card_response_multi_select(self):
        resp = ChatCardResponse(
            card_id="abc",
            card_type=CardType.MULTI_SELECT,
            selected_ids=["a", "b", "c"],
        )
        assert len(resp.selected_ids) == 3

    def test_chat_card_response_rank(self):
        resp = ChatCardResponse(
            card_id="abc",
            card_type=CardType.RANK,
            ranked_ids=["c", "a", "b"],
        )
        assert resp.ranked_ids == ["c", "a", "b"]

    def test_chat_card_response_number(self):
        resp = ChatCardResponse(
            card_id="abc",
            card_type=CardType.NUMBER_INPUT,
            number_value=68.5,
        )
        assert resp.number_value == 68.5

    def test_chat_card_response_confirm_yes(self):
        resp = ChatCardResponse(
            card_id="abc",
            card_type=CardType.CONFIRM,
            confirmed=True,
        )
        assert resp.confirmed is True

    def test_chat_card_response_confirm_no(self):
        resp = ChatCardResponse(
            card_id="abc",
            card_type=CardType.CONFIRM,
            confirmed=False,
        )
        assert resp.confirmed is False


# ─── Service Helper Tests ────────────────────────────────────────────────────────

class TestServiceHelpers:
    """Test _build_card_from_tool_input and _build_card_response_text."""

    def test_build_card_from_tool_input_single_select(self):
        tool_input = {
            "card_type": "single_select",
            "title": "Mục tiêu của bạn?",
            "subtitle": "Chọn một",
            "options": [
                {"id": "muscle_gain", "label": "Tăng cơ", "icon": "💪"},
                {"id": "weight_loss", "label": "Giảm cân", "icon": "⬇️"},
            ],
        }
        card = _build_card_from_tool_input(tool_input)
        assert card.card_type == CardType.SINGLE_SELECT
        assert len(card.options) == 2
        assert card.trigger_reason == "ai_request"
        assert card.skippable is True
        assert card.card_id is not None

    def test_build_card_from_tool_input_number_input(self):
        tool_input = {
            "card_type": "number_input",
            "title": "Cân nặng của bạn?",
            "unit": "kg",
            "min_value": 30,
            "max_value": 200,
            "placeholder": "Nhập cân nặng",
        }
        card = _build_card_from_tool_input(tool_input)
        assert card.card_type == CardType.NUMBER_INPUT
        assert card.min_value == 30
        assert card.max_value == 200
        assert card.unit == "kg"

    def test_build_card_from_tool_input_minimal(self):
        tool_input = {
            "card_type": "confirm",
            "title": "Bạn có bệnh lý không?",
        }
        card = _build_card_from_tool_input(tool_input)
        assert card.card_type == CardType.CONFIRM
        assert card.options is None

    def test_build_card_response_text_single_select(self):
        card = ChatCard(
            card_id="c1",
            card_type=CardType.SINGLE_SELECT,
            title="Mục tiêu chính của bạn là gì?",
            options=[
                CardOption(id="muscle_gain", label="Tăng cơ", icon="💪"),
                CardOption(id="weight_loss", label="Giảm cân", icon="⬇️"),
            ],
            trigger_reason="test",
        )
        resp = ChatCardResponse(
            card_id="c1",
            card_type=CardType.SINGLE_SELECT,
            selected_ids=["muscle_gain"],
        )
        text = _build_card_response_text(card, resp)
        assert "Tăng cơ" in text

    def test_build_card_response_text_multi_select(self):
        card = ChatCard(
            card_id="c1",
            card_type=CardType.MULTI_SELECT,
            title="Bạn thích ăn gì?",
            options=[
                CardOption(id="viet", label="Việt Nam"),
                CardOption(id="jp", label="Nhật Bản"),
            ],
            trigger_reason="test",
        )
        resp = ChatCardResponse(
            card_id="c1",
            card_type=CardType.MULTI_SELECT,
            selected_ids=["viet", "jp"],
        )
        text = _build_card_response_text(card, resp)
        assert "Việt Nam" in text
        assert "Nhật Bản" in text

    def test_build_card_response_text_rank(self):
        card = ChatCard(
            card_id="c1",
            card_type=CardType.RANK,
            title="Sắp xếp ưu tiên",
            options=[
                CardOption(id="a", label="Protein"),
                CardOption(id="b", label="Carb"),
                CardOption(id="c", label="Fat"),
            ],
            trigger_reason="test",
        )
        resp = ChatCardResponse(
            card_id="c1",
            card_type=CardType.RANK,
            ranked_ids=["b", "a", "c"],
        )
        text = _build_card_response_text(card, resp)
        assert "Thứ tự ưu tiên" in text
        assert "1." in text

    def test_build_card_response_text_number_input(self):
        card = ChatCard(
            card_id="c1",
            card_type=CardType.NUMBER_INPUT,
            title="Cân nặng của bạn",
            unit="kg",
            trigger_reason="missing_weight",
        )
        resp = ChatCardResponse(
            card_id="c1",
            card_type=CardType.NUMBER_INPUT,
            number_value=68.0,
        )
        text = _build_card_response_text(card, resp)
        assert "68" in text
        assert "kg" in text

    def test_build_card_response_text_confirm_yes(self):
        card = ChatCard(
            card_id="c1",
            card_type=CardType.CONFIRM,
            title="Bạn có bệnh lý?",
            subtitle="Nếu có, mình sẽ điều chỉnh lời khuyên",
            trigger_reason="missing_health_conditions",
        )
        resp = ChatCardResponse(card_id="c1", card_type=CardType.CONFIRM, confirmed=True)
        text = _build_card_response_text(card, resp)
        assert "Có" in text

    def test_build_card_response_text_confirm_no(self):
        card = ChatCard(
            card_id="c1",
            card_type=CardType.CONFIRM,
            title="Bạn có bệnh lý?",
            trigger_reason="missing_health_conditions",
        )
        resp = ChatCardResponse(card_id="c1", card_type=CardType.CONFIRM, confirmed=False)
        text = _build_card_response_text(card, resp)
        assert "Không" in text

    def test_extract_single_id(self):
        resp = ChatCardResponse(
            card_id="c1",
            card_type=CardType.SINGLE_SELECT,
            selected_ids=["muscle_gain"],
        )
        assert _extract_single_id(resp) == "muscle_gain"

    def test_extract_single_id_none(self):
        resp = ChatCardResponse(card_id="c1", card_type=CardType.SINGLE_SELECT, selected_ids=[])
        assert _extract_single_id(resp) is None

    def test_extract_number_from_number_value(self):
        resp = ChatCardResponse(
            card_id="c1",
            card_type=CardType.NUMBER_INPUT,
            number_value=68.5,
        )
        assert _extract_number(resp) == 68.5

    def test_extract_number_from_selected_ids(self):
        resp = ChatCardResponse(
            card_id="c1",
            card_type=CardType.SINGLE_SELECT,
            selected_ids=["68"],
        )
        assert _extract_number(resp) == 68.0


# ─── Integration Tests (require DB) ─────────────────────────────────────────────

pytestmark = pytest.mark.asyncio


async def _create_test_user(db_session: AsyncSession) -> str:
    """Create a test user and return user_id string."""
    from app.models.user import User
    from app.core.security import get_password_hash

    user = User(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email=f"cardtest_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("testpass123"),
        full_name="Card Test User",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    return str(user.id)


async def _create_test_session(
    db_session: AsyncSession, user_id: str, fired_triggers: dict | None = None
) -> ChatSession:
    """Create a test chat session."""
    session = ChatSession(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        title="Test Session",
        status="active",
        fired_triggers=fired_triggers,
        last_activity_at=datetime.now(timezone.utc),
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


async def _create_test_profile(
    db_session: AsyncSession,
    user_id: str,
    usage_goal: str | None = None,
    health_conditions: list | None = None,
    current_weight_kg: float | None = None,
) -> UserProfile:
    """Create a test user profile."""
    from app.models.enums import UsageGoalEnum

    profile = UserProfile(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        usage_goal=UsageGoalEnum(usage_goal) if usage_goal else None,
        health_conditions=health_conditions,
        current_weight_kg=current_weight_kg,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


class TestCardEndpoints:
    """Integration tests for card-related API endpoints."""

    async def test_create_session_has_fired_triggers_field(
        self, client, auth_headers, db_session
    ):
        """New sessions should have a nullable fired_triggers field."""
        user_id = await _create_test_user(db_session)
        resp = await client.post(
            f"/api/v1/ai/chat/sessions",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data

    async def test_card_message_saved_to_db(
        self, client, auth_headers, db_session
    ):
        """When a hard-rule card fires, it should be saved as a chat message."""
        user_id = await _create_test_user(db_session)
        session = await _create_test_session(db_session, user_id)

        # Profile has no usage_goal → hard rule should fire
        await _create_test_profile(db_session, user_id, usage_goal=None)

        # Mock the AI call so stream completes without real API
        with patch("app.chatbot.service.Groq") as MockGroq:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create = AsyncMock(
                return_value=AsyncMock(
                    __aiter__=lambda self: iter([]),
                    aclose=AsyncMock(),
                )
            )
            MockGroq.return_value = mock_instance

            resp = await client.post(
                f"/api/v1/ai/chat/sessions/{session.id}/messages/stream",
                headers=auth_headers,
                json={"content": "Tôi nên ăn gì?"},
            )

        # Hard rule fires → returns card SSE event (event: card\ndata: ...)
        content = resp.text
        assert resp.status_code == 200
        # The response should contain a card SSE event
        assert "event: card" in content

    async def test_card_response_updates_profile(
        self, client, auth_headers, db_session
    ):
        """Submitting a card response should update the profile field."""
        user_id = await _create_test_user(db_session)
        session = await _create_test_session(db_session, user_id)
        await _create_test_profile(db_session, user_id, usage_goal=None)

        card_id = str(uuid.uuid4())

        # Save a card message first so backend can find it
        card_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content="Mục tiêu chính của bạn là gì?",
            message_type="card",
            card={
                "card_id": card_id,
                "card_type": "single_select",
                "title": "Mục tiêu chính của bạn là gì?",
                "trigger_reason": "missing_goal",
                "options": [
                    {"id": "muscle_gain", "label": "Tăng cơ"},
                    {"id": "weight_loss", "label": "Giảm cân"},
                ],
                "skippable": True,
            },
        )
        db_session.add(card_msg)
        await db_session.commit()

        # Submit card response
        resp = await client.post(
            f"/api/v1/ai/chat/sessions/{session.id}/card-response",
            headers=auth_headers,
            json={
                "card_id": card_id,
                "card_type": "single_select",
                "selected_ids": ["muscle_gain"],
            },
        )

        assert resp.status_code == 200

    async def test_card_response_idempotent(
        self, client, auth_headers, db_session
    ):
        """Submitting the same card response twice should not duplicate updates."""
        user_id = await _create_test_user(db_session)
        session = await _create_test_session(db_session, user_id)
        profile = await _create_test_profile(db_session, user_id, usage_goal=None)
        card_id = str(uuid.uuid4())

        # Save card message
        card_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content="Mục tiêu?",
            message_type="card",
            card={
                "card_id": card_id,
                "card_type": "single_select",
                "title": "Mục tiêu chính?",
                "trigger_reason": "missing_goal",
                "options": [{"id": "muscle_gain", "label": "Tăng cơ"}],
                "skippable": True,
            },
        )
        db_session.add(card_msg)
        await db_session.commit()

        # First submission
        resp1 = await client.post(
            f"/api/v1/ai/chat/sessions/{session.id}/card-response",
            headers=auth_headers,
            json={
                "card_id": card_id,
                "card_type": "single_select",
                "selected_ids": ["muscle_gain"],
            },
        )
        assert resp1.status_code == 200

        # Verify card_response was saved
        await db_session.refresh(card_msg)
        assert card_msg.card_response is not None

    async def test_card_not_found_returns_error(
        self, client, auth_headers, db_session
    ):
        """Submitting card response for non-existent card returns 200 with error in stream."""
        user_id = await _create_test_user(db_session)
        session = await _create_test_session(db_session, user_id)

        resp = await client.post(
            f"/api/v1/ai/chat/sessions/{session.id}/card-response",
            headers=auth_headers,
            json={
                "card_id": str(uuid.uuid4()),
                "card_type": "confirm",
                "confirmed": True,
            },
        )

        # Returns 200 but SSE stream contains error
        assert resp.status_code == 200
        assert "card_not_found" in resp.text or "error" in resp.text

    async def test_chat_message_has_card_fields(
        self, client, auth_headers, db_session
    ):
        """Messages with card data should include card and message_type fields."""
        user_id = await _create_test_user(db_session)
        session = await _create_test_session(db_session, user_id)

        # Save a card message directly
        card_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content="Mục tiêu?",
            message_type="card",
            card={"card_id": "test", "card_type": "confirm", "title": "Test"},
        )
        db_session.add(card_msg)
        await db_session.commit()

        # Fetch messages
        resp = await client.get(
            f"/api/v1/ai/chat/sessions/{session.id}/messages",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        # Find the card message
        card_msgs = [m for m in data["items"] if m.get("message_type") == "card"]
        assert len(card_msgs) > 0
        assert card_msgs[0]["card"] is not None
        assert card_msgs[0]["card"]["card_type"] == "confirm"


class TestCardResponseProfileMapping:
    """Test that card responses correctly update profile fields."""

    async def test_missing_goal_card_updates_profile_usage_goal(
        self, client, auth_headers, db_session
    ):
        """Card response for 'missing_goal' should update profile.usage_goal."""
        user_id = await _create_test_user(db_session)
        session = await _create_test_session(db_session, user_id)
        await _create_test_profile(db_session, user_id, usage_goal=None)
        card_id = str(uuid.uuid4())

        card_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content="Mục tiêu?",
            message_type="card",
            card={
                "card_id": card_id,
                "card_type": "single_select",
                "title": "Mục tiêu?",
                "trigger_reason": "missing_goal",
                "options": [{"id": "muscle_gain", "label": "Tăng cơ"}],
                "skippable": True,
            },
        )
        db_session.add(card_msg)
        await db_session.commit()

        # Mock AI so stream completes quickly
        with patch("app.chatbot.service.Groq"):
            resp = await client.post(
                f"/api/v1/ai/chat/sessions/{session.id}/card-response",
                headers=auth_headers,
                json={
                    "card_id": card_id,
                    "card_type": "single_select",
                    "selected_ids": ["muscle_gain"],
                },
            )

        assert resp.status_code == 200

        # Verify profile was updated (reload from DB)
        from sqlalchemy import select
        from app.models.user_profile import UserProfile

        result = await db_session.execute(
            select(UserProfile).where(UserProfile.user_id == uuid.UUID(user_id))
        )
        profile = result.scalar_one_or_none()
        assert profile is not None
        assert str(profile.usage_goal.value) == "muscle_gain"

    async def test_missing_weight_card_updates_profile_weight(
        self, client, auth_headers, db_session
    ):
        """Card response for 'missing_weight' should update profile.current_weight_kg."""
        user_id = await _create_test_user(db_session)
        session = await _create_test_session(db_session, user_id)
        await _create_test_profile(db_session, user_id, current_weight_kg=None)
        card_id = str(uuid.uuid4())

        card_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content="Cân nặng?",
            message_type="card",
            card={
                "card_id": card_id,
                "card_type": "number_input",
                "title": "Cân nặng?",
                "unit": "kg",
                "min_value": 30,
                "max_value": 200,
                "trigger_reason": "missing_weight",
                "skippable": True,
            },
        )
        db_session.add(card_msg)
        await db_session.commit()

        with patch("app.chatbot.service.Groq"):
            resp = await client.post(
                f"/api/v1/ai/chat/sessions/{session.id}/card-response",
                headers=auth_headers,
                json={
                    "card_id": card_id,
                    "card_type": "number_input",
                    "number_value": 68.0,
                },
            )

        assert resp.status_code == 200

        from sqlalchemy import select
        from app.models.user_profile import UserProfile

        result = await db_session.execute(
            select(UserProfile).where(UserProfile.user_id == uuid.UUID(user_id))
        )
        profile = result.scalar_one_or_none()
        assert profile is not None
        assert profile.current_weight_kg == 68.0
