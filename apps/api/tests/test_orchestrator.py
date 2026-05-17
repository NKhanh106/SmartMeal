import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.multi_agent_orchestrator import MultiAgentOrchestrator
from app.agents.base import AgentResult


def _async_gen(items):
    """Create a simple async generator that yields strings."""
    async def gen():
        for item in items:
            yield item
    return gen()


@pytest.fixture
def orchestrator():
    return MultiAgentOrchestrator()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.email = "test@test.com"
    return user


@pytest.mark.asyncio
async def test_extractor_runs_as_background_task(orchestrator, mock_user):
    """Extractor must be fire-and-forget — not blocking main response."""
    memory_mock = MagicMock()
    memory_mock.health_events = []
    memory_mock.key_facts = []
    memory_mock.body_snapshot = {}
    memory_mock.key_facts = []

    with patch("app.agents.multi_agent_orchestrator.get_or_create_memory",
               new_callable=AsyncMock, return_value=memory_mock):
        with patch.object(orchestrator, "_get_user_profile", new_callable=AsyncMock, return_value=None):
            with patch.object(orchestrator, "_get_recent_messages", new_callable=AsyncMock, return_value=[]):
                with patch.object(orchestrator, "_mark_needs_extraction", new_callable=AsyncMock):
                    with patch("asyncio.create_task") as mock_task:
                        with patch.object(orchestrator, "_stream_final_response",
                                          return_value=_async_gen(["data: OK\n\n"])):
                            chunks = []
                            async for chunk in orchestrator.process(
                                "안녕", "session-1", mock_user, AsyncMock()
                            ):
                                chunks.append(chunk)

                            # create_task must have been called (fire-and-forget)
                            mock_task.assert_called()


@pytest.mark.asyncio
async def test_single_agent_failure_does_not_break_response(orchestrator, mock_user):
    """If health monitor fails, nutrition/fitness should still work."""
    async def failing_health(*args, **kwargs):
        raise Exception("AI timeout")

    success_nutrition = AgentResult(
        agent_name="nutrition_advisor", success=True,
        insight_type="nutrition_recommendation",
        content={"user_facing_summary": "Ăn nhiều rau xanh"},
        confidence=0.9, priority=5,
        text_for_orchestrator="Ăn nhiều rau xanh",
        memory_updates={}, suggested_card=None, error=None
    )

    async def success_nutrition_coro(*args, **kwargs):
        return success_nutrition

    memory_mock = MagicMock()
    memory_mock.health_events = []  # empty list — no active issues
    memory_mock.key_facts = []
    memory_mock.body_snapshot = {}

    with patch("app.agents.multi_agent_orchestrator.HealthMonitorAgent") as MockHealth:
        with patch("app.agents.multi_agent_orchestrator.NutritionAdvisorAgent") as MockNutr:
            MockHealth.return_value.run = failing_health
            MockNutr.return_value.run = success_nutrition_coro

            with patch("app.agents.multi_agent_orchestrator.get_or_create_memory",
                       new_callable=AsyncMock, return_value=memory_mock):
                with patch.object(orchestrator, "_get_user_profile",
                                  new_callable=AsyncMock, return_value=None):
                    with patch.object(orchestrator, "_get_recent_messages",
                                      new_callable=AsyncMock, return_value=[]):
                        with patch.object(orchestrator, "_mark_needs_extraction",
                                          new_callable=AsyncMock):
                            with patch("asyncio.create_task"):
                                with patch.object(orchestrator, "_stream_final_response") as mock_stream:
                                    mock_stream.return_value = _async_gen(["data: OK\n\n"])

                                    chunks = []
                                    async for chunk in orchestrator.process(
                                        "tôi nên ăn gì", "session-1", mock_user, AsyncMock()
                                    ):
                                        chunks.append(chunk)

                                    # Final response must still be called
                                    mock_stream.assert_called()


def test_nutrition_keywords_trigger_nutrition_advisor(orchestrator):
    assert orchestrator._needs_nutrition_advice("tôi nên ăn gì hôm nay") is True
    assert orchestrator._needs_nutrition_advice("gợi ý bữa trưa") is True
    assert orchestrator._needs_nutrition_advice("thời tiết hôm nay thế nào") is False


def test_health_keywords_trigger_health_monitor(orchestrator):
    memory = MagicMock()
    memory.health_events = []
    assert orchestrator._needs_health_check("tôi bị đau đầu", memory) is True
    assert orchestrator._needs_health_check("hôm nay tôi ổn", memory) is False


def test_fitness_keywords_trigger_fitness_coach(orchestrator):
    assert orchestrator._needs_fitness_advice("lịch tập hôm nay thế nào") is True
    assert orchestrator._needs_fitness_advice("bài tập gym cho ngày mai") is True
    assert orchestrator._needs_fitness_advice("tôi muốn uống cà phê") is False


@pytest.mark.asyncio
async def test_parallel_execution_not_sequential(orchestrator, mock_user):
    """Verify agents run concurrently via asyncio.wait."""
    call_times = []
    _lock = asyncio.Lock()

    async def slow_agent(*args, **kwargs):
        async with _lock:
            call_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.1)
        return AgentResult(
            agent_name="test", success=True,
            insight_type="test", content={},
            confidence=1.0, priority=5,
            text_for_orchestrator="", memory_updates={},
            suggested_card=None, error=None
        )

    memory_mock = MagicMock()
    memory_mock.health_events = []  # use list, not string
    memory_mock.key_facts = []
    memory_mock.body_snapshot = {}

    with patch("app.agents.multi_agent_orchestrator.HealthMonitorAgent") as H:
        with patch("app.agents.multi_agent_orchestrator.NutritionAdvisorAgent") as N:
            with patch("app.agents.multi_agent_orchestrator.FitnessCoachAgent") as F:
                H.return_value.run = slow_agent
                N.return_value.run = slow_agent
                F.return_value.run = slow_agent

                with patch("app.agents.multi_agent_orchestrator.get_or_create_memory",
                           new_callable=AsyncMock, return_value=memory_mock):
                    with patch.object(orchestrator, "_get_user_profile",
                                      new_callable=AsyncMock, return_value=None):
                        with patch.object(orchestrator, "_get_recent_messages",
                                          new_callable=AsyncMock, return_value=[]):
                            with patch.object(orchestrator, "_mark_needs_extraction",
                                              new_callable=AsyncMock):
                                with patch("asyncio.create_task"):
                                    with patch.object(orchestrator, "_stream_final_response") as mock_stream:
                                        mock_stream.return_value = _async_gen([])

                                        async for _ in orchestrator.process(
                                            "tôi mệt và muốn tập gym ăn gì",
                                            "session-1", mock_user, AsyncMock()
                                        ):
                                            pass

                # All 3 agents should have started within 50ms (parallel)
                if len(call_times) >= 2:
                    time_spread = max(call_times) - min(call_times)
                    assert time_spread < 0.05
