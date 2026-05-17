"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type {
  ChatMessage,
  ChatSession,
  StaleSessionWarning,
  MealLogCardData,
  ChatCard,
  ChatCardResponse,
} from "@/components/chatbot/types";
import {
  chatbotService,
  getCachedSessionId,
  cacheSessionId,
  listChatSessions,
  getLatestSession,
  createSession,
  deleteSession,
  renameSession,
  checkStaleSession,
} from "@/services/chatbot.service";
import { mealService } from "@/services/meal.service";

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Xin chào, tôi là SmartMeal AI Assistant. Tôi có thể hỗ trợ bạn về dinh dưỡng, bữa ăn và luyện tập. Bạn cần giúp gì hôm nay?",
  timestamp: new Date(),
};

export interface ChatSessionWithMeta extends ChatSession {
  isLoading?: boolean;
}

export function useChatBot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mealLogs, setMealLogs] = useState<MealLogCardData[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [staleWarning, setStaleWarning] = useState<StaleSessionWarning | null>(null);
  // ── Card state ──────────────────────────────────────────────────────────────
  const [pendingCard, setPendingCard] = useState<ChatCard | null>(null);
  const [isCardLoading, setIsCardLoading] = useState(false);
  // ── End card state ──────────────────────────────────────────────────────────

  const queryClient = useQueryClient(); // Invalidate dashboard/history after meal log mutations
  const abortRef = useRef<AbortController | null>(null);
  const historyLoadedRef = useRef(false);

  // ── Define callbacks before effects that use them ────────────────────────────

  const loadSessionsAndResume = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const sessionsResult = await listChatSessions(20);
      setSessions(sessionsResult.items);

      const cachedId = getCachedSessionId();
      if (cachedId) {
        await resumeSession(cachedId);
      } else {
        const latest = await getLatestSession();
        if (latest) {
          await resumeSession(latest.id);
        } else {
          setMessages([WELCOME_MESSAGE]);
        }
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
      setMessages([WELCOME_MESSAGE]);
    } finally {
      setIsLoadingHistory(false);
      historyLoadedRef.current = true;
    }
  }, []);

  // Initialize: load sessions and auto-resume latest
  useEffect(() => {
    if (isOpen && !historyLoadedRef.current) {
      loadSessionsAndResume();
    }
  }, [isOpen, loadSessionsAndResume]);

  const resumeSession = useCallback(async (sessionId: string) => {
    try {
      const msgs = await chatbotService.resumeSession(sessionId);
      setMessages(msgs.length > 0 ? msgs : [WELCOME_MESSAGE]);
      cacheSessionId(sessionId);

      const stale = await checkStaleSession(sessionId);
      setStaleWarning(stale.is_stale ? stale : null);
    } catch {
      localStorage.removeItem("smartmeal_chatbot_session_id");
      setMessages([WELCOME_MESSAGE]);
      setCurrentSession(null);
    }
  }, []);

  const switchSession = useCallback(async (session: ChatSession) => {
    if (currentSession?.id === session.id) return;

    setCurrentSession(session);
    cacheSessionId(session.id);
    setStaleWarning(null);
    setPendingCard(null); // Clear any pending card on session switch
    setMessages([]);
    setIsLoadingHistory(true);

    try {
      const msgs = await chatbotService.resumeSession(session.id);
      setMessages(msgs);

      const stale = await checkStaleSession(session.id);
      if (stale.is_stale) setStaleWarning(stale);
    } catch {
      setMessages([WELCOME_MESSAGE]);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [currentSession?.id]);

  const startNewSession = useCallback(async () => {
    setIsLoadingHistory(true);
    try {
      const session = await createSession();
      setCurrentSession(session);
      setSessions((prev) => [session, ...prev]);
      setMessages([WELCOME_MESSAGE]);
      setStaleWarning(null);
      setPendingCard(null);
      cacheSessionId(session.id);
    } catch (err) {
      console.error("Failed to create session:", err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  const removeSession = useCallback(async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));

      if (currentSession?.id === sessionId) {
        localStorage.removeItem("smartmeal_chatbot_session_id");
        if (sessions.length > 1) {
          const nextSession = sessions.find((s) => s.id !== sessionId);
          if (nextSession) await switchSession(nextSession);
        } else {
          setCurrentSession(null);
          setMessages([WELCOME_MESSAGE]);
        }
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  }, [currentSession, sessions, switchSession]);

  const editMealLog = useCallback(async (id: string, updates: Partial<MealLogCardData>) => {
    // Capture the current meal log state before optimistic update for recalculate call
    const currentMeal = mealLogs.find((m) => m.id === id);
    // Optimistic update
    setMealLogs((prev) =>
      prev.map((meal) => (meal.id === id ? { ...meal, ...updates } : meal))
    );
    try {
      // Trigger server-side total recalculation after editing items
      await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/api/v1/meal-logs/${id}/recalculate`, { method: "POST" });
    } catch (err) {
      // Revert optimistic update on failure
      if (currentMeal) {
        setMealLogs((prev) => prev.map((m) => (m.id === id ? currentMeal : m)));
      }
      console.error("Failed to recalculate meal totals:", err);
    }
  }, [mealLogs]);

  const removeMealLog = useCallback(async (id: string) => {
    try {
      await mealService.deleteMealLog(id);
      setMealLogs((prev) => prev.filter((meal) => meal.id !== id));
      // Invalidate dashboard and history queries so they refetch fresh data immediately
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["mealLogs"] });
    } catch (err) {
      console.error("Failed to remove meal log:", err);
    }
  }, [queryClient]);

  const updateSessionTitle = useCallback(async (sessionId: string, title: string) => {
    try {
      const updated = await renameSession(sessionId, title);
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? updated : s))
      );
      if (currentSession?.id === sessionId) {
        setCurrentSession(updated);
      }
    } catch (err) {
      console.error("Failed to rename session:", err);
    }
  }, [currentSession]);

  const dismissStaleWarning = useCallback(() => {
    setStaleWarning(null);
  }, []);

  const openChat = useCallback(() => setIsOpen(true), []);
  const closeChat = useCallback(() => setIsOpen(false), []);
  const toggleChat = useCallback(() => setIsOpen((prev) => !prev), []);

  // ── Card helpers ────────────────────────────────────────────────────────────

  const _handleStreamEvents = useCallback(
    async (reader: ReadableStreamDefaultReader<Uint8Array>, tempAssistantId: string) => {
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          // Check for SSE event: card
          if (line.startsWith("event: card\ndata: ")) {
            const jsonStr = line.slice("event: card\ndata: ".length);
            try {
              const card = JSON.parse(jsonStr) as ChatCard;
              setPendingCard(card);
              setIsTyping(false);
              // Remove the streaming placeholder since a card was emitted
              setMessages((prev) => prev.filter((m) => m.id !== tempAssistantId));
              return; // Done handling — card awaits user response
            } catch {
              // Malformed card JSON — ignore
            }
            continue;
          }

          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.delta) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === tempAssistantId ? { ...m, content: m.content + data.delta } : m
                )
              );
            }
            if (data.done) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === tempAssistantId ? { ...m, isStreaming: false } : m
                )
              );
              setStaleWarning(null);
            }
            if (data.error) {
              throw new Error(data.detail ?? data.error);
            }
          } catch {
            // Ignore malformed SSE lines
          }
        }
      }
    },
    []
  );

  const _handleStreamError = useCallback(
    (
      err: unknown,
      tempAssistantId: string,
      errorContent: string
    ) => {
      setMessages((prev) => prev.filter((m) => m.id !== tempAssistantId));
      if ((err as Error)?.name !== "AbortError") {
        const errorMsg: ChatMessage = {
          id: `msg-${Date.now()}-error`,
          role: "assistant",
          content: errorContent,
          isError: true,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      }
    },
    []
  );

  const _ensureSession = useCallback(async (): Promise<string | null> => {
    let sessionId = currentSession?.id || getCachedSessionId();
    if (!sessionId) {
      setIsLoadingHistory(true);
      try {
        const session = await createSession();
        sessionId = session.id;
        setCurrentSession(session);
        setSessions((prev) => [session, ...prev]);
      } catch {
        return null;
      } finally {
        setIsLoadingHistory(false);
      }
    }
    return sessionId;
  }, [currentSession]);

  const _streamFetch = useCallback(
    async (
      sessionId: string,
      content: string,
      tempAssistantId: string,
      errorContent: string
    ) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      const token = localStorage.getItem("smartmeal_access_token");
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/api/v1/ai/chat/sessions/${sessionId}/messages/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token ?? ""}`,
          },
          body: JSON.stringify({ content }),
          signal: abortRef.current.signal,
        }
      );

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      await _handleStreamEvents(response.body!.getReader(), tempAssistantId);
    },
    [_handleStreamEvents]
  );

  const sendMessageStream = useCallback(
    async (content: string) => {
      if (!content.trim() || isTyping) return;

      const sessionId = await _ensureSession();
      if (!sessionId) return;

      const tempUserMsg: ChatMessage = {
        id: `msg-${Date.now()}-user`,
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);
      setInputValue("");
      setIsTyping(true);

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
        await _streamFetch(
          sessionId,
          content.trim(),
          tempAssistantId,
          "Xin lỗi, tôi đang gặp sự cố kết nối. Vui lòng thử lại trong giây lát."
        );
      } catch (err) {
        _handleStreamError(
          err,
          tempAssistantId,
          "Xin lỗi, tôi đang gặp sự cố kết nối. Vui lòng thử lại trong giây lát."
        );
      } finally {
        setIsTyping(false);
      }
    },
    [isTyping, _ensureSession, _streamFetch, _handleStreamError]
  );

  const retryLastMessage = useCallback(async () => {
    const lastUserMsg = messages
      .filter((m) => m.role === "user")
      .at(-1);
    if (!lastUserMsg) return;

    setMessages((prev) => prev.filter((m) => m.isError !== true));
    await sendMessageStream(lastUserMsg.content);
  }, [messages, sendMessageStream]);

  // ── Card submission ──────────────────────────────────────────────────────────

  const submitCardResponse = useCallback(
    async (response: ChatCardResponse) => {
      if (!pendingCard || !currentSession) return;

      const sessionId = currentSession.id;
      setIsCardLoading(true);
      setPendingCard(null);
      setIsTyping(true);

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
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL ?? ""}/api/v1/ai/chat/sessions/${sessionId}/card-response`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token ?? ""}`,
            },
            body: JSON.stringify(response),
          }
        );

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        await _handleStreamEvents(res.body!.getReader(), tempAssistantId);
      } catch (err) {
        _handleStreamError(
          err,
          tempAssistantId,
          "Xin lỗi, tôi đang gặp sự cố kết nối. Vui lòng thử lại trong giây lát."
        );
      } finally {
        setIsCardLoading(false);
        setIsTyping(false);
      }
    },
    [pendingCard, currentSession, _handleStreamEvents, _handleStreamError]
  );

  const skipCard = useCallback(() => {
    if (!pendingCard?.skippable) return;
    setPendingCard(null);
  }, [pendingCard]);

  // ── Non-streaming sendMessage (unchanged) ───────────────────────────────────

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isTyping) return;

      let sessionId = currentSession?.id || getCachedSessionId();
      if (!sessionId) {
        try {
          const session = await createSession();
          sessionId = session.id;
          setCurrentSession(session);
          setSessions((prev) => [session, ...prev]);
        } catch {
          return;
        }
      }

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
        const reply = await chatbotService.sendMessage(sessionId!, content.trim(), {
          signal: abortRef.current.signal,
        });
        setMessages((prev) => [...prev, reply]);
        setStaleWarning(null);
      } catch (err) {
        if ((err as Error)?.name === "CanceledError" || (err as Error)?.name === "AbortError") return;
        const errorMsg: ChatMessage = {
          id: `msg-${Date.now()}-error`,
          role: "assistant",
          content: "Xin lỗi, tôi đang gặp sự cố kết nối. Vui lòng thử lại trong giây lát.",
          isError: true,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsTyping(false);
      }
    },
    [isTyping, currentSession]
  );

  // ── Return ──────────────────────────────────────────────────────────────────

  return {
    // State
    isOpen,
    messages,
    mealLogs,
    inputValue,
    isTyping,
    isLoadingHistory,
    currentSession,
    sessions,
    staleWarning,
    // Card state
    pendingCard,
    isCardLoading,
    // Actions
    setInputValue,
    openChat,
    closeChat,
    toggleChat,
    sendMessage,
    sendMessageStream,
    startNewSession,
    switchSession,
    removeSession,
    updateSessionTitle,
    dismissStaleWarning,
    resumeSession,
    editMealLog,
    removeMealLog,
    retryLastMessage,
    // Card actions
    submitCardResponse,
    skipCard,
  };
}
