"""
Planner Constraint Engine — rule-based validation for daily recommendations.

This module ensures AI-generated recommendations respect user constraints BEFORE
they are stored and shown to users. This prevents the LLM from hallucinating
impossible values or violating user goals.

The constraint engine operates in two modes:
1. VALIDATION: Check AI output, fix violations, flag issues
2. GUIDANCE: Provide structured constraints to the AI prompt

Constraint categories:
- Calorie budget (from TDEE ± goal adjustment)
- Macro ratio ranges (protein/carbs/fat percentages)
- Dietary restrictions (allergies, diet_type)
- Safety limits (minimum calories, maximum any macro)
"""

from dataclasses import dataclass
from typing import Optional

from app.models.enums import DietTypeEnum
from app.models.nutrition_goal import NutritionGoal
from app.models.user_profile import UserProfile

# ─── Constraint definitions ─────────────────────────────────────────────────────────

@dataclass
class PlannerConstraints:
    """The full constraint space for a daily plan."""

    # ── Required: calorie targets ──────────────────────────────────────────────
    daily_calorie_target: float  # From TDEE ± goal adjustment
    calorie_min: float          # Safety floor (never go below)
    calorie_max: float          # Safety ceiling (never go above)

    # ── Required: absolute macro targets ─────────────────────────────────────
    protein_target_g: float
    protein_target_g_min: float
    protein_target_g_max: float
    carbs_target_g: float
    carbs_target_g_min: float
    carbs_target_g_max: float
    fat_target_g: float
    fat_target_g_min: float
    fat_target_g_max: float

    # ── Required: diet & preferences ──────────────────────────────────────────
    diet_type: DietTypeEnum
    allergies: list[str]
    disliked_foods: list[str]
    preferred_foods: list[str]
    goal_type: str  # "giam_can", "giu_can", "tang_co"

    # ── Optional: macro ratio overrides ───────────────────────────────────────
    protein_pct_min: float = 0.15  # 15% of calories from protein minimum
    protein_pct_max: float = 0.35  # 35% maximum
    carbs_pct_min: float = 0.25    # 25% minimum
    carbs_pct_max: float = 0.60    # 60% maximum
    fat_pct_min: float = 0.15      # 15% minimum
    fat_pct_max: float = 0.35      # 35% maximum

    # ── Optional: yesterday context ───────────────────────────────────────────
    yesterday_calories: float = 0.0
    yesterday_over_target: float = 0.0  # positive if over, negative if under


@dataclass
class ConstraintViolation:
    """A single constraint violation."""
    field: str
    expected: str
    actual: str
    severity: str  # "error" (must fix) | "warning" (should fix)


@dataclass
class ValidationResult:
    """Result of constraint validation."""
    is_valid: bool
    violations: list[ConstraintViolation]
    warnings: list[str]
    # Fixed values (after auto-correction)
    fixed_calories: Optional[float] = None
    fixed_protein_g: Optional[float] = None
    fixed_carbs_g: Optional[float] = None
    fixed_fat_g: Optional[float] = None


# ─── Constraint builder ─────────────────────────────────────────────────────────────

def build_constraints_from_profile_and_goal(
    profile: UserProfile,
    goal: NutritionGoal,
    yesterday_calories: float = 0.0,
) -> PlannerConstraints:
    """
    Build the full constraint space from user profile and active goal.

    This is the authoritative way to get planning constraints.
    """
    daily_cal = float(goal.daily_calorie_target)
    weight = float(profile.current_weight_kg)

    # Safety floors
    calorie_min = max(1200, daily_cal * 0.75)   # Never go below 75% of target
    calorie_max = daily_cal * 1.15               # Never exceed 115% of target

    # If user was over yesterday, tighten today's budget
    yesterday_over_target = 0.0
    if yesterday_calories > daily_cal:
        over_by = yesterday_calories - daily_cal
        # Allow slightly more flexibility but not full compensation
        calorie_max = min(calorie_max, daily_cal * 1.05)
        yesterday_over_target = over_by

    # Protein: 1.6-2.2g per kg for most goals
    if goal.goal_type and goal.goal_type.value == "tang_co":
        protein_per_kg = 2.0
    elif goal.goal_type and goal.goal_type.value == "giam_can":
        protein_per_kg = 2.2  # Higher protein during cut to preserve muscle
    else:
        protein_per_kg = 1.8

    protein_g = protein_per_kg * weight
    protein_g_min = 0.80 * protein_g  # Allow 20% flexibility
    protein_g_max = 1.20 * protein_g

    # Carbs: remaining calories after protein + fat
    # Start with a reasonable fat target (25% of calories)
    fat_cals = daily_cal * 0.25
    fat_g = fat_cals / 9.0
    fat_g_min = fat_g * 0.80
    fat_g_max = fat_g * 1.20

    protein_cals = protein_g * 4.0
    remaining = daily_cal - protein_cals - fat_cals
    carbs_g = max(0, remaining / 4.0)
    carbs_g_min = carbs_g * 0.70
    carbs_g_max = carbs_g * 1.30

    # Parse allergies and dislikes
    allergies = _parse_text_list(profile.allergies)
    disliked = _parse_text_list(profile.disliked_foods)
    preferred = _parse_text_list(profile.preferred_foods)

    goal_type_str = goal.goal_type.value if hasattr(goal.goal_type, "value") else str(goal.goal_type)

    return PlannerConstraints(
        daily_calorie_target=round(daily_cal),
        calorie_min=round(calorie_min),
        calorie_max=round(calorie_max),
        protein_target_g=round(protein_g),
        protein_target_g_min=round(protein_g_min),
        protein_target_g_max=round(protein_g_max),
        carbs_target_g=round(carbs_g),
        carbs_target_g_min=round(carbs_g_min),
        carbs_target_g_max=round(carbs_g_max),
        fat_target_g=round(fat_g),
        fat_target_g_min=round(fat_g_min),
        fat_target_g_max=round(fat_g_max),
        diet_type=profile.diet_type,
        allergies=allergies,
        disliked_foods=disliked,
        preferred_foods=preferred,
        goal_type=goal_type_str,
        yesterday_calories=yesterday_calories,
        yesterday_over_target=yesterday_over_target,
    )


def _parse_text_list(text: str | None) -> list[str]:
    """Parse comma/semicolon/newline separated text into a list of strings."""
    if not text:
        return []
    separators = [",", ";", "\n", "\r\n"]
    result: list[str] = []
    for sep in separators:
        if sep in text:
            result = [s.strip().lower() for s in text.split(sep) if s.strip()]
            break
    if not result:
        result = [text.strip().lower()]
    return result


# ─── Validation engine ─────────────────────────────────────────────────────────────

def validate_recommendation(
    constraints: PlannerConstraints,
    calories_target: float | None,
    protein_g: float | None,
    carbs_g: float | None,
    fat_g: float | None,
) -> ValidationResult:
    """
    Validate AI-generated recommendation against constraints.

    Returns:
    - is_valid: True if all hard constraints are met
    - violations: List of hard constraint violations (must fix)
    - warnings: Soft issues (should fix but not critical)
    - fixed_values: Auto-corrected values for minor violations
    """
    violations: list[ConstraintViolation] = []
    warnings: list[str] = []

    cal = calories_target if calories_target is not None else constraints.daily_calorie_target
    prot = protein_g if protein_g is not None else constraints.protein_target_g
    carb = carbs_g if carbs_g is not None else constraints.carbs_target_g
    fat = fat_g if fat_g is not None else constraints.fat_target_g

    # ── Calorie validation ─────────────────────────────────────────────────────
    if cal < constraints.calorie_min:
        violations.append(ConstraintViolation(
            field="calories_target",
            expected=f">= {constraints.calorie_min} kcal",
            actual=f"{cal:.0f} kcal",
            severity="error",
        ))
        cal = constraints.calorie_min
    elif cal > constraints.calorie_max:
        violations.append(ConstraintViolation(
            field="calories_target",
            expected=f"<= {constraints.calorie_max} kcal",
            actual=f"{cal:.0f} kcal",
            severity="error",
        ))
        cal = constraints.calorie_max
    elif abs(cal - constraints.daily_calorie_target) > constraints.daily_calorie_target * 0.1:
        warnings.append(
            f"Calorie target ({cal:.0f}) deviates >10% from goal ({constraints.daily_calorie_target:.0f})."
        )

    # ── Macro validation ─────────────────────────────────────────────────────
    # Check protein
    if prot < constraints.protein_target_g_min:
        violations.append(ConstraintViolation(
            field="protein_target_g",
            expected=f">= {constraints.protein_target_g_min:.0f}g",
            actual=f"{prot:.0f}g",
            severity="warning",  # Warning for macro, error for calorie
        ))
        prot = constraints.protein_target_g_min
    elif prot > constraints.protein_target_g_max:
        warnings.append(
            f"Protein ({prot:.0f}g) exceeds target range. Consider reducing."
        )

    # Check carbs
    if carb < constraints.carbs_target_g_min:
        warnings.append(
            f"Carbs ({carb:.0f}g) below minimum ({constraints.carbs_target_g_min:.0f}g). "
            "This may affect energy levels."
        )
        carb = constraints.carbs_target_g_min

    # ── Diet type validation ─────────────────────────────────────────────────
    if constraints.diet_type == DietTypeEnum.an_chay or constraints.diet_type == DietTypeEnum.thuan_chay:
        warnings.append(
            "Diet type is vegetarian/vegan. Ensure meal suggestions exclude meat and animal products."
        )

    # ── Allergy warning ─────────────────────────────────────────────────────
    if constraints.allergies:
        warnings.append(
            f"Allergy considerations active: {', '.join(constraints.allergies)}. "
            "Meal suggestions should avoid these ingredients."
        )

    # ── Check if target respects yesterday's overconsumption ─────────────────
    if constraints.yesterday_over_target > 200:
        warnings.append(
            f"Yesterday exceeded target by {constraints.yesterday_over_target:.0f} kcal. "
            "Consider a slightly lower calorie target today."
        )

    is_valid = not any(v.severity == "error" for v in violations)

    return ValidationResult(
        is_valid=is_valid,
        violations=violations,
        warnings=warnings,
        fixed_calories=round(cal) if cal != (calories_target or constraints.daily_calorie_target) else None,
        fixed_protein_g=round(prot) if prot != (protein_g or constraints.protein_target_g) else None,
        fixed_carbs_g=round(carb) if carb != (carbs_g or constraints.carbs_target_g) else None,
        fixed_fat_g=round(fat) if fat != (fat_g or constraints.fat_target_g) else None,
    )


# ─── Constraint-guided prompt builder ──────────────────────────────────────────────

def build_constraint_guidance(constraints: PlannerConstraints) -> str:
    """
    Build a structured constraint string to include in the AI prompt.
    This tells the AI exactly what limits to respect.
    """
    goal_verb = {
        "giam_can": "giảm cân",
        "giu_can": "duy trì cân nặng",
        "tang_co": "tăng cơ",
    }.get(constraints.goal_type, "đạt mục tiêu")

    parts = [
        f"Người dùng đang có mục tiêu {goal_verb}.",
        f"Mục tiêu calo hàng ngày: {constraints.daily_calorie_target:.0f} kcal "
        f"(phạm vi: {constraints.calorie_min:.0f} - {constraints.calorie_max:.0f} kcal).",
        f"Mục tiêu protein: {constraints.protein_target_g:.0f}g "
        f"(phạm vi: {constraints.protein_target_g_min:.0f} - {constraints.protein_target_g_max:.0f}g).",
        f"Mục tiêu carbs: {constraints.carbs_target_g:.0f}g "
        f"(phạm vi: {constraints.carbs_target_g_min:.0f} - {constraints.carbs_target_g_max:.0f}g).",
        f"Mục tiêu fat: {constraints.fat_target_g:.0f}g "
        f"(phạm vi: {constraints.fat_target_g_min:.0f} - {constraints.fat_target_g_max:.0f}g).",
    ]

    if constraints.diet_type and constraints.diet_type != DietTypeEnum.binh_thuong:
        diet_name = {
            DietTypeEnum.an_chay: "Ăn chay (không thịt động vật)",
            DietTypeEnum.thuan_chay: "Thuần chay (không sản phẩm động vật)",
            DietTypeEnum.keto: "Keto (rất ít carb, nhiều fat)",
            DietTypeEnum.it_tinh_bot: "Ít tinh bột",
            DietTypeEnum.nhieu_dam: "Nhiều đạm",
            DietTypeEnum.khac: "Chế độ khác",
        }.get(constraints.diet_type, str(constraints.diet_type))
        parts.append(f"Chế độ ăn: {diet_name}.")

    if constraints.allergies:
        parts.append(f"LƯU Ý DỊ ỨNG: Không đề xuất món chứa: {', '.join(constraints.allergies)}.")

    if constraints.disliked_foods:
        parts.append(f"Thực phẩm người dùng không thích: {', '.join(constraints.disliked_foods[:5])}. Tránh các món này.")

    if constraints.preferred_foods:
        parts.append(f"Ưu tiên các món: {', '.join(constraints.preferred_foods[:5])}.")

    if constraints.yesterday_over_target > 200:
        parts.append(
            f"Hôm qua người dùng ăn vượt {constraints.yesterday_over_target:.0f} kcal. "
            f"Cân nhắc giảm nhẹ calo hôm nay."
        )

    return "\n".join(parts)
