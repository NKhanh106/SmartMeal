"""
Backwards-compatible re-exports from base_agent.py.

All existing import lines like:
    from app.agents.base import AgentContext, AgentResult, BaseAgent
continue to work unchanged.

New code should prefer:
    from app.agents.base_agent import AgentContext, AgentResult, BaseAgent
"""

from app.agents.base_agent import (
    AI_TIMEOUT_SECONDS,
    AgentContext,
    AgentResult,
    BaseAgent,
    _get_groq_client,
    get_async_groq_client,
)
