import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class InsightType(str):
    DIET_PREFERENCE = "diet_preference"
    HEALTH_CONSTRAINT = "health_constraint"
    FITNESS_NOTE = "fitness_note"
    GOAL_NOTE = "goal_note"
    GENERAL = "general"


class ConversationInsight(Base):
    """
    Rút trích thông tin cốt lõi từ cuộc trò chuyện chatbot để làm giàu context
    cho các đoạn hội thoại sau.

    Sau mỗi tin nhắn AI, hệ thống gọi AI một lần nữa để trích xuất:
    - Sở thích ăn uống (thích món nào, không thích món nào)
    - Ràng buộc sức khỏe (dị ứng, bệnh lý)
    - Ghi chú tập luyện (tần suất, khả năng)
    - Thay đổi mục tiêu
    - Thông tin tổng quát khác

    Logic deduplicate: cùng (user_id, key) → upsert, cập nhật value/summary.
    """

    __tablename__ = "conversation_insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    insight_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=InsightType.GENERAL,
    )

    # Key rút gọn dùng để deduplicate/upsert
    # Ví dụ: "preferred_cuisine", "allergy_soy", "exercise_freq", "goal_weight_loss"
    key: Mapped[str] = mapped_column(String(100), nullable=False)

    # Giá trị cụ thể
    value: Mapped[str] = mapped_column(Text, nullable=False)

    # Câu tóm tắt tiếng Việt do AI viết, dùng làm context
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    # Có còn hiệu lực không (user có thể tắt insights cũ)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    __table_args__ = (
        # Deduplicate: mỗi user chỉ có 1 active insight cho 1 key
        # Khi upsert, update existing thay vì tạo mới
        Index("idx_insights_user_key", "user_id", "key"),
        Index("idx_insights_user_active", "user_id", "is_active"),
        Index("idx_insights_session", "session_id"),
    )
