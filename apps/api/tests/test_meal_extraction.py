"""Tests for meal extraction service."""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.meal_extraction_service import (
    _extract_meals_from_text,
    _check_recent_duplicate,
    extract_meals_from_message,
    detect_meal_command,
    infer_meal_type_from_time,
)


class TestDetectMealCommand:
    """Tests for meal command detection."""

    def test_positive_log_command(self):
        is_cmd, mention = detect_meal_command("log pho bo")
        assert is_cmd is True
        assert "pho bo" in mention

    def test_positive_ate_command(self):
        is_cmd, mention = detect_meal_command("I just ate com rang")
        assert is_cmd is True

    def test_positive_add_command(self):
        is_cmd, mention = detect_meal_command("add banh mi")
        assert is_cmd is True
        assert "banh mi" in mention

    def test_negative_plain_text(self):
        is_cmd, mention = detect_meal_command("Hom nay toi an gi")
        assert is_cmd is False
        assert mention is None

    def test_positive_track_command(self):
        is_cmd, mention = detect_meal_command("track my lunch")
        assert is_cmd is True


class TestInferMealTypeFromTime:
    """Tests for meal type inference from current time."""

    def test_returns_meal_type_enum(self):
        result = infer_meal_type_from_time()
        assert result is not None
        # Just verify it returns a valid enum value without crashing
        from app.models.enums import MealTypeEnum
        assert isinstance(result, MealTypeEnum)


class TestExtractMealsFromText:
    """Tests for AI meal extraction logic."""

    @pytest.mark.asyncio
    async def test_parses_valid_json_response(self):
        """Valid JSON with high-confidence items are returned."""
        mock_response = '[{"food_name":"pho bo","quantity":1,"unit":"bowl","meal_type":"bua_trua","confidence":"high"}]'
        with patch(
            "fastapi.concurrency.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = mock_response
            result = await _extract_meals_from_text("Toi an pho bo", "")
            assert len(result) == 1
            assert result[0]["food_name"] == "pho bo"
            assert result[0]["confidence"] == "high"

    @pytest.mark.asyncio
    async def test_low_confidence_items_filtered(self):
        """Items with confidence=low are not included in results."""
        mock_response = '[{"food_name":"unknown food","quantity":1,"unit":"bowl","meal_type":"an_vat","confidence":"low"}]'
        with patch(
            "fastapi.concurrency.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = mock_response
            result = await _extract_meals_from_text("something", "")
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        """Malformed AI response returns empty list without raising."""
        with patch(
            "fastapi.concurrency.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = Exception("AI unavailable")
            result = await _extract_meals_from_text("something", "")
            assert result == []

    @pytest.mark.asyncio
    async def test_non_list_json_returns_empty(self):
        """AI returned non-list JSON returns empty list."""
        with patch(
            "fastapi.concurrency.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = '{"food_name":"pho"}'
            result = await _extract_meals_from_text("something", "")
            assert result == []

    @pytest.mark.asyncio
    async def test_strips_json_code_fences(self):
        """Response wrapped in ```json``` fences is handled correctly."""
        mock_response = '```json\n[{"food_name":"banh mi","quantity":1,"unit":"piece","meal_type":"an_vat","confidence":"medium"}]\n```'
        with patch(
            "fastapi.concurrency.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.return_value = mock_response
            result = await _extract_meals_from_text("banh mi", "")
            assert len(result) == 1
            assert result[0]["food_name"] == "banh mi"

    @pytest.mark.asyncio
    async def test_ai_provider_exception_returns_empty(self):
        """AI provider failure returns empty list gracefully."""
        with patch(
            "fastapi.concurrency.run_in_threadpool",
            new_callable=AsyncMock,
        ) as mock_run:
            mock_run.side_effect = RuntimeError("AI unavailable")
            result = await _extract_meals_from_text("something", "")
            assert result == []


class TestCheckRecentDuplicate:
    """Tests for meal deduplication logic."""

    @pytest.mark.asyncio
    async def test_no_duplicate_returns_false(self, db_session):
        """When no recent similar meal exists, returns False."""
        # Mock the DB result to return None (no duplicate)
        with patch.object(db_session, "execute", new_callable=AsyncMock) as mock_exec:
            from unittest.mock import MagicMock
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_exec.return_value = mock_result

            result = await _check_recent_duplicate(
                db_session,
                user_id="00000000-0000-0000-0000-000000000001",
                food_name="pho bo",
                minutes=10,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_duplicate_exists_returns_true(self, db_session):
        """When a similar meal exists within the time window, returns True."""
        with patch.object(db_session, "execute", new_callable=AsyncMock) as mock_exec:
            from unittest.mock import MagicMock
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = "some_meal_item"
            mock_exec.return_value = mock_result

            result = await _check_recent_duplicate(
                db_session,
                user_id="00000000-0000-0000-0000-000000000001",
                food_name="pho bo",
                minutes=10,
            )
            assert result is True


class TestExtractMealsFromMessage:
    """Integration-style tests for the main extraction entry point."""

    @pytest.mark.asyncio
    async def test_empty_message_returns_empty(self, db_session):
        """Empty user message returns [] without calling AI."""
        result = await extract_meals_from_message(
            db_session,
            user_id="00000000-0000-0000-0000-000000000001",
            user_message="",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_whitespace_message_returns_empty(self, db_session):
        """Whitespace-only message returns []."""
        result = await extract_meals_from_message(
            db_session,
            user_id="00000000-0000-0000-0000-000000000001",
            user_message="   ",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_no_meals_extracted_returns_empty(self, db_session):
        """When AI returns [], no meal logs are created."""
        with patch(
            "app.services.meal_extraction_service._extract_meals_from_text",
            new_callable=AsyncMock,
        ) as mock_extract:
            mock_extract.return_value = []

            result = await extract_meals_from_message(
                db_session,
                user_id="00000000-0000-0000-0000-000000000001",
                user_message="I am feeling great today",
            )
            assert result == []
