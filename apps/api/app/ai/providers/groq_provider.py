import base64
import json
from typing import Any, Type

from groq import Groq
from pydantic import BaseModel

from app.ai.base import AIProvider
from app.core.config import settings


class GroqProvider(AIProvider):
    provider_name = "groq"

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is missing in config/environment")

        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.text_model = settings.GROQ_TEXT_MODEL
        self.vision_model = settings.GROQ_VISION_MODEL

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.text_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=temperature,
        )

        return response.choices[0].message.content or ""

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
    ) -> tuple[BaseModel, dict[str, Any]]:
        """
        Bản ổn định cho MVP:
        - Dùng JSON Object Mode.
        - Sau đó validate bằng Pydantic.
        """

        schema_json = response_schema.model_json_schema()

        final_user_prompt = f"""
{user_prompt}

Bạn phải trả về JSON hợp lệ đúng theo schema sau.
Không viết giải thích ngoài JSON.

JSON Schema:
{json.dumps(schema_json, ensure_ascii=False)}
"""

        response = self.client.chat.completions.create(
            model=self.text_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": final_user_prompt,
                },
            ],
            temperature=temperature,
            response_format={
                "type": "json_object"
            },
        )

        text = response.choices[0].message.content or "{}"
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
        """
        Groq vision:
        - Gửi ảnh dưới dạng base64 data URL.
        - Dùng vision model.
        - Yêu cầu JSON và validate bằng Pydantic.
        """

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

        response = self.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": final_prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url,
                            },
                        },
                    ],
                }
            ],
            temperature=temperature,
            response_format={
                "type": "json_object"
            },
        )

        text = response.choices[0].message.content or "{}"
        data = json.loads(text)
        parsed = response_schema.model_validate(data)

        raw = {
            "provider": self.provider_name,
            "model": self.vision_model,
            "text": text,
            "parsed": parsed.model_dump(mode="json"),
        }

        return parsed, raw
