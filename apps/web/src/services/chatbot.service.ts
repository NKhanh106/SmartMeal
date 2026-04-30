/**
 * Chatbot service.
 *
 * TODO: Replace mock responses with a real FastAPI chatbot endpoint.
 *   - Endpoint: POST /api/v1/chatbot/send
 *   - Body: { message: string }
 *   - Response: { reply: string }
 *
 * DO NOT call Gemini API directly from the frontend.
 * DO NOT hardcode any API keys here.
 */

import type { ChatMessage } from "@/components/chatbot/types";

// ─── Mock response bank ─────────────────────────────────────────────────────────

const MOCK_RESPONSES = [
  "Mình đã nhận được câu hỏi của bạn. Ở bước tiếp theo, tính năng này sẽ được kết nối với AI backend.",
  "Cảm ơn bạn đã hỏi! Tính năng chat thông minh đang được phát triển. Bạn có thể theo dõi cập nhật sắp tới nhé.",
  "Mình hiểu rồi! Hiện tại chatbot đang chạy ở chế độ demo. Kết nối AI thật sẽ có trong phiên bản hoàn chỉnh.",
  "Bạn có thể hỏi mình về dinh dưỡng, bữa ăn, luyện tập hoặc mục tiêu sức khỏe của bạn. Mình sẽ hỗ trợ ngay khi có thể!",
  "Để có kết quả tốt nhất, hãy đảm bảo bạn đã thiết lập Health Profile và Nutrition Goal đầy đủ trong mục Profile nhé.",
];

function randomMockResponse(): string {
  return MOCK_RESPONSES[Math.floor(Math.random() * MOCK_RESPONSES.length)];
}

// ─── Simulate network delay ─────────────────────────────────────────────────────

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ─── Service ───────────────────────────────────────────────────────────────────

export const chatbotService = {
  /**
   * Send a chat message and receive a reply.
   *
   * Currently returns a mock response after a simulated delay.
   *
   * TODO: Replace with real API call:
   *   const res = await api.post<{ reply: string }>("/api/v1/chatbot/send", { message });
   *   return res.reply;
   */
  async sendMessage(
    _message: string,
    _options?: { signal?: AbortSignal }
  ): Promise<ChatMessage> {
    // Simulate typing delay
    await delay(1200 + Math.random() * 800);

    const now = new Date();
    return {
      id: `msg-${now.getTime()}-${Math.random().toString(36).slice(2, 7)}`,
      role: "assistant",
      content: randomMockResponse(),
      timestamp: now,
    };
  },
};
