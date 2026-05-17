# Thư mục `ai/` — AI Provider Integration

## Mục đích

Chứa **abstraction layer** cho các AI providers (Gemini, Groq). Tách biệt việc gọi AI provider cụ thể khỏi business logic — nếu cần đổi provider, chỉ cần thay đổi trong thư mục này.

## Cấu trúc

```
ai/
├── base.py              # Abstract AIProvider class — interface chung
├── factory.py           # Factory pattern — chọn provider theo config
├── orchestrator.py      # AI call orchestration (optional)
├── ai_logger.py         # Decorator: log AI calls
├── circuit_breaker.py   # Circuit breaker pattern
├── providers/           # Implementations cụ thể
│   ├── gemini_provider.py    # Google Gemini (vision: meal recognition)
│   └── groq_provider.py      # Groq (text: chatbot, daily planner)
└── prompts/            # System prompts cho từng use case
    └── daily_planner_prompt.py
```

## Abstract Interface (`base.py`)

```python
class AIProvider(ABC):
    provider_name: str

    @abstractmethod
    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float) -> str:
        pass

    @abstractmethod
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel],
        temperature: float,
    ) -> tuple[BaseModel, dict]:
        pass

    @abstractmethod
    def analyze_image_json(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        response_schema: Type[BaseModel],
        temperature: float,
    ) -> tuple[BaseModel, dict]:
        pass
```

## Factory Pattern (`factory.py`)

Factory khởi tạo và cache provider:

```python
from app.ai.factory import get_ai_provider

# Chọn provider theo config
provider = get_ai_provider("gemini")  # cho meal recognition
provider = get_ai_provider("groq")     # cho chatbot, planner

# Gọi AI
result = provider.analyze_image_json(...)
```

Provider được chọn dựa trên các biến config:
- `AI_MEAL_PROVIDER`: provider cho nhận diện món ăn từ ảnh
- `AI_CHAT_PROVIDER`: provider cho chatbot
- `AI_PLANNER_PROVIDER`: provider cho daily planner

## Providers

### Gemini Provider (`providers/gemini_provider.py`)

- **Use case**: Nhận diện đồ ăn từ ảnh (multimodal/vision model)
- **Model**: `gemini-2.5-flash` (configurable qua `GEMINI_MODEL`)
- **API**: Google Generative AI SDK
- **Input**: Base64-encoded image + text prompt
- **Output**: Structured JSON response

### Groq Provider (`providers/groq_provider.py`)

- **Use case**: Text generation nhanh cho chatbot và daily planner
- **Model**: `llama-3.3-70b-versatile` (configurable qua `GROQ_TEXT_MODEL`)
- **API**: Groq API (fast inference, low latency)
- **Input**: Text prompt
- **Output**: Text response hoặc structured JSON
- **Ưu điểm**: Latency cực thấp (~100-500ms), chi phí rẻ

## AI Logger (`ai_logger.py`)

Decorator log mọi lần gọi AI:

```python
@log_ai_call(feature="food_recognition")
async def analyze_meal_image(...):
    # Tự động ghi log: provider, model, latency, prompt_version, status
```

## Circuit Breaker (`circuit_breaker.py`)

Pattern ngăn chặn cascading failures khi AI provider down:

```python
# Nếu AI provider fail liên tục → circuit breaker mở
# → không gọi AI nữa trong thời gian cooldown
# → return fallback response
```

## Prompts (`prompts/`)

System prompts cho từng use case:

### Daily Planner Prompt (`prompts/daily_planner_prompt.py`)

Hướng dẫn AI tạo gợi ý bữa ăn + workout hàng ngày:
- Cân bằng macro theo user profile
- Tôn trọng allergies và disliked_foods
- Đa dạng món ăn
- Tạo workout plan phù hợp với difficulty

## Bảo mật

- **API keys** chỉ nằm trong environment variables
- **KHÔNG hardcode** keys trong code
- **KHÔNG log** raw API responses chứa sensitive data
- Rate limiting trên endpoint AI để tránh abuse

## Cách thêm provider mới

1. Tạo file `ai/providers/new_provider.py`
2. Implement `AIProvider` abstract class
3. Thêm vào factory: `if provider_name == "new": return NewProvider()`
4. Cập nhật biến môi trường để chọn provider
