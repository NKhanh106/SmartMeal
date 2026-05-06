from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ─── AI output schema (what the AI model returns) ──────────────────────────────

class AIMealItem(BaseModel):
    food_name: str = Field(..., description="Tên món ăn được AI nhận diện")
    estimated_weight_g: float = Field(..., ge=1, le=5000, description="Cân nặng ước lượng (gram)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Độ chắc chắn của AI (0-1)")


class AIMealUpdateOutput(BaseModel):
    items: list[AIMealItem] = Field(..., min_length=0, description="Danh sách món ăn được nhận diện (rỗng nếu không nhận diện được)")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Độ chắc chắn tổng thể")
    notes: Optional[str] = Field(None, description="Ghi chú thêm từ AI")


# ─── Preview response schema (what backend returns after mapping) ──────────────

MatchStatus = Literal["matched", "partial", "not_found"]


class MealUpdatePreviewItem(BaseModel):
    detected_food_name: str = Field(..., description="Tên món ăn được phát hiện từ ảnh")
    matched_food_id: Optional[UUID] = Field(None, description="UUID trong food_nutrition nếu match thành công")
    match_status: MatchStatus = Field(..., description="Trạng thái khớp: matched / partial / not_found")
    match_score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Điểm fuzzy match (0-1): 1.0=hoàn toàn khớp, 0.55+=tốt, 0.4-0.54=khớp một phần"
    )
    match_method: Optional[str] = Field(
        None,
        description="Phương pháp match: 'exact' | 'normalized' | 'fuzzy' | 'learned'"
    )
    alternatives: Optional[list[dict]] = Field(
        None,
        description="Danh sách gợi ý thay thế: [{food_id, food_name, score}]"
    )
    estimated_weight_g: float = Field(..., ge=1, description="Cân nặng ước lượng (gram)")

    confidence: float = Field(..., ge=0.0, le=1.0, description="Độ chắc chắn từ AI vision")
    calories: Optional[float] = Field(None, ge=0, description="Calories tính theo khối lượng")
    protein_g: Optional[float] = Field(None, ge=0, description="Protein (gram) tính theo khối lượng")
    carb_g: Optional[float] = Field(None, ge=0, description="Carb (gram) tính theo khối lượng")
    fat_g: Optional[float] = Field(None, ge=0, description="Fat (gram) tính theo khối lượng")


class MealUpdatePreviewResponse(BaseModel):
    items: list[MealUpdatePreviewItem]
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    total_calories: float = Field(..., ge=0)
    total_protein_g: float = Field(..., ge=0)
    total_carb_g: float = Field(..., ge=0)
    total_fat_g: float = Field(..., ge=0)
    meal_type: str
    ai_model: Optional[str] = None
    # Image metadata — set when image is persisted during preview
    uploaded_image_id: Optional[UUID] = Field(
        None,
        description="ID of the uploaded image. Use this in the confirm request to link the image to the meal.",
    )
    image_url: Optional[str] = Field(
        None,
        description="Public URL to the uploaded preview image.",
    )
    # Cache indicator — true when result was served from Redis cache
    from_cache: bool = Field(
        False,
        description="True if this result was served from Redis cache (duplicate image).",
    )

    model_config = ConfigDict(from_attributes=True)


# ─── Confirm request schema ────────────────────────────────────────────────────

class MealUpdateConfirmItem(BaseModel):
    food_nutrition_id: Optional[UUID] = Field(None, description="UUID trong food_nutrition (null nếu không match)")
    detected_food_name: str = Field(..., description="Tên món ăn đã được xác nhận")
    display_food_name: Optional[str] = Field(None)
    estimated_weight_g: float = Field(..., gt=0, description="Cân nặng đã xác nhận (gram)")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class MealUpdateConfirmRequest(BaseModel):
    meal_type: str = Field(..., description="bua_sang | bua_trua | bua_toi | an_vat | khac")
    meal_time: Optional[datetime] = Field(None)
    uploaded_image_id: Optional[UUID] = Field(
        None,
        description="ID of the image previously uploaded during preview. "
        "If provided, the image will be linked to this meal log.",
    )
    items: list[MealUpdateConfirmItem] = Field(..., min_length=1)


# ─── Confirm response schema ───────────────────────────────────────────────────

class MealUpdateConfirmResponse(BaseModel):
    meal_log_id: UUID
    message: str = "Meal confirmed and saved successfully."

    model_config = ConfigDict(from_attributes=True)
