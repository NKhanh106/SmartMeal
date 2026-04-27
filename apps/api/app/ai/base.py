from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel


class AIProvider(ABC):
    """
    Interface chung cho mọi AI provider.

    GeminiProvider và GroqProvider đều phải implement các hàm này.
    Nhờ vậy service không cần biết bên dưới đang dùng Gemini hay Groq.
    """

    provider_name: str

    @abstractmethod
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        pass

    @abstractmethod
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
    ) -> tuple[BaseModel, dict[str, Any]]:
        pass

    @abstractmethod
    def analyze_image_json(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
    ) -> tuple[BaseModel, dict[str, Any]]:
        pass
