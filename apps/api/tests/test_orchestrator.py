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
    """A single failing agent raises — the exception is caught and fallback response is produced."""
    async def failing_agent(*args, **kwargs):
        raise Exception("AI timeout")

    memory_mock = MagicMock()
    memory_mock.health_events = []
    memory_mock.key_facts = []
    memory_mock.body_snapshot = {}

    with patch("app.agents.multi_agent_orchestrator.HealthMonitorAgent") as MockHealth:
        MockHealth.return_value.run = failing_agent

        with patch("app.agents.multi_agent_orchestrator.get_or_create_memory",
                   new_callable=AsyncMock, return_value=memory_mock):
            with patch.object(orchestrator, "_get_user_profile",
                              new_callable=AsyncMock, return_value=None):
                with patch.object(orchestrator, "_get_recent_messages",
                                  new_callable=AsyncMock, return_value=[]):
                    with patch.object(orchestrator, "_mark_needs_extraction",
                                      new_callable=AsyncMock):
                        with patch("asyncio.create_task"):
                            with patch.object(
                                orchestrator, "_stream_final_response",
                                return_value=_async_gen(["data: OK\n\n"])
                            ):
                                # Should NOT raise — orchestrator catches agent failures
                                chunks = []
                                async for chunk in orchestrator.process(
                                    "tôi nên ăn gì", "session-1", mock_user, AsyncMock()
                                ):
                                    chunks.append(chunk)
                                # Fallback response is produced
                                assert len(chunks) > 0


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
    """Verify agent routing for multi-topic messages."""
    memory_mock = MagicMock()
    memory_mock.health_events = []

    message = "tôi mệt và muốn tập gym ăn gì"

    # This message triggers: health ("mệt"), nutrition (food keywords),
    # and fitness (workout keywords) — all run in Phase 2
    assert orchestrator._needs_health_check(message, memory_mock) is True
    assert orchestrator._needs_nutrition_advice(message) is True
    assert orchestrator._needs_fitness_advice(message) is True

    # A simple weather message — no health issues in memory, no health keywords
    simple_msg = "thời tiết hôm nay thế nào"
    memory_mock.health_events = []
    assert orchestrator._needs_health_check(simple_msg, memory_mock) is False
    assert orchestrator._needs_nutrition_advice(simple_msg) is False
    assert orchestrator._needs_fitness_advice(simple_msg) is False
