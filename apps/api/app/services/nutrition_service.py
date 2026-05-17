from datetime import date
from typing import Any, Dict, Optional

from app.core.constants import USAGE_GOAL_TO_NUTRITION_GOAL
from app.models.enums import ActivityLevelType, GenderType, NutritionGoalType
from app.models.user_profile import UserProfile


def calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: GenderType) -> float:
    """Công thức Mifflin-St Jeor"""
    base_bmr = (10.0 * float(weight_kg)) + (6.25 * float(height_cm)) - (5.0 * age)
    if gender == GenderType.nam:
        return base_bmr + 5
    elif gender == GenderType.nu:
        return base_bmr - 161
    else:
        return base_bmr - 78


def calculate_tdee(bmr: float, activity_level: ActivityLevelType) -> float:
    if activity_level == ActivityLevelType.it_van_dong:
        return bmr * 1.2
    elif activity_level == ActivityLevelType.van_dong_nhe:
        return bmr * 1.375
    elif activity_level == ActivityLevelType.van_dong_vua:
        return bmr * 1.55
    elif activity_level == ActivityLevelType.van_dong_nhieu:
        return bmr * 1.725
    elif activity_level == ActivityLevelType.van_dong_rat_nhieu:
        return bmr * 1.9
    return bmr * 1.2


def _get_health_adjustments(profile: UserProfile) -> Dict[str, Any]:
    """
    Return macro adjustment factors based on active health conditions.
    """
    adjustments: Dict[str, Any] = {
        "protein_factor": 1.0,
        "carb_factor": 1.0,
        "fat_factor": 1.0,
        "sodium_limit_mg": None,
        "extra_notes": [],
    }

    conditions = getattr(profile, "health_conditions", None) or []
    if not isinstance(conditions, list):
        return adjustments

    active = [c for c in conditions if isinstance(c, dict) and c.get("severity") != "resolved"]
    condition_ids = {c.get("condition") for c in active if c.get("condition")}

    if condition_ids & {"type1_diabetes", "type2_diabetes", "prediabetes"}:
        adjustments["carb_factor"] = 0.75
        adjustments["extra_notes"].append("Carb reduced for glycemic control")

    if "kidney_disease" in condition_ids:
        adjustments["protein_factor"] = 0.8
        adjustments["extra_notes"].append("Protein limited for kidney protection")

    if "gout" in condition_ids:
        adjustments["extra_notes"].append("Limit purine-rich foods")

    if "fatty_liver" in condition_ids:
        adjustments["fat_factor"] = 0.8
        adjustments["extra_notes"].append("Saturated fat limited for liver health")

    if "hypertension" in condition_ids:
        adjustments["sodium_limit_mg"] = 2000
        adjustments["extra_notes"].append("Sodium capped at 2g/day (DASH)")

    if "pcos" in condition_ids:
        adjustments["carb_factor"] = 0.85
        adjustments["extra_notes"].append("Low-GI approach for PCOS")

    if condition_ids & {"pregnancy", "breastfeeding"}:
        adjustments["protein_factor"] = 1.3
        adjustments["extra_notes"].append("Increased protein for pregnancy/lactation")

    return adjustments


def _map_usage_goal(usage_goal: Optional[str]) -> NutritionGoalType:
    if usage_goal and usage_goal in USAGE_GOAL_TO_NUTRITION_GOAL:
        return NutritionGoalType(USAGE_GOAL_TO_NUTRITION_GOAL[usage_goal])
    return NutritionGoalType.giu_can


def calculate_nutrition_targets(
    profile: UserProfile,
    goal_type: Optional[NutritionGoalType] = None,
) -> Dict[str, Any]:
    age = calculate_age(profile.date_of_birth)
    weight = float(profile.current_weight_kg)
    height = float(profile.height_cm)
    height_m = height / 100.0
    bmi = weight / (height_m ** 2)
    bmr = calculate_bmr(weight, height, age, profile.gender)
    tdee = calculate_tdee(bmr, profile.activity_level)

    if goal_type is None:
        usage_goal_val = getattr(profile, "usage_goal", None)
        usage_goal_str = (
            usage_goal_val.value
            if hasattr(usage_goal_val, "value")
            else str(usage_goal_val) if usage_goal_val else None
        )
        goal_type = _map_usage_goal(usage_goal_str)

    target_calories = float(tdee)
    if goal_type == NutritionGoalType.giam_can:
        target_calories = tdee - 500
    elif goal_type == NutritionGoalType.tang_co:
        target_calories = tdee + 300

    min_safe_cals = 1500 if profile.gender == GenderType.nam else 1200
    target_calories = max(target_calories, min_safe_cals)

    adjustments = _get_health_adjustments(profile)

    protein_g = 2.0 * weight * adjustments["protein_factor"]
    protein_cals = protein_g * 4

    fat_calories = target_calories * 0.25 * adjustments["fat_factor"]
    fat_g = fat_calories / 9

    remaining_cals = target_calories - protein_cals - fat_calories
    carb_g = (remaining_cals / 4) * adjustments["carb_factor"] if remaining_cals > 0 else 0

    return {
        "bmi": round(bmi, 2),
        "bmr_kcal": round(bmr),
        "tdee_kcal": round(tdee),
        "daily_calorie_target": round(target_calories),
        "protein_target_g": round(protein_g),
        "carb_target_g": round(carb_g),
        "fat_target_g": round(fat_g),
    }
