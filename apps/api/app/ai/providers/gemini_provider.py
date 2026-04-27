import json
from typing import Any, Type

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.ai.base import AIProvider
from app.core.config import settings


class GeminiProvider(AIProvider):
    provider_name = "gemini"

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing in config/environment")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                system_prompt,
                user_prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=temperature,
            ),
        )

        return response.text or ""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
    ) -> tuple[BaseModel, dict[str, Any]]:
        response = self.client.models.generate_content(
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

        if getattr(response, "parsed", None) is not None:
            parsed = response.parsed
        else:
            parsed = response_schema.model_validate(json.loads(response.text))

        raw = {
            "provider": self.provider_name,
            "model": self.model,
            "text": response.text,
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
        response = self.client.models.generate_content(
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

        if getattr(response, "parsed", None) is not None:
            parsed = response.parsed
        else:
            parsed = response_schema.model_validate(json.loads(response.text))

        raw = {
            "provider": self.provider_name,
            "model": self.model,
            "text": response.text,
            "parsed": parsed.model_dump(mode="json"),
        }

        return parsed, raw
