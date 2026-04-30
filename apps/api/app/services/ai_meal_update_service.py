import time
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.core.config import settings
from app.models.food_nutrition import FoodNutrition
from app.schemas.meal_update import (
    AIMealUpdateOutput,
    MealUpdatePreviewItem,
    MealUpdatePreviewResponse,
)

MEAL_UPDATE_PROMPT_VERSION = "meal_update_v1"

MEAL_UPDATE_SYSTEM_PROMPT = """
Bạn là chuyên gia dinh dưỡng của ứng dụng SmartMeal.
Nhiệm vụ: nhận diện các món ăn trong ảnh và ước lượng khối lượng.

Nguyên tắc:
1. Nhận diện chính xác từng món ăn trong ảnh.
2. Ước lượng cân nặng thực tế của từng món (gram), không phải khẩu phần.
3. Đưa ra confidence score (0-1) thể hiện độ chắc chắn.
4. Trả về JSON đúng schema, không giải thích ngoài JSON.
5. Nếu không nhận diện được món nào, vẫn trả về items rỗng.
"""


async def _search_food_in_db(db: AsyncSession, food_name: str) -> FoodNutrition | None:
    pattern = f"%{food_name.strip()}%"
    result = await db.execute(
        select(FoodNutrition).where(
            or_(
                FoodNutrition.food_name.ilike(pattern),
                FoodNutrition.food_name_vi.ilike(pattern),
                FoodNutrition.food_name_en.ilike(pattern),
            )
        ).order_by(FoodNutrition.is_verified.desc())
    )
    return result.scalars().first()


def _calc_nutrition_per_item(
    food: FoodNutrition | None,
    weight_g: float,
) -> dict:
    if food is None:
        return {"calories": 0.0, "protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0}
    ratio = weight_g / 100.0
    return {
        "calories": round(food.calories_per_100g * ratio, 2),
        "protein_g": round(food.protein_per_100g * ratio, 2),
        "carb_g": round(food.carb_per_100g * ratio, 2),
        "fat_g": round(food.fat_per_100g * ratio, 2),
    }


async def preview_meal_from_image(
    db: AsyncSession,
    user_id: UUID,
    meal_type: str,
    image_bytes: bytes,
    mime_type: str,
) -> tuple[MealUpdatePreviewResponse, dict, int]:
    """
    1. Gọi AI provider analyze_image_json.
    2. Map từng food_name sang food_nutrition.
    3. Tính nutrition + match_status.
    4. Trả về (preview_response, raw_ai_response, latency_ms).
    """
    user_prompt = (
        f"Meal type: {meal_type}. "
        "Analyze the food image and return a JSON with: "
        '{"items": [{"food_name": "...", "estimated_weight_g": ..., "confidence": ...}], '
        '"overall_confidence": ..., "notes": "..."}'
    )

    provider = get_ai_provider(settings.AI_MEAL_PROVIDER)
    start_time = time.perf_counter()

    ai_output, raw_response = await run_in_threadpool(
        provider.analyze_image_json,
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=user_prompt,
        response_schema=AIMealUpdateOutput,
        temperature=0.2,
    )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    preview_items: list[MealUpdatePreviewItem] = []
    total_cal = 0.0
    total_prot = 0.0
    total_carb = 0.0
    total_fat = 0.0

    for ai_item in ai_output.items:
        food = await _search_food_in_db(db, ai_item.food_name)

        if food is not None:
            match_status: str = "matched"
            nutrition = _calc_nutrition_per_item(food, ai_item.estimated_weight_g)
        else:
            match_status = "not_found"
            nutrition = _calc_nutrition_per_item(None, 0)

        preview_items.append(
            MealUpdatePreviewItem(
                detected_food_name=ai_item.food_name,
                matched_food_id=food.id if food else None,
                match_status=match_status,
                estimated_weight_g=ai_item.estimated_weight_g,
                confidence=ai_item.confidence,
                calories=nutrition["calories"],
                protein_g=nutrition["protein_g"],
                carb_g=nutrition["carb_g"],
                fat_g=nutrition["fat_g"],
            )
        )

        total_cal += nutrition["calories"]
        total_prot += nutrition["protein_g"]
        total_carb += nutrition["carb_g"]
        total_fat += nutrition["fat_g"]

    model_name = (
        settings.GEMINI_MODEL
        if settings.AI_MEAL_PROVIDER == "gemini"
        else settings.GROQ_VISION_MODEL
    )

    preview_response = MealUpdatePreviewResponse(
        items=preview_items,
        overall_confidence=ai_output.overall_confidence,
        total_calories=round(total_cal, 2),
        total_protein_g=round(total_prot, 2),
        total_carb_g=round(total_carb, 2),
        total_fat_g=round(total_fat, 2),
        meal_type=meal_type,
        ai_model=model_name,
    )

    return preview_response, raw_response, latency_ms
