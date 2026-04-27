import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, Enum, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ActivityLevelType, DietTypeEnum, GenderType


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Khóa ngoại trỏ đến bảng users (UNIQUE vì mỗi user chỉ có 1 profile)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        unique=True, 
        nullable=False
    )

    # --- Thông tin nhân khẩu học ---
    gender: Mapped[GenderType] = mapped_column(
        Enum(GenderType, name="gender_type", create_type=False), 
        nullable=False
    )
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)

    # --- Thông tin thể chất hiện tại ---
    height_cm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    current_weight_kg: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)

    # Số đo cơ thể hiện tại (Optional)
    current_body_fat_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_waist_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_neck_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_hip_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    current_chest_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))

    # --- Mức độ vận động ---
    activity_level: Mapped[ActivityLevelType] = mapped_column(
        Enum(ActivityLevelType, name="activity_level_type", create_type=False),
        nullable=False,
        default=ActivityLevelType.it_van_dong
    )

    # --- Cá nhân hóa thực đơn ---
    diet_type: Mapped[DietTypeEnum] = mapped_column(
        Enum(DietTypeEnum, name="diet_type_enum", create_type=False),
        nullable=False,
        default=DietTypeEnum.binh_thuong
    )
    allergies: Mapped[Optional[str]] = mapped_column(Text)
    disliked_foods: Mapped[Optional[str]] = mapped_column(Text)
    preferred_foods: Mapped[Optional[str]] = mapped_column(Text)

    # --- Ghi chú sức khỏe ---
    health_note: Mapped[Optional[str]] = mapped_column(Text)

    # --- Audit trails ---
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()"),
        onupdate=text("now()")
    )

    # Relationship để map ngược lại cho dễ truy vấn (vd: profile.user)
    # Lưu ý: Sẽ cần khai báo `profile = relationship("UserProfile", back_populates="user", uselist=False)` bên file user.py sau đó
    user = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(user_id='{self.user_id}', height='{self.height_cm}', weight='{self.current_weight_kg}')>"
