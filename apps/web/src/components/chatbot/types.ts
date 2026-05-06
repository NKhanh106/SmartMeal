export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: Date;
  /** True when the message is still streaming from the SSE endpoint */
  isStreaming?: boolean;
}

export interface ChatState {
  isOpen: boolean;
  messages: ChatMessage[];
  inputValue: string;
  isTyping: boolean;
}

export interface SendMessageOptions {
  signal?: AbortSignal;
}
