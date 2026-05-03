# `ai/` — AI Provider Integrations

Thư mục chứa abstraction layer cho các AI providers (Gemini, Groq).

## Mục đích

Tách biệt việc gọi AI provider cụ thể khỏi business logic. Nếu cần đổi provider (VD: từ Gemini sang GPT), chỉ cần thay đổi trong thư mục này.

## Cấu trúc

```
ai/
├── base.py           # Abstract base class — interface chung
├── factory.py        # Factory pattern — chọn provider theo config
├── providers/        # Implementations cụ thể
│   ├── gemini_provider.py   # Gemini Vision (meal recognition)
│   └── groq_provider.py      # Groq (text generation, fast)
└── prompts/          # System prompts cho từng use case
    └── daily_planner_prompt.py
```

## Các provider

### Gemini Provider (`gemini_provider.py`)
- **Use case**: Nhận diện đồ ăn từ ảnh (vision model)
- **Model**: `gemini-2.5-flash` (configurable qua `GEMINI_MODEL`)
- **Input**: Base64 image + text prompt
- **Output**: Structured JSON response

### Groq Provider (`groq_provider.py`)
- **Use case**: Text generation nhanh (chatbot, daily planner)
- **Model**: `llama-3.3-70b-versatile` (configurable)
- **Input**: Text prompt
- **Output**: Text response
- **Ưu điểm**: Latency thấp, chi phí rẻ

## Factory Pattern

```python
from app.ai.factory import AIProviderFactory

provider = AIProviderFactory.get_provider("gemini")
response = provider.generate(prompt, image_base64=...)
```

Provider được chọn dựa trên `AI_MEAL_PROVIDER` (cho meal) và `AI_PLANNER_PROVIDER` (cho planner) trong config.

## Prompts

System prompts được tách riêng trong `prompts/`:
- **Daily planner prompt**: Hướng dẫn AI tạo gợi ý bữa ăn + workout
- Prompts nên được version control và test riêng

## Bảo mật

- **API keys** chỉ nằm trong environment variables
- **KHÔNG hardcode** keys trong code
- **KHÔNG log** raw API responses chứa sensitive data
