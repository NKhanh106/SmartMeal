import json
import time
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ai_logger import log_ai_call
from app.ai.factory import get_ai_provider
from app.core.cache import cache_get, cache_set, make_image_cache_key
from app.core.config import settings
from app.models.food_nutrition import FoodNutrition
from app.schemas.meal_update import (
    AIMealUpdateOutput,
    MealUpdatePreviewItem,
    MealUpdatePreviewResponse,
)
from app.services.food_mapping_service import (
    match_food_name,
    calculate_nutrition_per_item,
)
from app.services.image_storage_service import save_image

MEAL_UPDATE_PROMPT_VERSION = "meal_update_v2"

MEAL_UPDATE_SYSTEM_PROMPT = """
Bạn là chuyên gia dinh dưỡng của ứng dụng SmartMeal.
Nhiệm vụ: nhận diện các món ăn trong ảnh và ước lượng khối lượng.

Nguyên tắc:
1. Nhận diện chính xác từng món ăn trong ảnh. Liệt kê từng món riêng biệt.
2. Ước lượng cân nặng thực tế của từng món (gram), không phải khẩu phần.
3. Đưa ra confidence score (0-1) thể hiện độ chắc chắn.
4. Trả về JSON đúng schema, không giải thích ngoài JSON.
5. Nếu không nhận diện được món nào, vẫn trả về items rỗng.
6. Với món ăn Việt Nam, ưu tiên dùng tên tiếng Việt có dấu (VD: "Cơm tấm", "Phở bò", "Bún chả").
7. Tách riêng các thành phần: ví dụ "Cơm sườn bì chả" → ["Cơm tấm", "Sườn nướng", "Bì chả", "Nước mắm"].
8. Với đồ uống trong ảnh (nước, trà, cà phê), ước lượng thể tích (ml) và nêu rõ loại đồ uống.
"""


@log_ai_call(feature="food_recognition")
async def preview_meal_from_image(
    db: AsyncSession,
    user_id: UUID,
    meal_type: str,
    image_bytes: bytes,
    mime_type: str,
    original_filename: str | None = None,
) -> tuple[MealUpdatePreviewResponse, dict, int]:
    """
    Multi-stage food recognition pipeline with Redis caching:

    1. Persist image to disk (image_type=temporary, 1-day TTL)
    2. Check Redis cache for same image hash → return cached result if found
    3. AI Vision: Call provider.analyze_image_json()
    4. Cache AI raw text for 24h
    5. Food Mapping: Match each detected food → food_nutrition DB
    6. Nutrition: Calculate macros per item weight
    7. Return preview with image metadata (uploaded_image_id, image_url)

    Returns (preview_response, raw_ai_response, latency_ms).
    """
    import logging

    logger = logging.getLogger(__name__)

    from fastapi import UploadFile
    from io import BytesIO

    # ── Step 1: Persist image as temporary (1-day TTL) ──────────────────────────
    uploaded_image_id = None
    image_url = None
    try:
        fake_file = UploadFile(
            filename=original_filename or "meal.jpg",
            file=BytesIO(image_bytes),
        )
        fake_file.content_type = mime_type

        saved = await save_image(
            db=db,
            file=fake_file,
            user_id=user_id,
            image_type="temporary",
        )
        uploaded_image_id = saved.id
        image_url = saved.url
        await db.commit()
    except Exception:
        # Image persistence failure should NOT break the preview
        logger.warning(
            "Failed to persist preview image for user %s, continuing without image.", user_id
        )

    user_prompt = (
        f"Meal type: {meal_type}. "
        "Analyze the food image and return a JSON with: "
        '{"items": [{"food_name": "...", "estimated_weight_g": ..., "confidence": ...}], '
        '"overall_confidence": ..., "notes": "..."}'
    )

    # ── Step 2: Check Redis cache (same image → same AI result) ─────────────────
    cache_key = make_image_cache_key(image_bytes)
    cached_raw_text = await cache_get(cache_key)
    start_time = time.perf_counter()
    provider = get_ai_provider(settings.AI_MEAL_PROVIDER)

    if cached_raw_text is not None:
        # Cache HIT — skip AI call, re-parse cached text
        logger.info("Food recognition cache HIT for key %s...", cache_key[:20])
        ai_text = cached_raw_text
        ai_output = AIMealUpdateOutput.model_validate(json.loads(ai_text))
        raw_response = {"provider": settings.AI_MEAL_PROVIDER, "cached": True, "text": ai_text}
    else:
        # Cache MISS — call AI
        logger.info("Food recognition cache MISS for key %s...", cache_key[:20])
        ai_output, raw_response = await run_in_threadpool(
            provider.analyze_image_json,
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=user_prompt,
            response_schema=AIMealUpdateOutput,
            temperature=0.2,
        )
        # Cache raw text for 24h
        if hasattr(ai_output, "model_dump"):
            cached_value = json.dumps(ai_output.model_dump(mode="json"), ensure_ascii=False)
            await cache_set(cache_key, cached_value, settings.FOOD_RECOGNITION_CACHE_TTL)
            raw_response["text"] = cached_value

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    preview_items: list[MealUpdatePreviewItem] = []
    total_cal = 0.0
    total_prot = 0.0
    total_carb = 0.0
    total_fat = 0.0

    for ai_item in ai_output.items:
        # Use the new fuzzy matching pipeline
        match_result = await match_food_name(db, ai_item.food_name, user_id=user_id)

        if match_result.matched_food is not None:
            nutrition = calculate_nutrition_per_item(
                match_result.matched_food, ai_item.estimated_weight_g
            )
        else:
            nutrition = calculate_nutrition_per_item(None, 0)

        preview_items.append(
            MealUpdatePreviewItem(
                detected_food_name=ai_item.food_name,
                matched_food_id=match_result.matched_food_id,
                match_status=match_result.match_status,
                estimated_weight_g=ai_item.estimated_weight_g,
                confidence=ai_item.confidence,
                match_score=match_result.match_score,
                match_method=match_result.search_method,
                alternatives=[
                    {
                        "food_id": str(alt.food.id),
                        "food_name": alt.food.food_name,
                        "score": alt.score,
                        "method": alt.method,
                    }
                    for alt in match_result.alternatives
                ],
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
        uploaded_image_id=uploaded_image_id,
        image_url=image_url,
    )

    return preview_response, raw_response, latency_ms
