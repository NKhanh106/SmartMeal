import asyncio
import base64
import json
import threading
from typing import Any, Type

from groq import Groq
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


class GroqProvider(AIProvider):
    provider_name = "groq"
    _key_index: int = 0
    _lock: threading.Lock = threading.Lock()

    def __init__(self):
        self.api_keys = settings.GROQ_API_KEYS_LIST
        if not self.api_keys:
            raise ValueError("GROQ_API_KEYS is missing or empty in config/environment")

        self.text_model = settings.GROQ_TEXT_MODEL
        self.vision_model = settings.GROQ_VISION_MODEL

    def _get_next_client(self) -> Groq:
        """Get the next Groq client with a different API key (round-robin)."""
        with self._lock:
            key = self.api_keys[self._key_index]
            self._key_index = (self._key_index + 1) % len(self.api_keys)
        return Groq(api_key=key)

    def _get_client_for_key(self, key: str) -> Groq:
        """Create a Groq client with a specific API key."""
        return Groq(api_key=key)

    @staticmethod
    def get_shared_client() -> Groq:
        """Get a shared Groq client instance with key rotation."""
        return GroqProvider()._get_next_client()

    def _call_with_timeout(self, coro):
        """Run a blocking sync call in a thread pool with a hard timeout."""
        try:
            return asyncio.run(asyncio.wait_for(
                asyncio.to_thread(coro),
                timeout=AI_TIMEOUT_SECONDS,
            ))
        except asyncio.TimeoutError:
            raise AITimeoutError(
                f"Groq API call timed out after {AI_TIMEOUT_SECONDS}s."
            )

    def _retryable_call(self, fn, *args, **kwargs):
        """Call a function with tenacity retry and asyncio timeout."""
        try:
            return self._call_with_timeout(lambda: fn(*args, **kwargs))
        except RetryError as exc:
            last_exc = exc.last_attempt.exception()
            if isinstance(last_exc, AITimeoutError):
                raise last_exc
            raise

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
            client = self._get_next_client()
            return client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )

        wrapped = self._retry_policy()(self._call_with_timeout)(_call)
        return wrapped.choices[0].message.content or ""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
    ) -> tuple[BaseModel, dict[str, Any]]:
        schema_json = response_schema.model_json_schema()
        final_user_prompt = f"""
{user_prompt}

Bạn phải trả về JSON hợp lệ đúng theo schema sau.
Không viết giải thích ngoài JSON.

JSON Schema:
{json.dumps(schema_json, ensure_ascii=False)}
"""
        def _call():
            client = self._get_next_client()
            return client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_user_prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )

        wrapped = self._retry_policy()(self._call_with_timeout)(_call)
        text = wrapped.choices[0].message.content or "{}"
        data = json.loads(text)
        parsed = response_schema.model_validate(data)

        raw = {
            "provider": self.provider_name,
            "model": self.text_model,
            "text": text,
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
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{encoded_image}"
        schema_json = response_schema.model_json_schema()
        final_prompt = f"""
{prompt}

Bạn phải trả về JSON hợp lệ đúng schema sau.
Không viết giải thích ngoài JSON.

JSON Schema:
{json.dumps(schema_json, ensure_ascii=False)}
"""
        def _call():
            client = self._get_next_client()
            return client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": final_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )

        wrapped = self._retry_policy()(self._call_with_timeout)(_call)
        text = wrapped.choices[0].message.content or "{}"
        data = json.loads(text)
        parsed = response_schema.model_validate(data)

        raw = {
            "provider": self.provider_name,
            "model": self.vision_model,
            "text": text,
            "parsed": parsed.model_dump(mode="json"),
        }
        return parsed, raw
