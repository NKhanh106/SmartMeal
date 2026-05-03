from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: Optional[str] = None
    status: str
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    ai_analysis_log_id: Optional[UUID] = None
    role: str
    content: str
    meta_data: Optional[dict] = Field(None, alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ChatSendMessageResponse(BaseModel):
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse


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
