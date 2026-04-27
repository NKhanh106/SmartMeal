from dataclasses import dataclass


@dataclass
class ChatbotContextPolicy:
    """
    Quy định chatbot được phép lấy bao nhiêu dữ liệu.
    Mục tiêu: đủ cá nhân hóa nhưng không tốn token quá mức.
    """
    max_recent_meals: int = 5
    max_chat_history_messages: int = 8
    include_weekly_dashboard: bool = True
    include_daily_recommendation: bool = True
    include_progress_logs: bool = False

DEFAULT_CHATBOT_CONTEXT_POLICY = ChatbotContextPolicy()
