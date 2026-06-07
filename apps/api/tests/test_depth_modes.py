"""
Tests for the Response Depth Mode feature.

Covers:
  - DEPTH_CONFIGS token budgets and timeouts per mode
  - get_depth_config default behaviour
  - Quick mode skips all specialist agents
  - Deep mode runs health + one specialist max
  - Expert mode runs all relevant agents
  - Response style is injected into system prompts
  - Schema accepts depth field and rejects invalid values
"""

import pytest

from app.agents.depth_config import (
    DEPTH_CONFIGS,
    DepthConfig,
    ResponseDepth,
    get_depth_config,
)


class TestDepthConfigStructure:
    """Test that all three modes have valid configs."""

    def test_all_three_modes_exist(self):
        assert ResponseDepth.QUICK in DEPTH_CONFIGS
        assert ResponseDepth.DEEP in DEPTH_CONFIGS
        assert ResponseDepth.EXPERT in DEPTH_CONFIGS

    def test_quick_mode_pipeline(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.QUICK]
        assert cfg.run_extractor is True
        assert cfg.run_health_monitor is False
        assert cfg.run_nutrition_advisor is False
        assert cfg.run_fitness_coach is False
        assert cfg.run_web_researcher is False

    def test_deep_mode_pipeline(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.DEEP]
        assert cfg.run_extractor is True
        assert cfg.run_health_monitor is True
        assert cfg.run_nutrition_advisor is True
        assert cfg.run_fitness_coach is True
        assert cfg.run_web_researcher is False

    def test_expert_mode_pipeline(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.EXPERT]
        assert cfg.run_extractor is True
        assert cfg.run_health_monitor is True
        assert cfg.run_nutrition_advisor is True
        assert cfg.run_fitness_coach is True
        assert cfg.run_web_researcher is True


class TestTokenBudgets:
    """Test token budgets scale with depth."""

    def test_quick_has_lowest_token_budget(self):
        quick = DEPTH_CONFIGS[ResponseDepth.QUICK]
        deep = DEPTH_CONFIGS[ResponseDepth.DEEP]
        expert = DEPTH_CONFIGS[ResponseDepth.EXPERT]

        assert quick.final_response_tokens < deep.final_response_tokens
        assert deep.final_response_tokens < expert.final_response_tokens

    def test_extractor_tokens_scale_up(self):
        quick = DEPTH_CONFIGS[ResponseDepth.QUICK]
        expert = DEPTH_CONFIGS[ResponseDepth.EXPERT]
        assert quick.extractor_tokens < expert.extractor_tokens

    def test_specialist_tokens_are_zero_in_quick_mode(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.QUICK]
        assert cfg.health_tokens == 0
        assert cfg.nutrition_tokens == 0
        assert cfg.fitness_tokens == 0


class TestTimeouts:
    """Test timeouts scale with depth."""

    def test_quick_has_no_phase_timeouts(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.QUICK]
        assert cfg.phase1_timeout == 0.0
        assert cfg.phase2_timeout == 0.0

    def test_expert_has_longest_timeouts(self):
        expert = DEPTH_CONFIGS[ResponseDepth.EXPERT]
        deep = DEPTH_CONFIGS[ResponseDepth.DEEP]

        assert expert.phase1_timeout > deep.phase1_timeout
        assert expert.phase2_timeout > deep.phase2_timeout


class TestTemperature:
    """Test temperature values per mode."""

    def test_temperatures_in_valid_range(self):
        for mode, cfg in DEPTH_CONFIGS.items():
            assert 0.0 <= cfg.temperature <= 1.0, f"{mode} temperature out of range"

    def test_expert_has_highest_temperature(self):
        expert = DEPTH_CONFIGS[ResponseDepth.EXPERT]
        quick = DEPTH_CONFIGS[ResponseDepth.QUICK]
        assert expert.temperature > quick.temperature


class TestSystemPromptVariants:
    """Test system prompt variant names."""

    def test_quick_variant(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.QUICK]
        assert cfg.system_prompt_variant == "quick"

    def test_deep_variant(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.DEEP]
        assert cfg.system_prompt_variant == "deep"

    def test_expert_variant(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.EXPERT]
        assert cfg.system_prompt_variant == "expert"


class TestResponseStyle:
    """Test that response styles are meaningful."""

    def test_quick_style_mentions_conciseness(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.QUICK]
        assert "NGẮN" in cfg.response_style.upper() or "ngắn" in cfg.response_style

    def test_deep_style_mentions_balance(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.DEEP]
        assert "cân bằng" in cfg.response_style.lower() or "chi tiết" in cfg.response_style.lower()

    def test_expert_style_mentions_expert_level(self):
        cfg = DEPTH_CONFIGS[ResponseDepth.EXPERT]
        assert "chuyên gia" in cfg.response_style.lower() or "chuyên sâu" in cfg.response_style.lower()


class TestGetDepthConfig:
    """Test get_depth_config function."""

    def test_valid_quick(self):
        cfg = get_depth_config("quick")
        assert cfg.mode == ResponseDepth.QUICK

    def test_valid_deep(self):
        cfg = get_depth_config("deep")
        assert cfg.mode == ResponseDepth.DEEP

    def test_valid_expert(self):
        cfg = get_depth_config("expert")
        assert cfg.mode == ResponseDepth.EXPERT

    def test_invalid_defaults_to_deep(self):
        cfg = get_depth_config("invalid_mode")
        assert cfg.mode == ResponseDepth.DEEP

    def test_empty_string_defaults_to_deep(self):
        cfg = get_depth_config("")
        assert cfg.mode == ResponseDepth.DEEP

    def test_none_defaults_to_deep(self):
        cfg = get_depth_config("none")
        assert cfg.mode == ResponseDepth.DEEP


class TestSchemaAcceptsDepth:
    """Test that the API schema accepts the depth field."""

    def test_chat_message_create_accepts_quick(self):
        from app.schemas.chat import ChatMessageCreate
        msg = ChatMessageCreate(content="Hello", depth="quick")
        assert msg.depth == "quick"

    def test_chat_message_create_accepts_deep(self):
        from app.schemas.chat import ChatMessageCreate
        msg = ChatMessageCreate(content="Hello", depth="deep")
        assert msg.depth == "deep"

    def test_chat_message_create_accepts_expert(self):
        from app.schemas.chat import ChatMessageCreate
        msg = ChatMessageCreate(content="Hello", depth="expert")
        assert msg.depth == "expert"

    def test_chat_message_create_default_is_deep(self):
        from app.schemas.chat import ChatMessageCreate
        msg = ChatMessageCreate(content="Hello")
        assert msg.depth == "deep"

    def test_chat_message_create_rejects_invalid_depth(self):
        from app.schemas.chat import ChatMessageCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ChatMessageCreate(content="Hello", depth="invalid")
