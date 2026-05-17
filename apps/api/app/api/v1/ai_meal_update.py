from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.cache import cache_get, cache_set, make_image_cache_key
from app.db.session import get_db
from app.models.enums import ItemSourceType
from app.models.user import User
from app.schemas.meal import MealItemCreate, MealLogCreate
from app.schemas.meal_update import (
    MealUpdateConfirmRequest,
    MealUpdateConfirmResponse,
    MealUpdatePreviewResponse,
)
from app.services.ai_log_service import create_ai_log
from app.services.ai_meal_update_service import (
    MEAL_UPDATE_PROMPT_VERSION,
)
from app.services.ai_meal_update_service import (
    preview_meal_from_image as _preview_meal_from_image,
)
from app.services.learning_service import record_food_correction
from app.services.meal_service import create_meal_log_with_items

router = APIRouter(prefix="/ai/meal-update", tags=["AI Meal Update"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Magic bytes signatures for image validation
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
_WEBP_RIFF = b"RIFF"
_WEBP_WEBP = b"WEBP"


def _validate_image(image: UploadFile) -> bytes:
    if image.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image/jpeg, image/png, image/webp are allowed.",
        )
    image_bytes = image.file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file too large. Maximum size is 10 MB.",
        )
    # Validate magic bytes to ensure file content matches declared MIME type
    if image.content_type == "image/jpeg" and not image_bytes.startswith(_JPEG_SIGNATURE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JPEG file content.",
        )
    elif image.content_type == "image/png" and not image_bytes.startswith(_PNG_SIGNATURE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PNG file content.",
        )
    elif image.content_type == "image/webp":
        if not image_bytes.startswith(_WEBP_RIFF):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid WebP file content.",
            )
        # RIFF header present, verify WEBP signature at offset 8
        if len(image_bytes) < 12 or image_bytes[8:12] != _WEBP_WEBP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid WebP file content.",
            )
    return image_bytes


def _get_effective_user_id(
    current_user: User,
    target_user_id: UUID | None,
) -> UUID:
    if current_user.role == "admin" and target_user_id is not None:
        return target_user_id
    return current_user.id


@router.post("/recognize-image", response_model=MealUpdatePreviewResponse)
@limiter.limit("10/minute")
async def recognize_meal_image(
    request: Request,
    meal_type: str = Form(...),
    image: UploadFile = File(...),
    target_user_id: UUID | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dedicated food recognition endpoint with Redis caching.
    Returns AI-detected dishes with cached result for duplicate images.

    DEPRECATED: This endpoint is disabled. Use chat-based meal logging instead.
    """
    if not settings.FEATURE_IMAGE_MEAL_UPLOAD_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Image-based meal logging has been deprecated. Please use chat-based meal logging instead.",
        )

    import json
    import logging

    logger = logging.getLogger(__name__)

    image_bytes = _validate_image(image)
    effective_user_id = _get_effective_user_id(current_user, target_user_id)

    # Check cache first using image SHA256 hash
    cache_key = make_image_cache_key(image_bytes)
    cached_result = await cache_get(cache_key)
    if cached_result is not None:
        logger.info("Food recognition cache HIT")
        cached_preview = MealUpdatePreviewResponse.model_validate(cached_result)
        cached_preview.from_cache = True
        return cached_preview

    logger.info("Food recognition cache MISS")
    model_name = (
        settings.GEMINI_MODEL
        if settings.AI_MEAL_PROVIDER == "gemini"
        else settings.GROQ_VISION_MODEL
    )

    try:
        preview, raw_response, latency_ms = await _preview_meal_from_image(
            db=db,
            user_id=effective_user_id,
            meal_type=meal_type,
            image_bytes=image_bytes,
            mime_type=image.content_type,
            original_filename=image.filename,
        )
    except Exception as exc:
        await create_ai_log(
            db=db,
            user_id=effective_user_id,
            task_type="meal_image_analysis",
            provider_name=settings.AI_MEAL_PROVIDER,
            model_name=model_name,
            prompt_version=MEAL_UPDATE_PROMPT_VERSION,
            input_summary=f"provider={settings.AI_MEAL_PROVIDER}, meal_type={meal_type}",
            raw_response=None,
            status="failed",
            error_message=str(exc),
            latency_ms=0,
        )
        await db.commit()
        error_detail = str(exc)
        if "timeout" in error_detail.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI service timeout. Please try again.",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI meal analysis failed. Please try again.",
        )

    await create_ai_log(
        db=db,
        user_id=effective_user_id,
        task_type="meal_image_analysis",
        provider_name=settings.AI_MEAL_PROVIDER,
        model_name=model_name,
        prompt_version=MEAL_UPDATE_PROMPT_VERSION,
        input_summary=f"provider={settings.AI_MEAL_PROVIDER}, meal_type={meal_type}",
        raw_response=raw_response,
        status="success",
        latency_ms=latency_ms,
    )
    await db.commit()

    # Cache result for 24h
    await cache_set(cache_key, preview.model_dump(mode="json"), settings.FOOD_RECOGNITION_CACHE_TTL)

    return preview


@router.post("/preview", response_model=MealUpdatePreviewResponse)
@limiter.limit("10/minute")
async def preview_meal_from_image(
    request: Request,
    meal_type: str = Form(...),
    image: UploadFile = File(...),
    target_user_id: UUID | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview meal from uploaded image.

    DEPRECATED: This endpoint is disabled. Use chat-based meal logging instead.
    """
    if not settings.FEATURE_IMAGE_MEAL_UPLOAD_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Image-based meal logging has been deprecated. Please use chat-based meal logging instead.",
        )

    image_bytes = _validate_image(image)
    effective_user_id = _get_effective_user_id(current_user, target_user_id)

    model_name = (
        settings.GEMINI_MODEL
        if settings.AI_MEAL_PROVIDER == "gemini"
        else settings.GROQ_VISION_MODEL
    )

    try:
        preview, raw_response, latency_ms = await _preview_meal_from_image(
            db=db,
            user_id=effective_user_id,
            meal_type=meal_type,
            image_bytes=image_bytes,
            mime_type=image.content_type,
            original_filename=image.filename,
        )
    except Exception as exc:
        await create_ai_log(
            db=db,
            user_id=effective_user_id,
            task_type="meal_image_analysis",
            provider_name=settings.AI_MEAL_PROVIDER,
            model_name=model_name,
            prompt_version=MEAL_UPDATE_PROMPT_VERSION,
            input_summary=f"provider={settings.AI_MEAL_PROVIDER}, meal_type={meal_type}",
            raw_response=None,
            status="failed",
            error_message=str(exc),
            latency_ms=0,
        )
        await db.commit()
        # Return 504 for timeout, 503 for other failures
        error_detail = str(exc)
        if "timeout" in error_detail.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI service timeout. Please try again.",
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI meal analysis failed. Please try again.",
        )

    await create_ai_log(
        db=db,
        user_id=effective_user_id,
        task_type="meal_image_analysis",
        provider_name=settings.AI_MEAL_PROVIDER,
        model_name=model_name,
        prompt_version=MEAL_UPDATE_PROMPT_VERSION,
        input_summary=f"provider={settings.AI_MEAL_PROVIDER}, meal_type={meal_type}",
        raw_response=raw_response,
        status="success",
        latency_ms=latency_ms,
    )
    await db.commit()

    return preview


@router.post("/confirm", response_model=MealUpdateConfirmResponse)
async def confirm_meal_from_preview(
    payload: MealUpdateConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirm AI-detected items and save as a meal log.
    Also records food corrections for the learning system — every user edit
    to AI-detected items becomes training data for future predictions.

    If uploaded_image_id is provided, the image will be linked to the meal log
    and its TTL will be extended from 1 day to 7 days (meal retention).
    """
    meal_items = []

    for item in payload.items:
        meal_items.append(
            MealItemCreate(
                food_nutrition_id=item.food_nutrition_id,
                detected_food_name=item.detected_food_name,
                display_food_name=item.display_food_name,
                estimated_weight_g=item.estimated_weight_g,
                confidence=item.confidence,
                source=ItemSourceType.ai_nhan_dien,
            )
        )

    from app.models.enums import MealTypeEnum

    try:
        meal_type_enum = MealTypeEnum(payload.meal_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid meal_type: {payload.meal_type}. Must be one of: bua_sang, bua_trua, bua_toi, an_vat, khac.",
        )

    meal_log_create = MealLogCreate(
        meal_type=meal_type_enum,
        meal_time=payload.meal_time,
        items=meal_items,
    )

    meal_log = await create_meal_log_with_items(
        db=db,
        payload=meal_log_create,
        user_id=current_user.id,
    )

    # ── Link uploaded image to meal log ────────────────────────────────────────
    if payload.uploaded_image_id:
        from app.services.image_storage_service import get_image_metadata, link_image_to_entity

        linked = await link_image_to_entity(
            db=db,
            image_id=payload.uploaded_image_id,
            entity_type="meal_log",
            entity_id=meal_log.id,
        )
        if linked:
            img_meta = await get_image_metadata(
                db=db,
                image_id=payload.uploaded_image_id,
                user_id=current_user.id,
            )
            if img_meta:
                meal_log.image_url = img_meta.url
                meal_log.image_storage_path = img_meta.id

    # ── Record food corrections for learning system ──────────────────────────
    # For each item the user confirmed, check if they edited the AI suggestion
    for item in payload.items:
        # Record correction if user changed the food name or weight significantly
        if (
            item.display_food_name
            and item.display_food_name.strip().lower() != item.detected_food_name.strip().lower()
        ):
            await record_food_correction(
                db=db,
                user_id=current_user.id,
                meal_log_id=meal_log.id,
                ai_detected_food_name=item.detected_food_name,
                corrected_food_name=item.display_food_name,
                corrected_food_id=item.food_nutrition_id,
                ai_estimated_weight_g=item.estimated_weight_g,
            )

    await db.commit()
    await db.refresh(meal_log)

    # ── Invalidate daily plan cache ─────────────────────────────────────────────
    # When user logs a meal, the daily plan should be regenerated
    from datetime import date
    from app.services.daily_recommendation_service import invalidate_user_plan_cache
    await invalidate_user_plan_cache(current_user.id, date.today())

    return MealUpdateConfirmResponse(
        meal_log_id=meal_log.id,
        message="Meal confirmed and saved successfully.",
    )
