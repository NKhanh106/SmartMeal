"use client";

import { useState, useCallback, useRef, useEffect } from "react";
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
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const historyLoadedRef = useRef(false);

  // Restore conversation history when chat is first opened
  useEffect(() => {
    if (isOpen && !historyLoadedRef.current) {
      historyLoadedRef.current = true;
      setIsLoadingHistory(true);
      chatbotService
        .restoreMessages()
        .then((history) => {
          if (history.length > 0) {
            setMessages((prev) => {
              // Keep welcome message, append history
              const withoutWelcome = prev[0]?.id === "welcome" ? prev.slice(1) : prev;
              return [...withoutWelcome, ...history];
            });
          }
        })
        .catch(() => {
          // Silently ignore history load errors
        })
        .finally(() => {
          setIsLoadingHistory(false);
        });
    }
  }, [isOpen]);

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
        // Ignore abort errors
        if ((err as Error).name === "CanceledError" || (err as Error).name === "AbortError") {
          return;
        }
        // Show error message to user
        const errorMsg: ChatMessage = {
          id: `msg-${Date.now()}-error`,
          role: "assistant",
          content:
            "Xin lỗi, tôi đang gặp sự cố kết nối. Vui lòng thử lại trong giây lát.",
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
    isLoadingHistory,
    setInputValue,
    openChat,
    closeChat,
    toggleChat,
    sendMessage,
  };
}
