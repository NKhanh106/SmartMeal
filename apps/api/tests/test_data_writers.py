# -*- coding: utf-8 -*-
"""
Tests for the write-back system: data_writers and proposal_builder.

Run with:
    cd apps/api && python -m pytest tests/test_data_writers.py -v --tb=short
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.agents.proposal_builder import build_proposals_from_extraction
from app.schemas.update_proposal import UpdateProposal, UpdateTarget, UpdateField


class DummyContext:
    """Minimal FullUserContext stub for proposal_builder tests."""
    def __init__(self, **kwargs):
        self.weight_kg = kwargs.get("weight_kg")
        self.body = kwargs.get("body")
        self.health_conditions = kwargs.get("health_conditions", [])


def make_proposal(target: UpdateTarget, raw_data: dict) -> UpdateProposal:
    return UpdateProposal(
        target=target,
        fields=[UpdateField(label="Test", value="test", display="test")],
        summary="Test proposal",
        detail="Test detail",
        confidence=0.9,
        raw_data=raw_data,
        source_message="test message",
        session_id="test-session",
    )


# ─── proposal_builder tests ───────────────────────────────────────────────────

def test_proposal_builder_generates_meal_proposal():
    extraction = {
        "meals": [{
            "meal_type": "lunch",
            "confidence": "high",
            "items": [{"food_name": "Cơm gà", "calories": 550, "protein_g": 30}]
        }],
        "body_state": {},
        "health_events": [],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="Tôi vừa ăn cơm gà",
        session_id="session-1",
        current_context=None,
    )
    assert len(proposals) == 1
    assert proposals[0].target == UpdateTarget.MEAL_LOG
    assert proposals[0].confidence >= 0.7
    assert proposals[0].raw_data["meal_type"] == "lunch"
    assert proposals[0].raw_data["items"][0]["food_name"] == "Cơm gà"


def test_proposal_builder_low_confidence_meal_filtered():
    extraction = {
        "meals": [{
            "meal_type": "snack",
            "confidence": "low",
            "items": [{"food_name": "Something", "calories": 100}]
        }],
        "body_state": {},
        "health_events": [],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="maybe I ate something",
        session_id="session-1",
        current_context=None,
    )
    assert len(proposals) == 0


def test_proposal_builder_body_weight_proposal():
    extraction = {
        "meals": [],
        "body_state": {"weight_kg": 68.5},
        "health_events": [],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="tôi nặng 68.5kg",
        session_id="session-1",
        current_context=None,
    )
    weight_proposals = [p for p in proposals if p.target == UpdateTarget.BODY_WEIGHT]
    assert len(weight_proposals) == 1
    assert weight_proposals[0].raw_data["weight_kg"] == 68.5


def test_proposal_builder_body_weight_ignores_no_change():
    """If weight hasn't changed significantly, don't generate a proposal."""
    ctx = DummyContext(weight_kg=68.5)
    extraction = {
        "meals": [],
        "body_state": {"weight_kg": 68.5},  # same as current
        "health_events": [],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="vẫn nặng 68.5kg",
        session_id="session-1",
        current_context=ctx,
    )
    weight_proposals = [p for p in proposals if p.target == UpdateTarget.BODY_WEIGHT]
    assert len(weight_proposals) == 0


def test_proposal_builder_health_symptom_proposal():
    extraction = {
        "meals": [],
        "body_state": {},
        "health_events": [{
            "type": "symptom",
            "confidence": "high",
            "description": "đau đầu nhẹ",
            "category": "other",
            "severity": "mild"
        }],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="tôi bị đau đầu",
        session_id="session-1",
        current_context=None,
    )
    symptom_proposals = [p for p in proposals if p.target == UpdateTarget.HEALTH_SYMPTOM]
    assert len(symptom_proposals) == 1
    assert symptom_proposals[0].raw_data["description"] == "đau đầu nhẹ"
    assert symptom_proposals[0].raw_data["severity"] == "mild"


def test_proposal_builder_low_confidence_symptom_filtered():
    extraction = {
        "meals": [],
        "body_state": {},
        "health_events": [{
            "type": "symptom",
            "confidence": "low",
            "description": "có thể hơi mệt",
            "category": "other",
            "severity": "mild"
        }],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="có thể tôi hơi mệt",
        session_id="session-1",
        current_context=None,
    )
    assert len(proposals) == 0


def test_proposal_builder_workout_proposal():
    extraction = {
        "meals": [],
        "body_state": {},
        "health_events": [],
        "fitness": {
            "workout_completed": True,
            "workout_type": "Gym",
            "duration_minutes": 45
        }
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="tôi tập gym 45 phút",
        session_id="session-1",
        current_context=None,
    )
    workout_proposals = [p for p in proposals if p.target == UpdateTarget.WORKOUT_LOG]
    assert len(workout_proposals) == 1
    assert workout_proposals[0].raw_data["workout_type"] == "Gym"
    assert workout_proposals[0].raw_data["duration_minutes"] == 45


def test_proposal_builder_sleep_proposal():
    extraction = {
        "meals": [],
        "body_state": {"sleep_last_night": 7.0},
        "health_events": [],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="tôi ngủ 7 tiếng",
        session_id="session-1",
        current_context=None,
    )
    sleep_proposals = [p for p in proposals if p.target == UpdateTarget.SLEEP_LOG]
    assert len(sleep_proposals) == 1
    assert sleep_proposals[0].raw_data["hours"] == 7.0


def test_proposal_builder_multiple_proposals_from_single_extraction():
    """Full extraction generates all applicable proposal types."""
    extraction = {
        "meals": [{
            "meal_type": "lunch",
            "confidence": "high",
            "items": [{"food_name": "Phở bò", "calories": 450}]
        }],
        "body_state": {"weight_kg": 68.0, "sleep_last_night": 6.5},
        "health_events": [{
            "type": "symptom",
            "confidence": "high",
            "description": "đau lưng",
            "category": "muscular",
            "severity": "moderate"
        }],
        "fitness": {
            "workout_completed": True,
            "workout_type": "Yoga",
            "duration_minutes": 30
        }
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="test",
        session_id="s1",
        current_context=None,
    )
    assert len(proposals) == 5
    targets = {p.target for p in proposals}
    assert UpdateTarget.MEAL_LOG in targets
    assert UpdateTarget.BODY_WEIGHT in targets
    assert UpdateTarget.HEALTH_SYMPTOM in targets
    assert UpdateTarget.WORKOUT_LOG in targets
    assert UpdateTarget.SLEEP_LOG in targets


def test_proposal_builder_empty_extraction_returns_empty():
    extraction = {
        "meals": [],
        "body_state": {},
        "health_events": [],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="hello",
        session_id="session-1",
        current_context=None,
    )
    assert len(proposals) == 0


def test_proposal_builder_meal_type_mapping():
    """Verify meal type enum values are mapped correctly."""
    extraction = {
        "meals": [{
            "meal_type": "dinner",
            "confidence": "high",
            "items": [{"food_name": "Cơm", "calories": 300}]
        }],
        "body_state": {},
        "health_events": [],
        "fitness": {}
    }
    proposals = build_proposals_from_extraction(
        extraction=extraction,
        user_message="tôi ăn cơm tối",
        session_id="session-1",
        current_context=None,
    )
    assert proposals[0].raw_data["meal_type"] == "dinner"


# ─── UpdateProposal schema tests ─────────────────────────────────────────────

def test_update_proposal_auto_generates_id():
    proposal = UpdateProposal(
        target=UpdateTarget.MEAL_LOG,
        fields=[UpdateField(label="Bữa ăn", value="lunch", display="Bữa trưa")],
        summary="Test",
        detail="Test detail",
        confidence=0.9,
        raw_data={"items": []},
        source_message="test",
        session_id="s1",
    )
    assert proposal.proposal_id is not None
    assert len(proposal.proposal_id) > 0


def test_update_proposal_preserves_existing_id():
    existing_id = "my-custom-id-123"
    proposal = UpdateProposal(
        target=UpdateTarget.BODY_WEIGHT,
        fields=[],
        summary="Test",
        detail="Test",
        confidence=0.9,
        raw_data={},
        source_message="test",
        session_id="s1",
        proposal_id=existing_id,
    )
    assert proposal.proposal_id == existing_id


# ─── data_writers unit tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_body_weight_creates_progress_log():
    from app.agents.data_writers import _write_body_weight, DataWriteResult
    from uuid import uuid4

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock):
        result = await _write_body_weight(
            {"weight_kg": 68.5, "measured_at": "2026-05-26"},
            user_id=1,
            db=mock_db,
        )

    assert result.success is True
    assert "68.5" in result.message
    assert result.records_created >= 1


@pytest.mark.asyncio
async def test_write_body_weight_missing_weight_returns_error():
    from app.agents.data_writers import _write_body_weight

    mock_db = AsyncMock()
    result = await _write_body_weight({}, user_id=1, db=mock_db)
    assert result.success is False
    assert "Missing weight_kg" in result.error


@pytest.mark.asyncio
async def test_write_health_symptom_creates_event():
    from app.agents.data_writers import _write_health_symptom

    mock_db = AsyncMock()
    with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
        result = await _write_health_symptom(
            {"description": "đau đầu", "category": "other", "severity": "mild"},
            user_id=1,
            db=mock_db,
        )

    assert result.success is True
    assert "đau đầu" in result.message
    mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_write_workout_log_updates_memory():
    from app.agents.data_writers import _write_workout_log

    mock_db = AsyncMock()
    with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
        result = await _write_workout_log(
            {"workout_type": "Gym", "duration_minutes": 45},
            user_id=1,
            db=mock_db,
        )

    assert result.success is True
    assert "Gym" in result.message
    assert "45" in result.message
    mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_write_muscle_soreness_add_areas():
    from app.agents.data_writers import _write_muscle_soreness

    mock_db = AsyncMock()
    with patch("app.agents.data_writers.get_or_create_memory", new_callable=AsyncMock) as mock_get_mem:
        mock_memory = MagicMock()
        mock_memory.body_snapshot = {"muscle_status": {"sore_areas": ["lower_back"]}}
        mock_get_mem.return_value = mock_memory

        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock):
            result = await _write_muscle_soreness(
                {"sore_areas": ["right_arm"], "action": "add"},
                user_id=1,
                db=mock_db,
            )

    assert result.success is True
    assert "right_arm" in result.message or "Đã ghi nhận" in result.message


@pytest.mark.asyncio
async def test_write_profile_metric_updates_user_profile():
    from app.agents.data_writers import _write_profile_metric

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    result = await _write_profile_metric(
        {"height_cm": 175.0, "weight_kg": 68.0},
        user_id=1,
        db=mock_db,
    )
    assert result.success is True
    assert "175" in result.message or "ho so" in result.message.lower()


@pytest.mark.asyncio
async def test_execute_confirmed_update_unknown_target():
    from app.agents.data_writers import execute_confirmed_update
    from app.schemas.update_proposal import UpdateProposal, UpdateTarget

    mock_db = AsyncMock()
    fake_proposal = UpdateProposal(
        target=UpdateTarget.HEALTH_CONDITION,
        fields=[],
        summary="test",
        detail="test",
        confidence=0.9,
        raw_data={},
        source_message="test",
        session_id="s1",
    )
    result = await execute_confirmed_update(fake_proposal, user_id=1, db=mock_db)
    assert result.success is False
    assert "Khong ho tro" in result.message or "No writer" in result.error
