import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, ForeignKey, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ProgressLog(Base):
    __tablename__ = "progress_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=text("CURRENT_DATE"))

    weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(6, 2))
    body_fat_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    waist_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    neck_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    chest_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    hip_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    progress_photo_url: Mapped[Optional[str]] = mapped_column(Text)
    note: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    user = relationship("User", back_populates="progress_logs")

    __table_args__ = (
        UniqueConstraint("user_id", "log_date", name="uq_progress_user_date"),
    )

    def __repr__(self) -> str:
        return f"<ProgressLog(user_id='{self.user_id}', log_date='{self.log_date}')>"
