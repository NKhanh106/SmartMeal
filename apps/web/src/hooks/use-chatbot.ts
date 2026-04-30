"use client";

import { useState, useCallback, useRef } from "react";
import type { ChatMessage } from "@/components/chatbot/types";
import { chatbotService } from "@/services/chatbot.service";

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Xin chào, tôi là SmartMeal AI Assistant. Tôi có thể hỗ trợ bạn về dinh dưỡng, bữa ăn và luyện tập. Bạn cần giúp gì hôm nay?",
  timestamp: new Date(),
};

export function useChatBot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const openChat = useCallback(() => setIsOpen(true), []);
  const closeChat = useCallback(() => setIsOpen(false), []);

  const toggleChat = useCallback(() => setIsOpen((prev) => !prev), []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isTyping) return;

      // Cancel any in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      const userMsg: ChatMessage = {
        id: `msg-${Date.now()}-user`,
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInputValue("");
      setIsTyping(true);

      try {
        const reply = await chatbotService.sendMessage(content.trim(), {
          signal: abortRef.current.signal,
        });
        setMessages((prev) => [...prev, reply]);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        const errorMsg: ChatMessage = {
          id: `msg-${Date.now()}-error`,
          role: "assistant",
          content: "Xin lỗi, đã có lỗi xảy ra. Vui lòng thử lại.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsTyping(false);
      }
    },
    [isTyping]
  );

  return {
    isOpen,
    messages,
    inputValue,
    isTyping,
    setInputValue,
    openChat,
    closeChat,
    toggleChat,
    sendMessage,
  };
}
