"""
Shared utilities for SmartMeal backend.

Eliminates duplicated code:
- round_decimal() was duplicated in 3 places
- serialize_dict() was duplicated in 2 places
- get_active_goal() was duplicated in 3 places
"""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.nutrition_goal import NutritionGoal


# ─── Decimal helpers ──────────────────────────────────────────────────────────────

def round_decimal(value: Decimal | float | int | None, places: str = "0.01") -> Decimal:
    """Làm tròn số thập phân đến n chữ số (mặc định 2 chữ số)."""
    if value is None:
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def safe_decimal(value: Any) -> Decimal:
    """Chuyển đổi an toàn bất kỳ giá trị nào về Decimal."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        if not value == value:  # NaN check
            return Decimal("0")
        return Decimal(str(value))
    if isinstance(value, int):
        return Decimal(value)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def decimal_to_float(value: Any) -> float | None:
    """Convert Decimal to float for JSON serialization."""
    if isinstance(value, Decimal):
        return float(value)
    return value


# ─── Serialization helpers ──────────────────────────────────────────────────────

def serialize_value(value: Any) -> Any:
    """Serialize a single value for JSON output."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def serialize_dict(obj: Any) -> Any:
    """Recursively serialize a dict/list for JSON output."""
    if isinstance(obj, dict):
        return {k: serialize_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_dict(v) for v in obj]
    if isinstance(obj, (Decimal, date, datetime, UUID)):
        return serialize_value(obj)
    return obj


# ─── Nutrition goal helpers ──────────────────────────────────────────────────────

async def get_active_goal(db: AsyncSession, user_id: UUID) -> NutritionGoal | None:
    """
    Lấy mục tiêu dinh dưỡng đang active của user.
    Canonical implementation — use this instead of duplicating the query.
    """
    result = await db.execute(
        select(NutritionGoal).where(
            NutritionGoal.user_id == user_id,
            NutritionGoal.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_enum_value(enum_instance: Any) -> str:
    """Safely get string value from a Pydantic/SQLAlchemy enum."""
    if hasattr(enum_instance, "value"):
        return enum_instance.value
    return str(enum_instance)
