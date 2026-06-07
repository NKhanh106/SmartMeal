/**
 * Chatbot service — connects to SmartMeal backend AI Chatbot API.
 *
 * Session Management:
 * - Sessions are persistent conversations listed in sidebar
 * - User can resume any past session
 * - NEW session only created when user explicitly clicks "New Chat"
 * - Most recent active session auto-loaded on login/return
 * - Sessions have auto-generated titles from first message
 */

import { api } from "@/lib/api-client";
import type { ChatMessage, ChatSession, ChatMessagesPaginated, StaleSessionWarning } from "@/components/chatbot/types";

const CHATBOT_SESSION_ENDPOINT = "/api/v1/ai/chat/sessions";
const CHATBOT_MESSAGES_ENDPOINT = (sessionId: string) =>
  `${CHATBOT_SESSION_ENDPOINT}/${sessionId}/messages`;

// ─── Types ─────────────────────────────────────────────────────────────────────

interface ChatSessionCreate {
  title?: string;
}

interface ChatSessionUpdate {
  title?: string;
}

// ─── Session management ────────────────────────────────────────────────────────

/**
 * Get the existing chat session or create a new one.
 * Reuses cached session if available to maintain conversation history.
 */
export async function getOrCreateSession(): Promise<ChatSession> {
  // Check localStorage for cached session ID
  const cached = localStorage.getItem("smartmeal_chatbot_session_id");
  if (cached) {
    try {
      // Verify the session still exists
      const session = await api.get<ChatSession>(`${CHATBOT_SESSION_ENDPOINT}/${cached}`);
      return session;
    } catch {
      // Session expired or invalid — clear cache
      localStorage.removeItem("smartmeal_chatbot_session_id");
    }
  }

  // Create a new session
  const session = await api.post<ChatSession>(CHATBOT_SESSION_ENDPOINT, {});
  localStorage.setItem("smartmeal_chatbot_session_id", session.id);
  return session;
}

/**
 * Cache a session ID in localStorage for persistence across browser sessions.
 */
export function cacheSessionId(sessionId: string): void {
  localStorage.setItem("smartmeal_chatbot_session_id", sessionId);
}

/**
 * Get the cached session ID from localStorage.
 * Returns null if no session exists yet.
 */
export function getCachedSessionId(): string | null {
  return localStorage.getItem("smartmeal_chatbot_session_id");
}

/**
 * List all chat sessions for current user with cursor-based pagination.
 */
export async function listChatSessions(
  limit: number = 20,
  cursor?: string
): Promise<{ items: ChatSession[]; has_more: boolean; next_cursor: string | null }> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);

  const response = await api.get<{ total: number; items: ChatSession[] }>(
    `${CHATBOT_SESSION_ENDPOINT}?${params.toString()}`
  );

  return {
    items: response.items,
    has_more: response.total > limit,
    next_cursor: response.items.length === limit ? response.items[response.items.length - 1].id : null,
  };
}

/**
 * Get the most recent session for auto-resume on login.
 */
export async function getLatestSession(): Promise<ChatSession | null> {
  try {
    return await api.get<ChatSession | null>(`${CHATBOT_SESSION_ENDPOINT}/latest`);
  } catch {
    return null;
  }
}

/**
 * Get a single session by ID.
 */
export async function getSession(sessionId: string): Promise<ChatSession> {
  return api.get<ChatSession>(`${CHATBOT_SESSION_ENDPOINT}/${sessionId}`);
}

/**
 * Create a new chat session (only called when user explicitly clicks New Chat).
 */
export async function createSession(title?: string): Promise<ChatSession> {
  const session = await api.post<ChatSession>(CHATBOT_SESSION_ENDPOINT, { title } as ChatSessionCreate);
  localStorage.setItem("smartmeal_chatbot_session_id", session.id);
  return session;
}

/**
 * Rename a chat session.
 */
export async function renameSession(
  sessionId: string,
  title: string
): Promise<ChatSession> {
  return api.patch<ChatSession>(`${CHATBOT_SESSION_ENDPOINT}/${sessionId}`, {
    title,
  } as ChatSessionUpdate);
}

/**
 * Soft delete a chat session.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`${CHATBOT_SESSION_ENDPOINT}/${sessionId}`);
  // Clear cached session if it was the deleted one
  if (getCachedSessionId() === sessionId) {
    localStorage.removeItem("smartmeal_chatbot_session_id");
  }
}

/**
 * Check if a session is stale (>24h since last activity).
 */
export async function checkStaleSession(sessionId: string): Promise<StaleSessionWarning> {
  return api.get<StaleSessionWarning>(`${CHATBOT_SESSION_ENDPOINT}/${sessionId}/stale`);
}

/**
 * Tell backend that user skipped a clarification card.
 * Used for anti-loop protection.
 */
export async function skipCard(sessionId: string): Promise<void> {
  await api.post(`${CHATBOT_SESSION_ENDPOINT}/${sessionId}/card-skip`, {});
}

// ─── Messages ─────────────────────────────────────────────────────────────────

/**
 * Fetch paginated messages for a session.
 * Loads newest first, use before_id for infinite scroll upward.
 */
export async function fetchSessionMessages(
  sessionId: string,
  limit: number = 30,
  beforeId?: string
): Promise<ChatMessagesPaginated> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (beforeId) params.set("before_id", beforeId);

  const response = await api.get<ChatMessagesPaginated>(
    `${CHATBOT_MESSAGES_ENDPOINT(sessionId)}?${params.toString()}`
  );

  return {
    items: response.items.map((msg) => ({
      id: msg.id,
      role: msg.role as "user" | "assistant",
      content: msg.content,
      timestamp: new Date(msg.created_at ?? new Date().toISOString()),
    })),
    has_more: response.has_more,
    next_cursor: response.next_cursor,
  };
}

// ─── Send message ─────────────────────────────────────────────────────────────

export interface SendMessageOptions {
  signal?: AbortSignal;
}

export const chatbotService = {
  /**
   * Send a message and receive an AI reply.
   */
  async sendMessage(
    sessionId: string,
    content: string,
    options?: SendMessageOptions
  ): Promise<ChatMessage> {
    const response = await api.post<{
      user_message: { id: string; role: string; content: string; created_at: string };
      assistant_message: { id: string; role: string; content: string; created_at: string };
    }>(
      CHATBOT_MESSAGES_ENDPOINT(sessionId),
      { content },
      options?.signal ? { signal: options.signal } : undefined
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
   * Start a new chat session.
   */
  async startNewSession(): Promise<ChatSession> {
    return createSession();
  },

  /**
   * Resume an existing session by loading its messages.
   */
  async resumeSession(sessionId: string): Promise<ChatMessage[]> {
    const paginated = await fetchSessionMessages(sessionId);
    // Return messages in chronological order (newest first for display)
    return paginated.items.reverse();
  },

  /**
   * Load more messages (for infinite scroll).
   */
  async loadMoreMessages(
    sessionId: string,
    beforeId: string
  ): Promise<ChatMessagesPaginated> {
    return fetchSessionMessages(sessionId, 30, beforeId);
  },
};
