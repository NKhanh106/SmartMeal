# Thư mục `chatbot/` — AI Chatbot System

## Mục đích

Chứa hệ thống **chatbot AI** thông minh của SmartMeal — cho phép người dùng trò chuyện tự nhiên về dinh dưỡng, bữa ăn, và sức khỏe. Chatbot sử dụng AI (Groq) để hiểu câu hỏi và đưa ra câu trả lời phù hợp với ngữ cảnh cá nhân.

## Tính năng

- Trò chuyện tự nhiên bằng **tiếng Việt / tiếng Anh**
- Tư vấn dinh dưỡng **cá nhân hóa** dựa trên profile & goals
- Truy cập dữ liệu meal logs và progress
- Tích hợp với AI providers (Groq — cho tốc độ phản hồi nhanh)
- Ghi nhớ **ngữ cảnh** cuộc trò chuyện (profile, goals, meal history)
- **Streaming response** — hiển thị token từng phần, giảm perceived latency từ ~5s xuống gần như instant
- **Conversation insights** — trích xuất allergies, preferences từ cuộc trò chuyện

## Các thành phần

| File | Mô tả |
|------|--------|
| `service.py` | Core logic: xử lý tin nhắn, gọi AI, lưu tin nhắn, trích xuất insights |
| `context_builder.py` | Xây dựng context cho AI: user profile, goals, recent meals, progress |
| `context_policy.py` | Quy tắc truy cập dữ liệu, privacy protection, validation |
| `prompts.py` | System prompt (hướng dẫn AI persona), prompt builders |
| `utils.py` | Helper: sinh chat title từ nội dung |

## Conversation Flow

```
User sends message
    │
    ▼
save_chat_message (role="user")
    │
    ▼
build_chatbot_context (profile + goals + history)
    │
    ▼
build_chatbot_user_prompt (system + context + message)
    │
    ▼
get_ai_provider("groq") → Groq API
    │
    ├── Streaming: yield tokens → SSE → Frontend
    └── Non-streaming: wait full response → save to DB
    │
    ▼
save_chat_message (role="assistant")
    │
    ▼
extract_insights_from_conversation (allergies, preferences)
    │
    ▼
upsert_conversation_insights (AI insights → DB)
    │
    ▼
Commit transaction
```

## Context Building (`context_builder.py`)

AI được cung cấp context để câu trả lời cá nhân hóa:

```python
context = {
    "user_profile": { height, weight, age, gender, activity_level, ... },
    "nutrition_goal": { daily_calorie_target, protein_target, ... },
    "recent_meals": [5 recent meal logs],
    "recent_progress": [weight trend],
    "allergies": "hải sản, đậu phộng",
    "diet_preferences": "ăn chay, keto",
    "language": "vi",  # ngôn ngữ mặc định
}
```

## Streaming Response

Chatbot hỗ trợ **Server-Sent Events (SSE)** để streaming tokens:

```
Frontend                    Backend
   │                           │
   │── POST /messages/stream ──▶│
   │                           │── Groq API ──▶
   │                           │◀─ token 1 ──
   │◀─ data: {delta: "X"} ────│
   │                           │◀─ token 2 ──
   │◀─ data: {delta: "Y"} ────│
   │         ...               │
   │◀─ data: {done: true} ────│
```

Perceived latency giảm từ ~5-10s xuống gần như instant vì text hiển thị từng từ.

## Conversation Insights

Sau mỗi cuộc trò chuyện, hệ thống trích xuất insights:

```python
insights = {
    "insight_type": "health_constraint",
    "key": "allergy_seafood",
    "value": "dị ứng hải sản nhẹ",
    "summary": "Người dùng dị ứng hải sản"
}
```

Insights được dùng để cá nhân hóa gợi ý về sau.

## Rate Limiting

- Non-streaming: **20 requests/phút/IP**
- Streaming: **20 requests/phút/IP**

## Database Schema

```
chat_sessions
├── id: UUID (PK)
├── user_id: UUID (FK)
├── title: String (auto-generated from first message)
├── status: String (active | deleted)
├── last_message_at: DateTime
└── created_at, updated_at

chat_messages
├── id: UUID (PK)
├── session_id: UUID (FK)
├── role: String (user | assistant | system)
├── content: Text
├── metadata: JSON (prompt_version, provider, ai_log_id)
└── created_at

conversation_insights
├── id: UUID (PK)
├── user_id: UUID (FK)
├── session_id: UUID (FK)
├── insight_type: String
├── key: String
├── value: Text
├── summary: String
├── is_active: Boolean
└── created_at, updated_at
```

## Frontend Integration

Frontend giao tiếp qua `apps/web/src/services/chatbot.service.ts`:

```typescript
// Tạo hoặc lấy session
const session = await getOrCreateSession();

// Gửi message và nhận streaming response
const response = await api.post<SSE>(
  `/api/v1/ai/chat/sessions/${sessionId}/messages/stream`,
  { content: userMessage }
);

// Hoặc gửi message thường (chờ response đầy đủ)
const result = await chatbotService.sendMessage("Hôm nay tôi ăn gì?");
```

## Best Practices

- Mỗi lần gửi message đều **build context mới** để AI có thông tin cập nhật nhất
- **Session ID được cache** trong sessionStorage để duy trì conversation history
- Insights chỉ được extract khi có **ít nhất 2 messages** (user + assistant)
- Privacy: không bao giờ expose dữ liệu của user A cho user B
