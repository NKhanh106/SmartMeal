from app.ai.base import AIProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.groq_provider import GroqProvider

_provider_cache: dict[str, AIProvider] = {}

def get_ai_provider(provider_name: str) -> AIProvider:
    """
    Factory lấy AI provider theo tên.
    """
    provider_name = provider_name.lower().strip()

    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    if provider_name == "gemini":
        provider = GeminiProvider()
    elif provider_name == "groq":
        provider = GroqProvider()
    else:
        raise ValueError(
            f"Unsupported AI provider: {provider_name}. "
            "Supported providers: gemini, groq"
        )

    _provider_cache[provider_name] = provider

    return provider
