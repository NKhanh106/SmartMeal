from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
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
from app.services.meal_service import create_meal_log_with_items

router = APIRouter(prefix="/ai/meal-update", tags=["AI Meal Update"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


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
    return image_bytes


def _get_effective_user_id(
    current_user: User,
    target_user_id: UUID | None,
) -> UUID:
    if current_user.role == "admin" and target_user_id is not None:
        return target_user_id
    return current_user.id


@router.post("/preview", response_model=MealUpdatePreviewResponse)
async def preview_meal_from_image(
    meal_type: str = Form(...),
    target_user_id: UUID | None = Form(default=None),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image_bytes = _validate_image(image)
    effective_user_id = _get_effective_user_id(current_user, target_user_id)

    try:
        preview, raw_response, latency_ms = await _preview_meal_from_image(
            db=db,
            user_id=effective_user_id,
            meal_type=meal_type,
            image_bytes=image_bytes,
            mime_type=image.content_type,
        )
    except Exception as exc:
        model_name = (
            settings.GEMINI_MODEL
            if settings.AI_MEAL_PROVIDER == "gemini"
            else settings.GROQ_VISION_MODEL
        )
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
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI meal analysis failed. Please try again.",
        )

    model_name = (
        settings.GEMINI_MODEL
        if settings.AI_MEAL_PROVIDER == "gemini"
        else settings.GROQ_VISION_MODEL
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
    meal_items = [
        MealItemCreate(
            food_nutrition_id=item.food_nutrition_id,
            detected_food_name=item.detected_food_name,
            display_food_name=item.display_food_name,
            estimated_weight_g=item.estimated_weight_g,
            confidence=item.confidence,
            source=ItemSourceType.ai_nhan_dien,
        )
        for item in payload.items
    ]

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

    await db.commit()
    await db.refresh(meal_log)

    return MealUpdateConfirmResponse(
        meal_log_id=meal_log.id,
        message="Meal confirmed and saved successfully.",
    )
