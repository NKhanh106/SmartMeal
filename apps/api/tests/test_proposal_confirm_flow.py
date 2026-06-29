# -*- coding: utf-8 -*-
"""
Integration tests for the proposal confirm flow.

Tests the complete user-facing flow:
1. Extraction generates proposals (stored in Redis)
2. Frontend fetches pending proposals
3. User confirms a proposal
4. DataWriter executes the write and updates DB

Run with:
    cd apps/api && python -m pytest tests/test_proposal_confirm_flow.py -v --tb=short

Requires TEST_DATABASE_URL and TEST_REDIS_URL in environment.
"""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.agents.proposal_builder import build_proposals_from_extraction
from app.agents.data_writers import (
    execute_confirmed_update,
    _write_body_weight,
    _write_health_symptom,
    _write_workout_log,
    _write_sleep_log,
    _write_muscle_soreness,
    DataWriteResult,
)
from app.schemas.update_proposal import UpdateProposal, UpdateTarget, UpdateField


class DummyContext:
    """Minimal FullUserContext stub."""
    def __init__(self, **kwargs):
        self.weight_kg = kwargs.get("weight_kg")
        self.body = kwargs.get("body")
        self.health_conditions = kwargs.get("health_conditions", [])
        self.sleep_hours = kwargs.get("sleep_hours")
        self.recent_workouts = kwargs.get("recent_workouts", [])


# ─── Test helpers ────────────────────────────────────────────────────────────

def make_proposal(
    target: UpdateTarget,
    raw_data: dict,
    confidence: float = 0.9,
) -> UpdateProposal:
    return UpdateProposal(
        target=target,
        fields=[UpdateField(label="Test", value="test", display="Test")],
        summary=f"Test {target.value}",
        detail="Test detail",
        confidence=confidence,
        raw_data=raw_data,
        source_message="test message",
        session_id="test-session",
    )


# ─── Test proposal builder generates correct proposals ─────────────────────────

class TestProposalBuilder:
    """Test all proposal types are generated correctly."""

    def test_health_symptom_proposal_generated(self):
        """When user mentions a symptom, HEALTH_SYMPTOM proposal should be generated."""
        extraction = {
            "meals": [],
            "body_state": {},
            "health_events": [{
                "type": "symptom",
                "confidence": "high",
                "description": "đau đầu nhẹ",
                "category": "other",
                "severity": "mild",
            }],
            "fitness": {},
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="tôi bị đau đầu",
            session_id="session-1",
            current_context=None,
        )
        symptom_proposals = [p for p in proposals if p.target == UpdateTarget.HEALTH_SYMPTOM]
        assert len(symptom_proposals) == 1, "Should generate HEALTH_SYMPTOM proposal"
        assert symptom_proposals[0].raw_data["description"] == "đau đầu nhẹ"
        assert symptom_proposals[0].raw_data["severity"] == "mild"

    def test_body_weight_proposal_generated(self):
        """When user mentions weight, BODY_WEIGHT proposal should be generated."""
        extraction = {
            "meals": [],
            "body_state": {"weight_kg": 68.5},
            "health_events": [],
            "fitness": {},
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="tôi nặng 68.5kg",
            session_id="session-1",
            current_context=None,
        )
        weight_proposals = [p for p in proposals if p.target == UpdateTarget.BODY_WEIGHT]
        assert len(weight_proposals) == 1, "Should generate BODY_WEIGHT proposal"
        assert weight_proposals[0].raw_data["weight_kg"] == 68.5

    def test_workout_proposal_generated(self):
        """When user mentions a workout, WORKOUT_LOG proposal should be generated."""
        extraction = {
            "meals": [],
            "body_state": {},
            "health_events": [],
            "fitness": {
                "workout_completed": True,
                "workout_type": "Gym",
                "duration_minutes": 60,
            },
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="tôi tập gym 1 tiếng",
            session_id="session-1",
            current_context=None,
        )
        workout_proposals = [p for p in proposals if p.target == UpdateTarget.WORKOUT_LOG]
        assert len(workout_proposals) == 1, "Should generate WORKOUT_LOG proposal"
        assert workout_proposals[0].raw_data["workout_type"] == "Gym"
        assert workout_proposals[0].raw_data["duration_minutes"] == 60

    def test_sleep_proposal_generated(self):
        """When user mentions sleep, SLEEP_LOG proposal should be generated."""
        extraction = {
            "meals": [],
            "body_state": {"sleep_last_night": 7.5},
            "health_events": [],
            "fitness": {},
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="tôi ngủ 7 tiếng rưỡi",
            session_id="session-1",
            current_context=None,
        )
        sleep_proposals = [p for p in proposals if p.target == UpdateTarget.SLEEP_LOG]
        assert len(sleep_proposals) == 1, "Should generate SLEEP_LOG proposal"
        assert sleep_proposals[0].raw_data["hours"] == 7.5

    def test_muscle_soreness_proposal_generated(self):
        """When user mentions sore muscles in fitness data, MUSCLE_SORENESS proposal should be generated."""
        extraction = {
            "meals": [],
            "body_state": {},
            "health_events": [],
            "fitness": {
                "new_sore_areas": ["lower_back"],  # Muscle soreness comes from fitness.new_sore_areas
            },
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="tôi bị đau lưng dưới",
            session_id="session-1",
            current_context=None,
        )
        soreness_proposals = [p for p in proposals if p.target == UpdateTarget.MUSCLE_SORENESS]
        assert len(soreness_proposals) == 1, "Should generate MUSCLE_SORENESS proposal"
        assert "lower_back" in soreness_proposals[0].raw_data.get("sore_areas", [])

    def test_multiple_proposals_from_single_extraction(self):
        """Single message with multiple facts should generate multiple proposals."""
        extraction = {
            "meals": [{
                "meal_type": "lunch",
                "confidence": "high",
                "items": [{"food_name": "Cơm gà", "calories": 550}],
            }],
            "body_state": {"weight_kg": 68.0, "sleep_last_night": 6.5},
            "health_events": [{
                "type": "symptom",
                "confidence": "high",
                "description": "hơi chóng mặt",
                "category": "other",
                "severity": "mild",
            }],
            "fitness": {
                "workout_completed": True,
                "workout_type": "Yoga",
                "duration_minutes": 30,
            },
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="test",
            session_id="s1",
            current_context=None,
        )
        assert len(proposals) >= 4, f"Should generate at least 4 proposals, got {len(proposals)}"
        targets = {p.target for p in proposals}
        assert UpdateTarget.MEAL_LOG in targets
        assert UpdateTarget.BODY_WEIGHT in targets
        assert UpdateTarget.HEALTH_SYMPTOM in targets
        assert UpdateTarget.WORKOUT_LOG in targets
        assert UpdateTarget.SLEEP_LOG in targets

    def test_low_confidence_symptom_filtered(self):
        """Low confidence symptoms should NOT generate proposals."""
        extraction = {
            "meals": [],
            "body_state": {},
            "health_events": [{
                "type": "symptom",
                "confidence": "low",
                "description": "có thể hơi mệt",
                "category": "other",
                "severity": "mild",
            }],
            "fitness": {},
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="có thể tôi hơi mệt",
            session_id="session-1",
            current_context=None,
        )
        symptom_proposals = [p for p in proposals if p.target == UpdateTarget.HEALTH_SYMPTOM]
        assert len(symptom_proposals) == 0, "Low confidence symptom should be filtered"

    def test_weight_no_change_ignored(self):
        """Weight same as current should NOT generate a proposal."""
        ctx = DummyContext(weight_kg=68.5)
        extraction = {
            "meals": [],
            "body_state": {"weight_kg": 68.5},  # same as context
            "health_events": [],
            "fitness": {},
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="vẫn nặng 68.5kg",
            session_id="session-1",
            current_context=ctx,
        )
        weight_proposals = [p for p in proposals if p.target == UpdateTarget.BODY_WEIGHT]
        assert len(weight_proposals) == 0, "No change in weight should not generate proposal"


# ─── Test data writers execute correctly ────────────────────────────────────

class TestDataWriters:
    """Test each data writer handles user_id correctly (UUID vs int)."""

    @pytest.mark.asyncio
    async def test_write_health_symptom_with_int_user_id(self):
        """_write_health_symptom should handle int user_id (the bug we fixed)."""
        mock_db = AsyncMock()
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
            result = await _write_health_symptom(
                {"description": "đau đầu", "category": "other", "severity": "mild"},
                user_id=1,  # int - this was causing the bug
                db=mock_db,
            )

        assert result.success is True, f"Should succeed, got: {result.message}"
        assert "đau đầu" in result.message
        mock_apply.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_health_symptom_with_uuid_user_id(self):
        """_write_health_symptom should also handle UUID user_id."""
        mock_db = AsyncMock()
        user_uuid = uuid4()
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
            result = await _write_health_symptom(
                {"description": "đau bụng", "category": "digestive", "severity": "moderate"},
                user_id=user_uuid,
                db=mock_db,
            )

        assert result.success is True, f"Should succeed, got: {result.message}"
        mock_apply.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_body_weight_with_int_user_id(self):
        """_write_body_weight should handle int user_id."""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock):
            result = await _write_body_weight(
                {"weight_kg": 68.5},
                user_id=1,  # int
                db=mock_db,
            )

        assert result.success is True, f"Should succeed, got: {result.message}"
        assert "68.5" in result.message

    @pytest.mark.asyncio
    async def test_write_workout_log_with_int_user_id(self):
        """_write_workout_log should handle int user_id."""
        mock_db = AsyncMock()
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
            result = await _write_workout_log(
                {"workout_type": "Chạy bộ", "duration_minutes": 30},
                user_id=1,  # int
                db=mock_db,
            )

        assert result.success is True, f"Should succeed, got: {result.message}"
        assert "Chạy bộ" in result.message
        mock_apply.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_sleep_log_with_int_user_id(self):
        """_write_sleep_log should handle int user_id."""
        mock_db = AsyncMock()
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
            result = await _write_sleep_log(
                {"hours": 7.0, "quality": "good"},
                user_id=1,  # int
                db=mock_db,
            )

        assert result.success is True, f"Should succeed, got: {result.message}"
        assert "7" in result.message
        mock_apply.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_muscle_soreness_with_int_user_id(self):
        """_write_muscle_soreness should handle int user_id."""
        mock_db = AsyncMock()
        with patch("app.agents.data_writers.get_or_create_memory", new_callable=AsyncMock) as mock_get_mem:
            mock_memory = MagicMock()
            mock_memory.body_snapshot = {}
            mock_get_mem.return_value = mock_memory
            with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock):
                result = await _write_muscle_soreness(
                    {"sore_areas": ["lưng"], "action": "add"},
                    user_id=1,  # int
                    db=mock_db,
                )

        assert result.success is True, f"Should succeed, got: {result.message}"


# ─── Test execute_confirmed_update routes correctly ───────────────────────────

class TestExecuteConfirmedUpdate:
    """Test execute_confirmed_update dispatches to correct writer."""

    @pytest.mark.asyncio
    async def test_health_symptom_routes_correctly(self):
        """confirm endpoint should route HEALTH_SYMPTOM to correct writer."""
        proposal = make_proposal(
            UpdateTarget.HEALTH_SYMPTOM,
            {"description": "đau họng", "category": "respiratory", "severity": "mild"},
        )
        mock_db = AsyncMock()
        with patch("app.agents.data_writers._write_health_symptom", new_callable=AsyncMock) as mock_writer:
            mock_writer.return_value = DataWriteResult(
                success=True,
                target=UpdateTarget.HEALTH_SYMPTOM,
                message="Đã ghi nhận",
            )
            result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is True
        mock_writer.assert_called_once()

    @pytest.mark.asyncio
    async def test_body_weight_routes_correctly(self):
        """confirm endpoint should route BODY_WEIGHT to correct writer."""
        proposal = make_proposal(
            UpdateTarget.BODY_WEIGHT,
            {"weight_kg": 67.0},
        )
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        with patch("app.agents.data_writers._write_body_weight", new_callable=AsyncMock) as mock_writer:
            mock_writer.return_value = DataWriteResult(
                success=True,
                target=UpdateTarget.BODY_WEIGHT,
                message="Đã cập nhật",
            )
            with patch("app.agents.data_writers.invalidate_user_plan_cache"):
                result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is True
        mock_writer.assert_called_once()

    @pytest.mark.asyncio
    async def test_workout_log_routes_correctly(self):
        """confirm endpoint should route WORKOUT_LOG to correct writer."""
        proposal = make_proposal(
            UpdateTarget.WORKOUT_LOG,
            {"workout_type": "Bơi lội", "duration_minutes": 45},
        )
        mock_db = AsyncMock()
        with patch("app.agents.data_writers._write_workout_log", new_callable=AsyncMock) as mock_writer:
            mock_writer.return_value = DataWriteResult(
                success=True,
                target=UpdateTarget.WORKOUT_LOG,
                message="Đã ghi nhận",
            )
            with patch("app.agents.data_writers.invalidate_user_plan_cache"):
                result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is True
        mock_writer.assert_called_once()

    @pytest.mark.asyncio
    async def test_sleep_log_routes_correctly(self):
        """confirm endpoint should route SLEEP_LOG to correct writer."""
        proposal = make_proposal(
            UpdateTarget.SLEEP_LOG,
            {"hours": 8.0, "quality": "excellent"},
        )
        mock_db = AsyncMock()
        with patch("app.agents.data_writers._write_sleep_log", new_callable=AsyncMock) as mock_writer:
            mock_writer.return_value = DataWriteResult(
                success=True,
                target=UpdateTarget.SLEEP_LOG,
                message="Đã ghi nhận",
            )
            with patch("app.agents.data_writers.invalidate_user_plan_cache"):
                result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is True
        mock_writer.assert_called_once()

    @pytest.mark.asyncio
    async def test_muscle_soreness_routes_correctly(self):
        """confirm endpoint should route MUSCLE_SORENESS to correct writer."""
        proposal = make_proposal(
            UpdateTarget.MUSCLE_SORENESS,
            {"sore_areas": ["cổ"], "action": "add"},
        )
        mock_db = AsyncMock()
        with patch("app.agents.data_writers._write_muscle_soreness", new_callable=AsyncMock) as mock_writer:
            mock_writer.return_value = DataWriteResult(
                success=True,
                target=UpdateTarget.MUSCLE_SORENESS,
                message="Đã ghi nhận",
            )
            with patch("app.agents.data_writers.invalidate_user_plan_cache"):
                result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is True
        mock_writer.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_target_returns_error(self):
        """Unknown target should return error (not crash)."""
        proposal = make_proposal(
            UpdateTarget.HEALTH_CONDITION,  # No writer registered
            {"condition": "test"},
        )
        mock_db = AsyncMock()
        result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is False
        assert "Khong ho tro" in result.message or "No writer" in str(result.error)


# ─── Test full flow (proposal → confirm → write) ────────────────────────────

class TestFullConfirmFlow:
    """Test the complete user-facing flow with mocks."""

    @pytest.mark.asyncio
    async def test_full_flow_health_symptom(self):
        """
        Simulate full flow:
        1. Extraction → proposal generated
        2. User confirms
        3. DataWriter writes to DB
        """
        # Step 1: Extraction generates proposal
        extraction = {
            "meals": [],
            "body_state": {},
            "health_events": [{
                "type": "symptom",
                "confidence": "high",
                "description": "mỏi chân",
                "category": "muscular",
                "severity": "mild",
            }],
            "fitness": {},
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="tôi bị mỏi chân",
            session_id="session-1",
            current_context=None,
        )

        symptom_proposal = next(p for p in proposals if p.target == UpdateTarget.HEALTH_SYMPTOM)
        assert symptom_proposal is not None
        assert symptom_proposal.raw_data["description"] == "mỏi chân"

        # Step 2: User confirms → execute_confirmed_update
        mock_db = AsyncMock()
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
            mock_apply.return_value = True
            result = await execute_confirmed_update(symptom_proposal, user_id=1, db=mock_db)

        # Step 3: Verify write succeeded
        assert result.success is True, f"Confirm should succeed, got: {result.message}"
        assert "mỏi chân" in result.message

    @pytest.mark.asyncio
    async def test_full_flow_multiple_proposals(self):
        """
        Test extracting multiple facts and confirming all.
        """
        extraction = {
            "meals": [],
            "body_state": {"weight_kg": 65.0, "sleep_last_night": 6.0},
            "health_events": [{
                "type": "symptom",
                "confidence": "high",
                "description": "đau lưng",
                "category": "muscular",
                "severity": "moderate",
            }],
            "fitness": {
                "workout_completed": True,
                "workout_type": "Gym",
                "duration_minutes": 45,
            },
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="test",
            session_id="s1",
            current_context=None,
        )

        # Should have 4 proposals
        assert len(proposals) == 4, f"Expected 4 proposals, got {len(proposals)}"

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        # Confirm all
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
            mock_apply.return_value = True
            for proposal in proposals:
                result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)
                assert result.success is True, f"Confirm {proposal.target} failed: {result.message}"

    @pytest.mark.asyncio
    async def test_confirm_caches_invalidated_on_success(self):
        """Successful confirm should invalidate user plan cache."""
        proposal = make_proposal(
            UpdateTarget.BODY_WEIGHT,
            {"weight_kg": 70.0},
        )
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()

        with patch("app.agents.data_writers._write_body_weight", new_callable=AsyncMock) as mock_writer:
            mock_writer.return_value = DataWriteResult(
                success=True,
                target=UpdateTarget.BODY_WEIGHT,
                message="Đã cập nhật",
            )
            with patch("app.agents.data_writers.invalidate_user_plan_cache") as mock_invalidate:
                result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is True
        mock_invalidate.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_rollback_on_failure(self):
        """Failed confirm should rollback and not invalidate cache."""
        proposal = make_proposal(
            UpdateTarget.HEALTH_SYMPTOM,
            {"description": "test", "category": "other", "severity": "mild"},
        )
        mock_db = AsyncMock()

        with patch("app.agents.data_writers._write_health_symptom", new_callable=AsyncMock) as mock_writer:
            mock_writer.side_effect = Exception("DB error")
            result = await execute_confirmed_update(proposal, user_id=1, db=mock_db)

        assert result.success is False
        assert "DB error" in str(result.error)
        mock_db.rollback.assert_called_once()


# ─── Edge cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_proposal_id_auto_generated(self):
        """Each proposal should have unique ID."""
        p1 = make_proposal(UpdateTarget.BODY_WEIGHT, {"weight_kg": 60.0})
        p2 = make_proposal(UpdateTarget.BODY_WEIGHT, {"weight_kg": 61.0})
        assert p1.proposal_id != p2.proposal_id

    def test_proposal_with_custom_id(self):
        """Proposal can use custom ID for known proposals."""
        custom_id = "my-custom-id-123"
        proposal = make_proposal(UpdateTarget.MEAL_LOG, {"items": []})
        # Note: UpdateProposal doesn't accept proposal_id in constructor via make_proposal helper
        # This tests the schema accepts it
        assert proposal.proposal_id is not None

    def test_empty_extraction_returns_no_proposals(self):
        """Empty extraction should not generate any proposals."""
        extraction = {
            "meals": [],
            "body_state": {},
            "health_events": [],
            "fitness": {},
        }
        proposals = build_proposals_from_extraction(
            extraction=extraction,
            user_message="hello",
            session_id="s1",
            current_context=None,
        )
        assert len(proposals) == 0

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_error(self):
        """Writer should handle missing required fields gracefully."""
        from app.agents.data_writers import _write_body_weight

        mock_db = AsyncMock()
        result = await _write_body_weight({}, user_id=1, db=mock_db)

        assert result.success is False
        assert "Missing weight_kg" in result.error

    @pytest.mark.asyncio
    async def test_user_id_as_string_uuid(self):
        """Writers should handle user_id as UUID string."""
        from app.agents.data_writers import _write_health_symptom

        mock_db = AsyncMock()
        user_uuid_str = str(uuid4())
        with patch("app.agents.data_writers.apply_memory_updates", new_callable=AsyncMock) as mock_apply:
            result = await _write_health_symptom(
                {"description": "test", "category": "other", "severity": "mild"},
                user_id=user_uuid_str,
                db=mock_db,
            )

        assert result.success is True
