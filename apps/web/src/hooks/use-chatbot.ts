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

  const sendMessageStream = useCallback(
    async (content: string) => {
      if (!content.trim() || isTyping) return;

      const sessionId = chatbotService.getCachedSessionId();
      if (!sessionId) {
        // No session yet — fall back to regular sendMessage
        sendMessage(content);
        return;
      }

      // Cancel any in-flight request
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      // Add user message to UI immediately
      const tempUserMsg: ChatMessage = {
        id: `msg-${Date.now()}-user`,
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);
      setInputValue("");
      setIsTyping(true);

      // Placeholder for streaming assistant response
      const tempAssistantId = `msg-${Date.now()}-assistant`;
      const tempAssistantMsg: ChatMessage = {
        id: tempAssistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      };
      setMessages((prev) => [...prev, tempAssistantMsg]);

      try {
        const token = localStorage.getItem("smartmeal_access_token");
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"}/api/v1/ai/chat/sessions/${sessionId}/messages/stream`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token ?? ""}`,
            },
            body: JSON.stringify({ content: content.trim() }),
            signal: abortRef.current.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));

              if (data.delta) {
                // Append token to streaming message
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === tempAssistantId
                      ? { ...m, content: m.content + data.delta }
                      : m
                  )
                );
              }
              if (data.done) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === tempAssistantId ? { ...m, isStreaming: false } : m
                  )
                );
              }
              if (data.error) {
                throw new Error(data.detail ?? data.error);
              }
            } catch {
              // Ignore malformed SSE lines
            }
          }
        }
      } catch (err) {
        // Remove streaming placeholder on error
        setMessages((prev) => prev.filter((m) => m.id !== tempAssistantId));
        if ((err as Error).name !== "AbortError") {
          // Show error message
          const errorMsg: ChatMessage = {
            id: `msg-${Date.now()}-error`,
            role: "assistant",
            content:
              "Xin lỗi, tôi đang gặp sự cố kết nối. Vui lòng thử lại trong giây lát.",
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errorMsg]);
        }
      } finally {
        setIsTyping(false);
      }
    },
    [isTyping]
  );

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
    sendMessageStream,
  };
}
