from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    title: Optional[str] = None


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)


class ChatSessionListResponse(BaseModel):
    total: int
    items: list["ChatSessionResponse"]


class ChatSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: Optional[str] = None
    status: str
    last_message_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    depth: str = Field(
        default="deep",
        pattern="^(quick|deep|expert)$",
        description="Response depth mode: quick (fast, concise), deep (balanced), expert (comprehensive)",
    )


class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    ai_analysis_log_id: Optional[UUID] = None
    role: str
    content: str
    # message_type values: "text" | "card" | "card_response" | "meal_log" | "system"
    message_type: str = "text"
    # Full ChatCard payload when message_type == "card"
    card: Optional[dict] = None
    # ChatCardResponse when message_type == "card_response"
    card_response: Optional[dict] = None
    meta_data: Optional[dict] = Field(None, alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_with_safe_metadata(cls, msg) -> "ChatMessageResponse":
        """Construct response with safe metadata dict conversion."""
        return cls(
            id=msg.id,
            session_id=msg.session_id,
            ai_analysis_log_id=msg.ai_analysis_log_id,
            role=msg.role,
            content=msg.content,
            message_type=getattr(msg, "message_type", "text"),
            card=getattr(msg, "card", None),
            card_response=getattr(msg, "card_response", None),
            meta_data=msg.metadata_dict if hasattr(msg, "metadata_dict") else msg.meta_data,
            created_at=msg.created_at,
        )


class ChatSendMessageResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


class ChatMessagesPaginatedResponse(BaseModel):
    items: list["ChatMessageResponse"]
    has_more: bool
    next_cursor: Optional[str] = None


class StaleSessionWarning(BaseModel):
    is_stale: bool
    days_since_activity: Optional[int] = None
    last_activity_at: Optional[datetime] = None


# ─── Conversation Insights ─────────────────────────────────────────────────────

InsightType = str  # "diet_preference" | "health_constraint" | "fitness_note" | "goal_note" | "general"


class ExtractedInsightItem(BaseModel):
    """
    Schema cho mỗi insight mà AI trả về khi trích xuất.
    """
    insight_type: InsightType = Field(
        ...,
        description="Loại: diet_preference | health_constraint | fitness_note | goal_note | general",
    )
    key: str = Field(
        ...,
        max_length=100,
        description="Key rút gọn, dùng để deduplicate. Ví dụ: preferred_cuisine, allergy_gluten, exercise_freq",
    )
    value: str = Field(
        ...,
        max_length=500,
        description="Giá trị cụ thể. Ví dụ: thich an chay, diabetis type 2, tap gym 3 lan/tuan",
    )
    summary: str = Field(
        ...,
        max_length=300,
        description="Câu tóm tắt tiếng Việt dùng làm context. Ví dụ: Nguoi dung thich mon an chay, can han che tinh bot",
    )


class ExtractedInsightsOutput(BaseModel):
    """
    Schema cho output của AI khi trích xuất insights từ cuộc trò chuyện.
    """
    insights: list[ExtractedInsightItem] = Field(
        default_factory=list,
        description="Danh sách insights trích xuất được. Rỗng nếu không có thông tin mới.",
    )
    has_new_information: bool = Field(
        ...,
        description="True nếu có ít nhất 1 insight mới hoặc thay đổi so với trước.",
    )


class ConversationInsightResponse(BaseModel):
    id: UUID
    user_id: UUID
    session_id: UUID
    insight_type: str
    key: str
    value: str
    summary: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
