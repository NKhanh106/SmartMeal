"""
SmartMeal Multi-Agent System.

Agents:
- extractor           : Extracts facts from conversations → UserMemory
- health_monitor     : Monitors health events, raises alerts
- nutrition_advisor  : Personalized nutrition advice and meal suggestions
- fitness_coach      : Workout recommendations and schedule adjustments
- web_researcher     : On-demand web research for external information
- multi_agent_orchestrator : Routes messages to specialists, synthesizes responses

Each agent inherits from BaseAgent and implements the `run()` method.
Use memory_service.py to read/write UserMemory.
"""

from app.agents.base import AgentContext, AgentResult, BaseAgent, get_async_groq_client

__all__ = [
    "AgentContext",
    "AgentResult",
    "BaseAgent",
    "get_async_groq_client",
]


# Re-export all agents for convenient imports
def get_all_agents():
    from app.agents.extractor_agent import ExtractorAgent
    from app.agents.health_monitor_agent import HealthMonitorAgent
    from app.agents.nutrition_advisor_agent import NutritionAdvisorAgent
    from app.agents.fitness_coach_agent import FitnessCoachAgent
    from app.agents.web_researcher_agent import WebResearcherAgent
    return {
        "extractor": ExtractorAgent,
        "health_monitor": HealthMonitorAgent,
        "nutrition_advisor": NutritionAdvisorAgent,
        "fitness_coach": FitnessCoachAgent,
        "web_researcher": WebResearcherAgent,
    }


# Re-export trigger helpers for use by the chatbot service
def get_trigger_helpers():
    from app.agents.web_researcher_agent import (
        needs_low_confidence_research,
        should_trigger_web_research,
    )
    return should_trigger_web_research, needs_low_confidence_research
