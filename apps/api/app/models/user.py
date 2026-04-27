import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import CITEXT, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    # Sử dụng SQLAlchemy 2.0 style syntax (Mapped và mapped_column) để type hint chuẩn hơn
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String)

    role: Mapped[str] = mapped_column(String(20), default="user", server_default="user", nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Các trường phục vụ security và chặn login/spam (Từ Schema Database)
    failed_login_attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    login_allowed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )

    # Audit trails & Soft Delete
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), 
        server_default=text("now()"),
        onupdate=text("now()") # Hỗ trợ tự động cập nhật updated_at
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    # Relationship (1-1 với user_profiles)
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="chk_users_role"),
    )

    def __repr__(self) -> str:
        return f"<User(email='{self.email}')>"
