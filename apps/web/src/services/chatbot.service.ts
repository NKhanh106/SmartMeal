/**
 * Chatbot service — connects to SmartMeal backend AI Chatbot API.
 *
 * Flow:
 * 1. getOrCreateSession() — creates a new chat session (once per browser session).
 *    After creation, session ID is cached in sessionStorage.
 * 2. sendMessage() — POST /api/v1/ai/chat/sessions/{session_id}/messages
 *    Returns { user_message, assistant_message }
 *
 * The backend handles:
 * - User context building (profile, goals, dashboard, history)
 * - AI generation via Groq
 * - Message persistence
 * - AI audit logging
 */

import { api } from "@/lib/api-client";
import type { ChatMessage } from "@/components/chatbot/types";

const SESSION_CACHE_KEY = "smartmeal_chatbot_session_id";
const CHATBOT_SESSION_ENDPOINT = "/api/v1/ai/chat/sessions";
const CHATBOT_MESSAGES_ENDPOINT = (sessionId: string) =>
  `${CHATBOT_SESSION_ENDPOINT}/${sessionId}/messages`;

// ─── Session management ─────────────────────────────────────────────────────────

interface ChatSessionResponse {
  id: string;
  user_id: string;
  title: string | null;
  status: string;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

interface SendMessageResponse {
  user_message: {
    id: string;
    session_id: string;
    role: string;
    content: string;
    created_at: string;
    [key: string]: unknown;
  };
  assistant_message: {
    id: string;
    session_id: string;
    role: string;
    content: string;
    created_at: string;
    [key: string]: unknown;
  };
}

/**
 * Get the cached session ID from sessionStorage.
 * Returns null if no session exists yet.
 */
export function getCachedSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(SESSION_CACHE_KEY);
}

/**
 * Cache a session ID in sessionStorage for this browser session.
 */
function cacheSessionId(sessionId: string): void {
  if (typeof window !== "undefined") {
    sessionStorage.setItem(SESSION_CACHE_KEY, sessionId);
  }
}

/**
 * Get the existing chat session or create a new one.
 * Reuses cached session if available to maintain conversation history.
 */
export async function getOrCreateSession(): Promise<ChatSessionResponse> {
  const cached = getCachedSessionId();
  if (cached) {
    // Verify the session still exists by fetching its messages
    try {
      await api.get<unknown[]>(`${CHATBOT_SESSION_ENDPOINT}/${cached}/messages`);
      // Session still valid — return it
      return { id: cached, user_id: "", title: null, status: "active", last_message_at: null, created_at: "", updated_at: "" };
    } catch {
      // Session expired or invalid — clear cache and create new
      sessionStorage.removeItem(SESSION_CACHE_KEY);
    }
  }

  // Create a new session
  const session = await api.post<ChatSessionResponse>(CHATBOT_SESSION_ENDPOINT, {});
  cacheSessionId(session.id);
  return session;
}

/**
 * Fetch all messages for the current session.
 * Used on initial load to restore conversation history.
 */
export async function fetchSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  const messages = await api.get<ChatSessionResponse[]>(
    `${CHATBOT_SESSION_ENDPOINT}/${sessionId}/messages`
  );

  return messages.map((msg) => ({
    id: msg.id,
    role: msg.role as "user" | "assistant",
    content: msg.content,
    timestamp: new Date(msg.created_at),
  }));
}

// ─── Send message ───────────────────────────────────────────────────────────────

export interface SendMessageOptions {
  signal?: AbortSignal;
}

export const chatbotService = {
  /**
   * Send a message and receive an AI reply.
   *
   * Internally:
   * - Gets or creates a persistent chat session.
   * - POSTs the message to the backend.
   * - Backend builds user context, calls Groq AI, and returns both messages.
   *
   * @param content  The user's message text.
   * @param options  AbortSignal for cancellation.
   * @returns The assistant's ChatMessage reply.
   */
  async sendMessage(
    content: string,
    options?: SendMessageOptions
  ): Promise<ChatMessage> {
    // Ensure we have a session
    const session = await getOrCreateSession();

    // Cache the session ID if not already cached
    cacheSessionId(session.id);

    const response = await api.post<SendMessageResponse>(
      CHATBOT_MESSAGES_ENDPOINT(session.id),
      { content },
      options?.signal
        ? {
            // Pass AbortSignal via custom config — axios needs adapter interceptors
            signal: options.signal,
          }
        : undefined
    );

    const assistantMsg = response.assistant_message;

    return {
      id: assistantMsg.id,
      role: assistantMsg.role as "user" | "assistant",
      content: assistantMsg.content,
      timestamp: new Date(assistantMsg.created_at),
    };
  },

  /**
   * Restore messages from a previous session.
   * Call this on initial load to show conversation history.
   */
  async restoreMessages(): Promise<ChatMessage[]> {
    const sessionId = getCachedSessionId();
    if (!sessionId) return [];

    try {
      return await fetchSessionMessages(sessionId);
    } catch {
      return [];
    }
  },

  /**
   * Force-create a new session (clears cached session).
   * Useful for "New conversation" button.
   */
  async startNewSession(): Promise<ChatSessionResponse> {
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(SESSION_CACHE_KEY);
    }
    return getOrCreateSession();
  },
};
