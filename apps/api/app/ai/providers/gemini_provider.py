import asyncio
import json
from typing import Any, Type

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    RetryError,
)

from app.ai.base import AIProvider
from app.core.config import settings

AI_TIMEOUT_SECONDS = 30.0


class AITimeoutError(Exception):
    """Raised when an AI API call exceeds the timeout threshold."""
    pass


class GeminiProvider(AIProvider):
    provider_name = "gemini"

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing in config/environment")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL

    def _call_with_timeout(self, coro):
        """Run a blocking sync call in a thread pool with a hard timeout."""
        try:
            return asyncio.run(asyncio.wait_for(
                asyncio.to_thread(coro),
                timeout=AI_TIMEOUT_SECONDS,
            ))
        except asyncio.TimeoutError:
            raise AITimeoutError(
                f"Gemini API call timed out after {AI_TIMEOUT_SECONDS}s."
            )

    @staticmethod
    def _retry_policy():
        return retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        def _call():
            return self.client.models.generate_content(
                model=self.model,
                contents=[
                    system_prompt,
                    user_prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                ),
            )

        wrapped = self._retry_policy()(self._call_with_timeout)(_call)
        return wrapped.text or ""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
    ) -> tuple[BaseModel, dict[str, Any]]:
        def _call():
            return self.client.models.generate_content(
                model=self.model,
                contents=[
                    system_prompt,
                    user_prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )

        wrapped = self._retry_policy()(self._call_with_timeout)(_call)
        if getattr(wrapped, "parsed", None) is not None:
            parsed = wrapped.parsed
        else:
            parsed = response_schema.model_validate(json.loads(wrapped.text))

        raw = {
            "provider": self.provider_name,
            "model": self.model,
            "text": wrapped.text,
            "parsed": parsed.model_dump(mode="json"),
        }
        return parsed, raw

    def analyze_image_json(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
    ) -> tuple[BaseModel, dict[str, Any]]:
        def _call():
            return self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type,
                    ),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )

        wrapped = self._retry_policy()(self._call_with_timeout)(_call)
        if getattr(wrapped, "parsed", None) is not None:
            parsed = wrapped.parsed
        else:
            parsed = response_schema.model_validate(json.loads(wrapped.text))

        raw = {
            "provider": self.provider_name,
            "model": self.model,
            "text": wrapped.text,
            "parsed": parsed.model_dump(mode="json"),
        }
        return parsed, raw
