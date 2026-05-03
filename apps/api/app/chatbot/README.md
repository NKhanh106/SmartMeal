# Thư mục chatbot/ - AI Chatbot System

## Mục đích

Chứa hệ thống **chatbot AI** thông minh của SmartMeal - cho phép người dùng trò chuyện tự nhiên về dinh dưỡng, bữa ăn, và sức khỏe. Chatbot sử dụng AI để hiểu câu hỏi và đưa ra câu trả lời phù hợp với ngữ cảnh.

## Tính năng

- 💬 Trò chuyện tự nhiên bằng tiếng Việt/Tiếng Anh
- 🍽️ Tư vấn dinh dưỡng cá nhân hóa
- 📊 Truy cập dữ liệu meal logs và progress
- 🤖 Tích hợp với AI providers (Gemini, Groq)
- 📝 Ghi nhớ ngữ cảnh cuộc trò chuyện

## Các thành phần

### service.py
Logic chính của chatbot:
- Xử lý tin nhắn user
- Gọi AI để tạo response
- Quản lý conversation flow
- Xử lý special commands

### context_builder.py
Xây dựng ngữ cảnh cho AI:
```python
def build_context(user_id: UUID, conversation_history: list) -> dict:
    # Lấy user profile
    profile = get_user_profile(user_id)
    
    # Lấy meal logs gần đây
    recent_meals = get_recent_meals(user_id, days=7)
    
    # Lấy nutrition goals
    goals = get_nutrition_goals(user_id)
    
    # Xây dựng context prompt
    return {
        "user_info": profile,
        "recent_nutrition": summarize_nutrition(recent_meals),
        "goals": goals,
        "conversation_history": conversation_history
    }
```

### context_policy.py
Quy tắc xử lý ngữ cảnh:
- Kiểm tra thông tin cần thiết (profile complete?)
- Validation cho queries
- Fallback responses khi thiếu data
- Privacy protection

### prompts.py
System prompts cho chatbot:
```python
SYSTEM_PROMPT = """
Bạn là SmartMeal Assistant - trợ lý dinh dưỡng AI.
- Hỗ trợ tiếng Việt và tiếng Anh
- Cung cấp thông tin dinh dưỡng chính xác
- Đưa ra lời khuyên cá nhân hóa dựa trên user data
- Khuyến khích lifestyle lành mạnh
"""
```

### utils.py
Các hàm tiện ích:
- Text processing
- Message formatting
- Sentiment detection
- Command parsing

## Conversation Flow

```
User Message
    ↓
Parse & Validate
    ↓
Build Context (user data, history)
    ↓
Call AI Provider (with system prompt + context)
    ↓
Process AI Response
    ↓
Save to Database
    ↓
Return Response to User
```

## Message Types

### User Message
```python
{
    "role": "user",
    "content": "Hôm nay tôi ăn gì để giảm cân?",
    "timestamp": "2026-05-01T10:30:00Z"
}
```

### Assistant Message
```python
{
    "role": "assistant",
    "content": "Dựa trên mục tiêu giảm cân của bạn...",
    "timestamp": "2026-05-01T10:30:05Z",
    "suggestions": ["Gợi ý bữa ăn..."]
}
```

### System Message
```python
{
    "role": "system",
    "content": "Context updated: User logged breakfast",
    "timestamp": "2026-05-01T10:30:00Z"
}
```

## Special Commands

| Command | Mô tả | Ví dụ |
|---------|-------|-------|
| `/help` | Hiển thị hướng dẫn | "Bạn có thể làm gì?" |
| `/meal` | Log bữa ăn | "/meal 2 trứng, 1 lát bánh mì" |
| `/progress` | Xem tiến độ | "/progress tuần này" |
| `/goals` | Xem/cài goals | "/goals của tôi là gì?" |

## Database Schema

```
ChatSession
├── id: UUID (PK)
├── user_id: UUID (FK)
├── title: String
├── created_at: DateTime
└── updated_at: DateTime

ChatMessage
├── id: UUID (PK)
├── session_id: UUID (FK)
├── role: Enum (user/assistant/system)
├── content: Text
├── metadata: JSON (extra data)
└── created_at: DateTime
```

## Context Window

Chatbot có giới hạn context window:
- Lưu trữ tối đa 20 tin nhắn gần nhất
- Tổng token giới hạn bởi AI model
- Older messages được summarized nếu cần

## Privacy & Safety

- User data không bao giờ được share với bên thứ ba
- Sensitive info được masked trong logs
- AI responses được validate trước khi trả về
- Rate limiting để prevent abuse

## Integration với Frontend

Frontend gọi API qua `apps/web/src/services/chatbot.service.ts`:

```typescript
const response = await chatbotService.sendMessage({
  sessionId: session.id,
  content: userMessage,
  context: { ... }
});
```
