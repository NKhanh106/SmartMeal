import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.health_monitor_agent import HealthMonitorAgent
from app.agents.base import AgentContext


def _make_mock_context(**overrides):
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.id = 1
    ctx.session_id = "test-session"
    ctx.run_id = "test-run"
    ctx.profile = None
    ctx.memory = MagicMock()
    ctx.memory.health_events = []
    ctx.memory.body_snapshot = {}
    ctx.memory.key_facts = []
    for k, v in overrides.items():
        setattr(ctx, k, v)
    return ctx


def _make_mock_run():
    run = MagicMock()
    run.run_id = "test-run-uuid"
    return run


async def _noop(*args, **kwargs):
    pass


@pytest.mark.asyncio
async def test_urgent_keyword_triggers_immediate_alert_no_ai_call():
    """Urgent keywords must return priority=1 WITHOUT calling AI."""
    mock_context = _make_mock_context(current_message="Tôi bị đau ngực và khó thở")

    agent = HealthMonitorAgent()
    with patch.object(agent, "_call_ai") as mock_ai:
        with patch.object(agent, "_log_start", return_value=_make_mock_run()):
            with patch.object(agent, "_log_complete", side_effect=_noop):
                result = await agent.run(mock_context, AsyncMock())

    mock_ai.assert_not_called()
    assert result.priority == 1
    assert result.success is True
    alerts = result.content.get("alerts", [])
    assert any("URGENT" in str(a) or "nghiêm trọng" in str(a) for a in alerts)


@pytest.mark.asyncio
async def test_digestive_issue_sets_fitness_restriction():
    """Active digestive illness should restrict high-intensity exercise."""
    mock_context = _make_mock_context(current_message="Tôi bị tiêu chảy từ sáng")
    mock_context.memory.health_events = [
        {"event_id": "1", "type": "symptom", "category": "digestive",
         "description": "tiêu chảy", "severity": "moderate", "resolved": False}
    ]
    mock_context.memory.body_snapshot = {}

    agent = HealthMonitorAgent()
    agent._last_usage = {}

    # _call_ai with response_format="json" returns a dict (already parsed)
    ai_result = {
        "current_status": {"overall": "monitor"},
        "active_issues": [{
            "issue": "Tiêu chảy",
            "since": "today",
            "severity": "moderate",
            "recommendation": "Nghỉ ngơi, uống nhiều nước",
            "dietary_restriction": ["high_fat", "spicy"],
            "fitness_restriction": ["high_intensity", "heavy_lifting"],
            "see_doctor_if": "Kéo dài hơn 2 ngày"
        }],
        "nutritional_needs": {"increase": ["electrolytes"], "decrease": [], "avoid": ["dairy"]},
        "fitness_clearance": {
            "cleared_for": ["light_walk"],
            "avoid": ["high_intensity", "heavy_lifting"],
            "reason": "Đang bị tiêu chảy"
        },
        "alerts": [],
        "user_facing_note": "Bạn nên nghỉ ngơi hôm nay."
    }

    async def mock_call_ai(*args, **kwargs):
        return ai_result

    with patch.object(agent, "_call_ai", side_effect=mock_call_ai):
        with patch.object(agent, "_log_start", return_value=_make_mock_run()):
            with patch.object(agent, "_log_complete", side_effect=_noop):
                with patch.object(agent, "_update_memory", side_effect=_noop):
                    result = await agent.run(mock_context, AsyncMock())

    clearance = result.content.get("fitness_clearance", {})
    assert "high_intensity" in clearance.get("avoid", [])


@pytest.mark.asyncio
async def test_healthy_user_returns_good_status():
    """User with no issues should get overall=good."""
    mock_context = _make_mock_context(current_message="Hôm nay tôi cảm thấy rất ổn!")

    agent = HealthMonitorAgent()
    agent._last_usage = {}

    ai_result = {
        "current_status": {"overall": "good", "energy": "normal",
            "digestion": "normal", "musculoskeletal": "normal", "metabolic": "normal"},
        "active_issues": [],
        "nutritional_needs": {"increase": [], "decrease": [], "avoid": []},
        "fitness_clearance": {"cleared_for": ["normal_activity"], "avoid": [], "reason": "Không có hạn chế"},
        "alerts": [],
        "user_facing_note": ""
    }

    async def mock_call_ai(*args, **kwargs):
        return ai_result

    with patch.object(agent, "_call_ai", side_effect=mock_call_ai):
        with patch.object(agent, "_log_start", return_value=_make_mock_run()):
            with patch.object(agent, "_log_complete", side_effect=_noop):
                with patch.object(agent, "_update_memory", side_effect=_noop):
                    result = await agent.run(mock_context, AsyncMock())

    assert result.content["current_status"]["overall"] == "good"
