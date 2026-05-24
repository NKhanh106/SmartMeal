"""Tests for health context builder and dietary rules."""
import pytest

from app.chatbot.context_builder import build_health_context, get_dietary_rules
from app.core.constants import CONDITION_RULES


class MockProfile:
    """Minimal mock of UserProfile with just the fields needed for testing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ─── get_dietary_rules tests ─────────────────────────────────────────────────────

class TestGetDietaryRules:
    def test_none_conditions_returns_empty(self):
        assert get_dietary_rules(None) == []
        assert get_dietary_rules([]) == []

    def test_resolved_condition_excluded(self):
        conditions = [
            {"condition": "type2_diabetes", "severity": "resolved"},
        ]
        assert get_dietary_rules(conditions) == []

    def test_managed_condition_included(self):
        conditions = [
            {"condition": "type2_diabetes", "severity": "managed"},
        ]
        rules = get_dietary_rules(conditions)
        assert "limit_simple_carbs" in rules
        assert "prioritize_low_gi" in rules

    def test_unmanaged_condition_included(self):
        conditions = [
            {"condition": "hypertension", "severity": "unmanaged"},
        ]
        rules = get_dietary_rules(conditions)
        assert "limit_sodium_2g_day" in rules
        assert "dash_diet" in rules

    def test_multiple_conditions_combined(self):
        conditions = [
            {"condition": "type2_diabetes", "severity": "managed"},
            {"condition": "gout", "severity": "managed"},
        ]
        rules = get_dietary_rules(conditions)
        assert "limit_simple_carbs" in rules
        assert "limit_purine" in rules

    def test_no_match_condition_returns_empty(self):
        conditions = [{"condition": "none", "severity": "managed"}]
        assert get_dietary_rules(conditions) == []

    def test_unknown_condition_id_ignored(self):
        conditions = [{"condition": "fake_unknown_condition", "severity": "managed"}]
        assert get_dietary_rules(conditions) == []


# ─── build_health_context tests ───────────────────────────────────────────────

class TestBuildHealthContext:
    def test_no_profile_returns_empty(self):
        assert build_health_context(None) == ""
        assert build_health_context(MockProfile()) == ""

    def test_usage_goal_included(self):
        profile = MockProfile(
            usage_goal=MockValue("weight_loss"),
        )
        ctx = build_health_context(profile)
        assert "weight_loss" in ctx

    def test_health_conditions_included(self):
        profile = MockProfile(
            health_conditions=[
                {"condition": "type2_diabetes", "severity": "managed"},
            ],
        )
        ctx = build_health_context(profile)
        assert "MEDICAL CONDITIONS" in ctx
        assert "type2_diabetes" in ctx

    def test_resolved_condition_not_included(self):
        profile = MockProfile(
            health_conditions=[
                {"condition": "type2_diabetes", "severity": "resolved"},
            ],
        )
        ctx = build_health_context(profile)
        assert "MEDICAL CONDITIONS" not in ctx

    def test_allergies_included(self):
        profile = MockProfile(
            allergies=[
                {"allergen": "peanuts", "severity": "severe"},
                {"allergen": "milk", "severity": "moderate"},
            ],
        )
        ctx = build_health_context(profile)
        assert "ALLERGIES" in ctx
        assert "peanuts" in ctx
        assert "milk" in ctx

    def test_dietary_restrictions_included(self):
        profile = MockProfile(
            dietary_restrictions=["vegetarian", "halal"],
        )
        ctx = build_health_context(profile)
        assert "Dietary restrictions" in ctx
        assert "vegetarian" in ctx
        assert "halal" in ctx

    def test_medications_included(self):
        profile = MockProfile(
            medications=[
                {"name": "Metformin", "frequency": "daily"},
            ],
        )
        ctx = build_health_context(profile)
        assert "Metformin" in ctx
        assert "food-drug interactions" in ctx

    def test_taste_preferences_dominant_included(self):
        profile = MockProfile(
            taste_preferences={"spicy": 5, "sweet": 1, "salty": 3},
        )
        ctx = build_health_context(profile)
        assert "spicy" in ctx

    def test_taste_preferences_avoided_included(self):
        profile = MockProfile(
            taste_preferences={"spicy": 5, "sweet": 1, "salty": 3},
        )
        ctx = build_health_context(profile)
        assert "sweet" in ctx

    def test_disliked_foods_included(self):
        profile = MockProfile(
            disliked_foods=["liver", "bitter_melon"],
        )
        ctx = build_health_context(profile)
        assert "Dislikes" in ctx
        assert "liver" in ctx
        assert "bitter_melon" in ctx

    def test_cuisine_preferences_included(self):
        profile = MockProfile(
            cuisine_preferences=["vietnamese", "japanese"],
        )
        ctx = build_health_context(profile)
        assert "Preferred cuisines" in ctx
        assert "vietnamese" in ctx

    def test_sleep_info_included(self):
        profile = MockProfile(
            sleep_duration_hours=6.5,
            sleep_quality=MockValue("poor"),
        )
        ctx = build_health_context(profile)
        assert "6.5" in ctx
        assert "poor" in ctx

    def test_high_stress_triggers_note(self):
        profile = MockProfile(
            stress_level=8,
        )
        ctx = build_health_context(profile)
        assert "High stress level" in ctx
        assert "magnesium" in ctx.lower() or "B-vitamins" in ctx

    def test_normal_stress_no_note(self):
        profile = MockProfile(
            stress_level=4,
        )
        ctx = build_health_context(profile)
        assert "High stress level" not in ctx

    def test_disclaimer_when_conditions_present(self):
        profile = MockProfile(
            health_conditions=[{"condition": "hypertension", "severity": "managed"}],
        )
        ctx = build_health_context(profile)
        assert " DISCLAIMER" in ctx
        assert "bác sĩ" in ctx.lower()

    def test_no_disclaimer_without_conditions(self):
        profile = MockProfile(
            usage_goal=MockValue("weight_loss"),
            allergies=[],
        )
        ctx = build_health_context(profile)
        assert " DISCLAIMER" not in ctx

    def test_dietary_constraints_included_when_conditions_active(self):
        profile = MockProfile(
            health_conditions=[{"condition": "type2_diabetes", "severity": "managed"}],
        )
        ctx = build_health_context(profile)
        assert "DIETARY CONSTRAINTS" in ctx
        assert "Limit Simple Carbs" in ctx


class MockValue:
    """Helper to simulate SQLAlchemy enum .value access."""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"MockValue({self.value!r})"
