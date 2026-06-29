from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.meal import MealLog
from app.models.enums import MealLogSourceType
from app.core.utils import get_active_goal as _get_active_goal


def round_decimal(value: Decimal, places: str = "0.01") -> Decimal:
    """Làm tròn số thập phân. Nếu None thì không xử lý trực tiếp ở đây, xử lý từ safe_decimal."""
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def safe_decimal(value) -> Decimal:
    """Chuyển đổi an toàn về Decimal."""
    if value is None:
        return Decimal("0")
    # Cast trước sang dạng float/string an toàn
    return Decimal(str(value))


def calculate_progress(consumed: Decimal, target) -> dict:
    """
    Tính tiến độ theo target.
    Ví dụ:
        consumed = 1500
        target = 2000
        remaining = 500
        percent = 75
    """
    consumed = round_decimal(consumed)

    if target is None:
        return {
            "consumed": consumed,
            "target": None,
            "remaining": None,
            "percent": None,
        }

    target = safe_decimal(target)

    if target <= 0:
        return {
            "consumed": consumed,
            "target": round_decimal(target),
            "remaining": None,
            "percent": None,
        }

    remaining = target - consumed
    percent = consumed / target * Decimal("100")

    return {
        "consumed": consumed,
        "target": round_decimal(target),
        "remaining": round_decimal(remaining),
        "percent": round_decimal(percent),
    }


def get_day_range(
    target_date: date,
    timezone_str: str = "Asia/Ho_Chi_Minh",
):
    """
    Tạo khoảng thời gian bắt đầu/kết thúc của một ngày theo timezone local,
    sau đó đổi về UTC để query với TIMESTAMPTZ.
    """
    tz = ZoneInfo(timezone_str)

    start_local = datetime.combine(
        target_date,
        time.min,
        tzinfo=tz,
    )

    end_local = start_local + timedelta(days=1)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    return start_utc, end_utc


# Canonical get_active_goal is imported from app.core.utils
# This module re-exports it for backward compatibility
get_active_goal = _get_active_goal


def build_goal_summary(goal):
    """
    Tạo tóm tắt mục tiêu (dict).
    """
    if not goal:
        return None

    return {
        "id": goal.id,
        "goal_type": goal.goal_type.value if hasattr(goal.goal_type, "value") else str(goal.goal_type),
        "daily_calorie_target": safe_decimal(goal.daily_calorie_target),
        "protein_target_g": safe_decimal(goal.protein_target_g),
        "carb_target_g": safe_decimal(goal.carb_target_g),
        "fat_target_g": safe_decimal(goal.fat_target_g),
    }


async def get_daily_dashboard(
    db: AsyncSession,
    user_id: UUID,
    target_date: date,
    timezone_str: str = "Asia/Ho_Chi_Minh",
) -> dict:
    """
    Tổng hợp dashboard trong một ngày.
    """
    start_utc, end_utc = get_day_range(
        target_date=target_date,
        timezone_str=timezone_str,
    )

    active_goal = await get_active_goal(
        db=db,
        user_id=user_id,
    )

    result = await db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .filter(
            MealLog.user_id == user_id,
            MealLog.meal_time >= start_utc,
            MealLog.meal_time < end_utc,
        )
        .order_by(MealLog.meal_time.desc())
    )
    meals = result.scalars().all()

    total_calories = sum((safe_decimal(meal.total_calories) for meal in meals), Decimal("0"))
    total_protein = sum((safe_decimal(meal.total_protein_g) for meal in meals), Decimal("0"))
    total_carb = sum((safe_decimal(meal.total_carb_g) for meal in meals), Decimal("0"))
    total_fat = sum((safe_decimal(meal.total_fat_g) for meal in meals), Decimal("0"))

    total_calories = round_decimal(total_calories)
    total_protein = round_decimal(total_protein)
    total_carb = round_decimal(total_carb)
    total_fat = round_decimal(total_fat)

    meals_response = [
        {
            "id": meal.id,
            "meal_type": meal.meal_type,
            "meal_time": meal.meal_time,
            "total_calories": safe_decimal(meal.total_calories),
            "total_protein_g": safe_decimal(meal.total_protein_g),
            "total_carb_g": safe_decimal(meal.total_carb_g),
            "total_fat_g": safe_decimal(meal.total_fat_g),
            "note": meal.note,
            "source": meal.source.value if hasattr(meal.source, "value") else str(meal.source),
        }
        for meal in meals
    ]

    # Count auto-detected meals (from chat)
    auto_detected_count = sum(
        1 for meal in meals
        if meal.source in (MealLogSourceType.chat_extraction, MealLogSourceType.chat_command)
    )

    return {
        "user_id": user_id,
        "target_date": target_date,
        "active_goal": build_goal_summary(active_goal),

        "total_calories": total_calories,
        "total_protein_g": total_protein,
        "total_carb_g": total_carb,
        "total_fat_g": total_fat,

        "calories_progress": calculate_progress(
            consumed=total_calories,
            target=active_goal.daily_calorie_target if active_goal else None,
        ),
        "protein_progress": calculate_progress(
            consumed=total_protein,
            target=active_goal.protein_target_g if active_goal else None,
        ),
        "carb_progress": calculate_progress(
            consumed=total_carb,
            target=active_goal.carb_target_g if active_goal else None,
        ),
        "fat_progress": calculate_progress(
            consumed=total_fat,
            target=active_goal.fat_target_g if active_goal else None,
        ),

        "meal_count": len(meals),
        "auto_detected_count": auto_detected_count,
        "meals": meals_response,
    }


async def get_weekly_dashboard(
    db: AsyncSession,
    user_id: UUID,
    end_date: date,
    timezone_str: str = "Asia/Ho_Chi_Minh",
) -> dict:
    """
    Tổng hợp dashboard 7 ngày (end_date là ngày cuối cùng).
    """
    start_date = end_date - timedelta(days=6)

    start_utc, _ = get_day_range(
        target_date=start_date,
        timezone_str=timezone_str,
    )

    _, end_utc_exclusive = get_day_range(
        target_date=end_date,
        timezone_str=timezone_str,
    )

    active_goal = await get_active_goal(
        db=db,
        user_id=user_id,
    )

    result = await db.execute(
        select(MealLog)
        .filter(
            MealLog.user_id == user_id,
            MealLog.meal_time >= start_utc,
            MealLog.meal_time < end_utc_exclusive,
        )
        .order_by(MealLog.meal_time.asc())
    )
    meals = result.scalars().all()

    tz = ZoneInfo(timezone_str)

    daily_map = {}

    # Khởi tạo bản nháp 7 ngày
    for i in range(7):
        d = start_date + timedelta(days=i)
        daily_map[d] = {
            "date": d,
            "total_calories": Decimal("0"),
            "total_protein_g": Decimal("0"),
            "total_carb_g": Decimal("0"),
            "total_fat_g": Decimal("0"),
            "meal_count": 0,
        }

    # Cộng dồn số liệu từ DB vào bản đồ 7 ngày
    for meal in meals:
        meal_time = meal.meal_time

        if meal_time.tzinfo is None:
            meal_time = meal_time.replace(tzinfo=timezone.utc)

        local_date = meal_time.astimezone(tz).date()

        if local_date not in daily_map:
            continue

        daily_map[local_date]["total_calories"] += safe_decimal(meal.total_calories)
        daily_map[local_date]["total_protein_g"] += safe_decimal(meal.total_protein_g)
        daily_map[local_date]["total_carb_g"] += safe_decimal(meal.total_carb_g)
        daily_map[local_date]["total_fat_g"] += safe_decimal(meal.total_fat_g)
        daily_map[local_date]["meal_count"] += 1

    daily_items = []
    total_calories = Decimal("0")
    total_protein = Decimal("0")
    total_carb = Decimal("0")
    total_fat = Decimal("0")

    for d in sorted(daily_map.keys()):
        item = daily_map[d]

        item["total_calories"] = round_decimal(item["total_calories"])
        item["total_protein_g"] = round_decimal(item["total_protein_g"])
        item["total_carb_g"] = round_decimal(item["total_carb_g"])
        item["total_fat_g"] = round_decimal(item["total_fat_g"])

        total_calories += item["total_calories"]
        total_protein += item["total_protein_g"]
        total_carb += item["total_carb_g"]
        total_fat += item["total_fat_g"]

        daily_items.append(item)

    avg_calories = total_calories / Decimal("7")

    return {
        "user_id": user_id,

        "start_date": start_date,
        "end_date": end_date,

        "active_goal": build_goal_summary(active_goal),

        "total_calories": round_decimal(total_calories),
        "avg_calories": round_decimal(avg_calories),

        "total_protein_g": round_decimal(total_protein),
        "total_carb_g": round_decimal(total_carb),
        "total_fat_g": round_decimal(total_fat),

        "daily_items": daily_items,
    }
