"""Tests for ExtractorAgent (Agent 1).

Covers:
- Meal extraction from clear statements
- Health event extraction from symptom mentions
- Sore areas additive update (never replace)
- Food reactions → facts with food_reaction category
- Low-confidence items go to key_facts, not body_snapshot
- Session marked as extracted after run
- Safe JSON failure handling
- No blocking on errors
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentContext, AgentResult
from app.agents.extractor_agent import ExtractorAgent
from app.models.user_memory import UserMemory


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def agent() -> ExtractorAgent:
    return ExtractorAgent()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user.email = "test@example.com"
    user.full_name = "Test User"
    return user


@pytest.fixture
def mock_memory():
    mem = MagicMock(spec=UserMemory)
    mem.body_snapshot = {}
    mem.health_events = []
    mem.nutrition_memory = {}
    mem.fitness_memory = {}
    mem.key_facts = []
    mem.conversation_summary = ""
    return mem


# ── Test 1: Extracts meal correctly from clear statement ────────────────────────

@pytest.mark.asyncio
async def test_extract_meal_from_message(agent, mock_user, mock_memory):
    """
    User says: "Hôm nay tôi ăn phở bò buổi sáng và cơm gà buổi trưa"
    → nutrition_memory.recent_meals should have 2 entries.
    """
    mock_memory.nutrition_memory = {}
    session_id = str(uuid.uuid4())
    context = AgentContext(
        user=mock_user,
        session_id=session_id,
        current_message="Hôm nay tôi ăn phở bò buổi sáng và cơm gà buổi trưa",
        conversation_history=[],
        profile=None,
        memory=mock_memory,
    )

    ai_response = {
        "meals": [
            {
                "date": "2026-05-13",
                "meal_type": "breakfast",
                "items": ["phở bò"],
                "estimated_kcal": 450,
                "confidence": "high",
            },
            {
                "date": "2026-05-13",
                "meal_type": "lunch",
                "items": ["cơm gà"],
                "estimated_kcal": 550,
                "confidence": "high",
            },
        ],
        "body_state": {},
        "health_events": [],
        "facts": [],
        "fitness": {},
    }

    async def run_test():
        with patch.object(agent, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ai_response
            with patch.object(agent, "_log_start") as mock_log_start:
                mock_run = MagicMock()
                mock_log_start.return_value = mock_run
                with patch.object(agent, "_log_complete", new_callable=AsyncMock):
                    with patch.object(agent, "_update_memory", new_callable=AsyncMock):
                        with patch.object(agent, "_mark_session_extracted", new_callable=AsyncMock):
                            return await agent.run(context, MagicMock())

    result = await run_test()
    assert result.success is True
    assert result.insight_type == "extraction"
    assert "recent_meals" in result.memory_updates
    meals = result.memory_updates["recent_meals"]
    assert len(meals) == 2
    assert meals[0]["meal_type"] == "breakfast"
    assert meals[1]["meal_type"] == "lunch"


# ── Test 2: Extracts health event from symptom mention ────────────────────────────

@pytest.mark.asyncio
async def test_extract_health_event(agent, mock_user, mock_memory):
    """
    User says: "Tôi bị tiêu chảy từ tối qua, khá mệt"
    → health_events should have a digestive/moderate event.
    """
    session_id = str(uuid.uuid4())
    context = AgentContext(
        user=mock_user,
        session_id=session_id,
        current_message="Tôi bị tiêu chảy từ tối qua, khá mệt",
        conversation_history=[],
        profile=None,
        memory=mock_memory,
    )

    ai_response = {
        "meals": [],
        "body_state": {"energy_level": "low", "digestion_status": "diarrhea"},
        "health_events": [
            {
                "date": "2026-05-13",
                "type": "symptom",
                "category": "digestive",
                "description": "Tiêu chảy từ tối qua",
                "severity": "moderate",
            },
        ],
        "facts": [],
        "fitness": {},
    }

    async def run_test():
        with patch.object(agent, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ai_response
            with patch.object(agent, "_log_start") as mock_log_start:
                mock_run = MagicMock()
                mock_log_start.return_value = mock_run
                with patch.object(agent, "_log_complete", new_callable=AsyncMock):
                    with patch.object(agent, "_update_memory", new_callable=AsyncMock):
                        with patch.object(agent, "_mark_session_extracted", new_callable=AsyncMock):
                            return await agent.run(context, MagicMock())

    result = await run_test()
    assert result.success is True
    assert "health_events" in result.memory_updates
    events = result.memory_updates["health_events"]
    assert len(events) == 1
    assert events[0]["category"] == "digestive"
    assert events[0]["type"] == "symptom"


# ── Test 3: Sore areas are additive (never replace) ────────────────────────────

@pytest.mark.asyncio
async def test_sore_areas_additive_update(agent, mock_user):
    """
    Existing: sore_areas = ["lower_back"]
    User: "Hôm nay tập gym bị đau bắp tay phải"
    → Result sore_areas: ["lower_back", "right_arm"] (both present).
    """
    existing_memory = MagicMock(spec=UserMemory)
    existing_memory.body_snapshot = {"sore_areas": ["lower_back"]}
    existing_memory.health_events = []
    existing_memory.nutrition_memory = {}
    existing_memory.fitness_memory = {}
    existing_memory.key_facts = []
    existing_memory.conversation_summary = ""

    session_id = str(uuid.uuid4())
    context = AgentContext(
        user=mock_user,
        session_id=session_id,
        current_message="Hôm nay tập gym bị đau bắp tay phải",
        conversation_history=[],
        profile=None,
        memory=existing_memory,
    )

    ai_response = {
        "meals": [],
        "body_state": {"sore_areas": ["right_arm"]},
        "health_events": [],
        "facts": [],
        "fitness": {"workout_type": "gym"},
    }

    async def run_test():
        with patch.object(agent, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ai_response
            with patch.object(agent, "_log_start") as mock_log_start:
                mock_run = MagicMock()
                mock_log_start.return_value = mock_run
                with patch.object(agent, "_log_complete", new_callable=AsyncMock):
                    with patch.object(agent, "_update_memory", new_callable=AsyncMock):
                        with patch.object(agent, "_mark_session_extracted", new_callable=AsyncMock):
                            return await agent.run(context, MagicMock())

    result = await run_test()
    assert "body_snapshot" in result.memory_updates
    snapshot = result.memory_updates["body_snapshot"]
    assert "sore_areas" in snapshot
    assert "lower_back" in snapshot["sore_areas"]
    assert "right_arm" in snapshot["sore_areas"]
    assert len(snapshot["sore_areas"]) == 2


# ── Test 4: Food reaction → facts with food_reaction category ─────────────────

@pytest.mark.asyncio
async def test_food_reaction_extraction(agent, mock_user, mock_memory):
    """
    User: "Ăn sữa xong tôi bị tiêu chảy"
    → key_facts should have entry with category "food_reaction" mentioning "sữa".
    """
    session_id = str(uuid.uuid4())
    context = AgentContext(
        user=mock_user,
        session_id=session_id,
        current_message="Ăn sữa xong tôi bị tiêu chảy",
        conversation_history=[],
        profile=None,
        memory=mock_memory,
    )

    ai_response = {
        "meals": [],
        "body_state": {"digestion_status": "diarrhea"},
        "health_events": [
            {
                "date": "2026-05-13",
                "type": "symptom",
                "category": "digestive",
                "description": "Tiêu chảy sau khi uống sữa",
                "severity": "mild",
            },
        ],
        "facts": [
            {
                "fact": "Sữa gây tiêu chảy — cần tránh",
                "category": "food_reaction",
                "confidence": "high",
            },
        ],
        "fitness": {},
    }

    async def run_test():
        with patch.object(agent, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ai_response
            with patch.object(agent, "_log_start") as mock_log_start:
                mock_run = MagicMock()
                mock_log_start.return_value = mock_run
                with patch.object(agent, "_log_complete", new_callable=AsyncMock):
                    with patch.object(agent, "_update_memory", new_callable=AsyncMock):
                        with patch.object(agent, "_mark_session_extracted", new_callable=AsyncMock):
                            return await agent.run(context, MagicMock())

    result = await run_test()
    assert "key_facts" in result.memory_updates
    facts = result.memory_updates["key_facts"]
    food_reaction_facts = [f for f in facts if f.get("category") == "food_reaction"]
    assert len(food_reaction_facts) >= 1
    assert any("sữa" in f["fact"].lower() for f in food_reaction_facts)


# ── Test 5: JSON parse failure → graceful empty result ─────────────────────────

@pytest.mark.asyncio
async def test_json_parse_failure_returns_empty_result(agent, mock_user, mock_memory):
    """
    If AI returns invalid JSON, agent returns success=True with empty content
    and does NOT raise an exception.
    """
    session_id = str(uuid.uuid4())
    context = AgentContext(
        user=mock_user,
        session_id=session_id,
        current_message="Hôm nay tôi ăn cơm",
        conversation_history=[],
        profile=None,
        memory=mock_memory,
    )

    async def run_test():
        with patch.object(agent, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Đây không phải JSON hợp lệ"
            with patch.object(agent, "_log_start") as mock_log_start:
                mock_run = MagicMock()
                mock_log_start.return_value = mock_run
                with patch.object(agent, "_log_complete", new_callable=AsyncMock):
                    with patch.object(agent, "_update_memory", new_callable=AsyncMock):
                        with patch.object(agent, "_mark_session_extracted", new_callable=AsyncMock):
                            return await agent.run(context, MagicMock())

    result = await run_test()
    assert result.success is True
    assert result.content == {}
    assert result.error is None


# ── Test 6: Session marked as extracted after run ───────────────────────────────

@pytest.mark.asyncio
async def test_session_marked_extracted_after_run(agent, mock_user, mock_memory):
    """
    After agent.run(), _mark_session_extracted should be called with the correct session_id.
    """
    session_id = str(uuid.uuid4())
    context = AgentContext(
        user=mock_user,
        session_id=session_id,
        current_message="Tôi ăn phở",
        conversation_history=[],
        profile=None,
        memory=mock_memory,
    )

    ai_response = {
        "meals": [
            {
                "date": "2026-05-13",
                "meal_type": "lunch",
                "items": ["phở"],
                "estimated_kcal": 400,
                "confidence": "high",
            }
        ],
        "body_state": {},
        "health_events": [],
        "facts": [],
        "fitness": {},
    }

    async def run_test():
        with patch.object(agent, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ai_response
            with patch.object(agent, "_log_start") as mock_log_start:
                mock_run = MagicMock()
                mock_log_start.return_value = mock_run
                with patch.object(agent, "_log_complete", new_callable=AsyncMock):
                    with patch.object(agent, "_update_memory", new_callable=AsyncMock):
                        with patch.object(agent, "_mark_session_extracted", new_callable=AsyncMock) as mock_mark:
                            await agent.run(context, MagicMock())
                            return mock_mark

    mock_mark = await run_test()
    mock_mark.assert_called_once()
    assert mock_mark.call_args[0][0] == session_id


# ── Test 7: Exception does not propagate (non-blocking) ───────────────────────

@pytest.mark.asyncio
async def test_exception_does_not_propagate(agent, mock_user, mock_memory):
    """
    If an unexpected exception occurs, agent returns a failure AgentResult
    and does NOT raise. Orchestrator can continue normally.
    """
    session_id = str(uuid.uuid4())
    context = AgentContext(
        user=mock_user,
        session_id=session_id,
        current_message="Test",
        conversation_history=[],
        profile=None,
        memory=mock_memory,
    )

    async def run_test():
        with patch.object(agent, "_call_ai", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = RuntimeError("Simulated AI failure")
            with patch.object(agent, "_log_start") as mock_log_start:
                mock_run = MagicMock()
                mock_log_start.return_value = mock_run
                with patch.object(agent, "_log_complete", new_callable=AsyncMock):
                    return await agent.run(context, MagicMock())

    result = await run_test()
    assert result.success is False
    assert result.error is not None
    assert "Simulated AI failure" in result.error


# ── Test 8: _merge_sore_areas deduplicates correctly ────────────────────────────

def test_merge_sore_areas_deduplicates(agent):
    """_merge_sore_areas should add new areas without creating duplicates."""
    existing = ["lower_back", "right_arm"]
    new = ["lower_back", "left_knee"]
    result = agent._merge_sore_areas(existing, new)
    assert result.count("lower_back") == 1
    assert "right_arm" in result
    assert "left_knee" in result
    assert len(result) == 3
