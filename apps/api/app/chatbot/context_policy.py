from dataclasses import dataclass


@dataclass
class ChatbotContextPolicy:
    """
    Quy định chatbot được phép lấy bao nhiêu dữ liệu.
    Mục tiêu: đủ cá nhân hóa nhưng không tốn token quá mức.
    """
    max_recent_meals: int = 5
    max_chat_history_messages: int = 4
    include_weekly_dashboard: bool = False
    include_daily_recommendation: bool = True
    include_progress_logs: bool = False

    # Token-budget caps for free-text fields injected into the prompt.
    # Cap chosen to keep total context under Groq llama-3.1-8b-instant's
    # free-tier 6000 TPM limit even when a user fills every card with long text.
    profile_free_text_cap: int = 200
    chat_history_message_cap: int = 200

DEFAULT_CHATBOT_CONTEXT_POLICY = ChatbotContextPolicy()
