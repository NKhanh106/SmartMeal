export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: Date;
  created_at?: string; // from API response
  /** True when the message is still streaming from the SSE endpoint */
  isStreaming?: boolean;
  /** True when this message represents a failed/errored request */
  isError?: boolean;
  /** Full card payload when message_type === "card" */
  card?: ChatCard;
  /** Depth mode used to generate this assistant response */
  depth?: "quick" | "deep" | "expert";
}

// ─── Interactive Card Types ──────────────────────────────────────────────────────

export type CardType = "single_select" | "multi_select" | "rank" | "number_input" | "confirm";

export interface CardOption {
  id: string;
  label: string;
  icon?: string | null;
  description?: string | null;
}

export interface ChatCard {
  card_id: string;
  card_type: CardType;
  title: string;
  subtitle?: string | null;
  options?: CardOption[] | null;
  min_value?: number | null;
  max_value?: number | null;
  unit?: string | null;
  placeholder?: string | null;
  min_selections?: number | null;
  max_selections?: number | null;
  trigger_reason: string;
  skippable?: boolean;
}

export interface ChatCardResponse {
  card_id: string;
  card_type: CardType;
  selected_ids?: string[] | null;
  ranked_ids?: string[] | null;
  number_value?: number | null;
  text_value?: string | null;
  confirmed?: boolean | null;
}

export interface ChatSession {
  id: string;
  user_id: string;
  title: string | null;
  status: string;
  last_message_at: string | null;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessagesPaginated {
  items: ChatMessage[];
  has_more: boolean;
  next_cursor: string | null;
}

export interface StaleSessionWarning {
  is_stale: boolean;
  days_since_activity: number | null;
  last_activity_at: string | null;
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

export interface MealLogCardData {
  id: string;
  meal_type: string;
  meal_time: string;
  total_calories: number;
  total_protein_g: number;
  total_carb_g: number;
  total_fat_g: number;
  source: "manual" | "chat_extraction" | "chat_command";
  items: Array<{
    id: string;
    detected_food_name: string;
    display_food_name?: string;
    estimated_weight_g?: number;
    calories: number;
    protein_g: number;
    carb_g: number;
    fat_g: number;
  }>;
}
