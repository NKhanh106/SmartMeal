"""
Nutrition Math Engine — algorithmic TDEE / macro calculator.

Provides deterministic, mathematically accurate calculations for meal planning.
Designed to be called BEFORE the LLM generates Vietnamese meal suggestions.

Formulas:
  - BMR:   Mifflin-St Jeor (most accurate for modern populations)
  - TDEE:  BMR × activity multiplier
  - Macro: golden-ratio split tuned for Vietnamese/Asian diets

Usage:
    from app.services.nutrition_math import calculate_macro_targets

    result = calculate_macro_targets(
        weight_kg=65,
        height_cm=170,
        age=25,
        gender="male",
        activity_level="moderate",
        nutrition_goal_type="deficit",
    )
"""

from enum import Enum

from pydantic import BaseModel, Field


class ActivityLevel(str, Enum):
    SEDENTARY     = "sedentary"
    LIGHT         = "light"
    MODERATE      = "moderate"
    ACTIVE        = "active"
    VERY_ACTIVE   = "very_active"


class NutritionGoalType(str, Enum):
    DEFICIT  = "deficit"
    SURPLUS  = "surplus"
    MAINTAIN = "maintain"


# ── Constants ──────────────────────────────────────────────────────────────────

# Activity multipliers — Katch-McArdle-adjacent values for Mifflin-St Jeor
ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY:   1.200,
    ActivityLevel.LIGHT:       1.375,
    ActivityLevel.MODERATE:    1.550,
    ActivityLevel.ACTIVE:      1.725,
    ActivityLevel.VERY_ACTIVE: 1.900,
}

# Gender constants for Mifflin-St Jeor (s coefficient)
MALE_S   = +5
FEMALE_S = -161

# Caloric adjustments per goal
DEFICIT_CAL_ADJUSTMENT  = -500  # kcal — conservative cut, preserves muscle
SURPLUS_CAL_ADJUSTMENT  = +300  # kcal — lean bulk
MAINTENANCE_CAL_ADJUSTMENT = 0  # kcal

# Macro split — golden-ratio inspired, tuned for Vietnamese/Asian diet
# Protein: 2.0 g/kg body weight (muscle preservation during deficit)
# Fat:     25% of total calories  (brain health, satiety)
# Carb:    remainder              (performance, cultural staples)
PROTEIN_G_PER_KG      = 2.0
FAT_PERCENTAGE         = 0.25
KCAL_PER_G_PROTEIN    = 4
KCAL_PER_G_CARB       = 4
KCAL_PER_G_FAT        = 9

# Minimum calorie floor during deficit — never go below BMR
MINIMUM_CALORIE_FLOOR_FACTOR = 1.0  # BMR × 1.0 (no deficit below BMR)

# Upper sanity bounds — prevent absurd values from reaching the database
# A-5 fix: no upper bound on TDEE/macros was a MEDIUM risk
MAX_REASONABLE_CALORIES = 6000   # kcal — base cap; dynamically scaled for extreme obesity
MAX_REASONABLE_PROTEIN_G = 300   # g/day
MAX_REASONABLE_FAT_G = 200        # g/day
MAX_REASONABLE_CARB_G = 900      # g/day


# ── Schema ─────────────────────────────────────────────────────────────────────


class MacroTargets(BaseModel):
    """Output schema for the TDEE / macro calculation tool."""

    bmr: float = Field(..., description="Basal Metabolic Rate (kcal/day)")
    tdee: float = Field(..., description="Total Daily Energy Expenditure (kcal/day)")
    target_calories: float = Field(
        ...,
        description="Adjusted target calories based on nutrition goal"
    )
    protein_g: float = Field(..., description="Daily protein target in grams")
    carb_g: float = Field(..., description="Daily carbohydrate target in grams")
    fat_g: float = Field(..., description="Daily fat target in grams")

    class Config:
        json_schema_extra = {
            "example": {
                "bmr": 1585.0,
                "tdee": 2457.0,
                "target_calories": 1957.0,
                "protein_g": 130.0,
                "carb_g": 244.0,
                "fat_g": 54.0,
            }
        }


class MacroCalculationResult(BaseModel):
    """Extended result with metadata for the agent."""

    macros: MacroTargets
    weight_kg: float
    height_cm: float
    age: int
    gender: str
    activity_level: str
    goal_type: str
    calculation_method: str = "mifflin_st_jeor"
    calorie_floor: float = Field(
        ...,
        description="Minimum safe calories (BMR) enforced during deficit"
    )
    calories_from_protein: float
    calories_from_fat: float
    calories_from_carb: float
    is_using_floor: bool = Field(
        False,
        description="True if target was clamped to calorie floor"
    )


# ── Core calculation ───────────────────────────────────────────────────────────


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """
    Mifflin-St Jeor Equation.

    BMR = 10 × weight(kg) + 6.25 × height(cm) - 5 × age + s

    s = +5  for male
    s = -161 for female
    """
    s = MALE_S if gender.lower() in ("male", "nam", "m") else FEMALE_S
    return 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age + s


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    Multiply BMR by activity multiplier to get TDEE.
    Defaults to MODERATE if activity_level is unrecognized.
    """
    multiplier = ACTIVITY_MULTIPLIERS.get(
        ActivityLevel(activity_level.lower()),
        ACTIVITY_MULTIPLIERS[ActivityLevel.MODERATE],
    )
    return round(bmr * multiplier, 1)


def apply_goal_adjustment(tdee: float, bmr: float, goal_type: str) -> float:
    """
    Adjust TDEE based on nutrition goal.

    - deficit:  TDEE - 500, clamped to minimum BMR
    - surplus:  TDEE + 300
    - maintain: TDEE
    """
    goal = goal_type.lower()

    if goal == "deficit":
        adjustment = DEFICIT_CAL_ADJUSTMENT
        raw_target = tdee + adjustment
        # FIX-9: Align math floor with data_writers.MIN_DAILY_CALORIES hard floor (1000 kcal).
        clinical_min = max(raw_target, bmr * MINIMUM_CALORIE_FLOOR_FACTOR, 1000)
        return clinical_min

    if goal == "surplus":
        return tdee + SURPLUS_CAL_ADJUSTMENT

    # maintain
    return float(tdee)


def calculate_macros(target_calories: float, weight_kg: float) -> tuple[float, float, float]:
    """
    Golden-ratio macro split for Vietnamese/Asian diets.

    Protein: 2.0 g/kg body weight
    Fat:     25% of target calories
    Carb:    remaining calories

    Returns (protein_g, carb_g, fat_g).
    """
    protein_g = round(weight_kg * PROTEIN_G_PER_KG, 1)

    calories_from_protein = protein_g * KCAL_PER_G_PROTEIN
    calories_from_fat     = target_calories * FAT_PERCENTAGE
    fat_g                = round(calories_from_fat / KCAL_PER_G_FAT, 1)

    calories_from_carb    = target_calories - calories_from_protein - calories_from_fat
    carb_g                = round(max(calories_from_carb, 0) / KCAL_PER_G_CARB, 1)

    return protein_g, carb_g, fat_g


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_macro_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str = "moderate",
    nutrition_goal_type: str = "maintain",
) -> MacroCalculationResult:
    """
    Full TDEE + macro calculation pipeline.

    Args:
        weight_kg:          Body weight in kilograms
        height_cm:          Height in centimetres
        age:                Age in years
        gender:             "male" or "female" (case-insensitive)
        activity_level:     One of sedentary | light | moderate | active | very_active
        nutrition_goal_type: One of deficit | surplus | maintain

    Returns:
        MacroCalculationResult with detailed breakdown.

    Raises:
        ValueError: If inputs are invalid (zero/negative dimensions, unknown enums).
    """
    # ── Input validation ───────────────────────────────────────────────────────
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError(
            f"weight_kg ({weight_kg}), height_cm ({height_cm}), and age ({age}) "
            "must all be positive numbers."
        )

    gender_clean = gender.strip().lower()
    if gender_clean not in ("male", "female", "nam", "nu"):
        raise ValueError(
            f"gender must be 'male' or 'female' (got: '{gender}')."
        )

    # ── Step 1: BMR ─────────────────────────────────────────────────────────────
    bmr = calculate_bmr(weight_kg, height_cm, age, gender_clean)

    # ── Step 2: TDEE ────────────────────────────────────────────────────────────
    tdee = calculate_tdee(bmr, activity_level)

    # ── Step 3: Goal-adjusted calories ─────────────────────────────────────────
    target_calories_raw = apply_goal_adjustment(tdee, bmr, nutrition_goal_type)
    target_calories = round(target_calories_raw, 1)

    is_using_floor = (
        nutrition_goal_type.lower() == "deficit"
        and target_calories_raw < tdee + DEFICIT_CAL_ADJUSTMENT
    )

    # ── Step 4: Macro split ────────────────────────────────────────────────────
    protein_g, carb_g, fat_g = calculate_macros(target_calories, weight_kg)

    # ── A-5 fix: Upper sanity bounds on computed values ───────────────────────
    # FIX-9: Scale max dynamically for extreme hyper-obesity profiles
    dynamic_max_cal = max(6000, int(bmr * 1.5))
    protein_g = min(protein_g, MAX_REASONABLE_PROTEIN_G)
    fat_g = min(fat_g, MAX_REASONABLE_FAT_G)
    carb_g = min(carb_g, MAX_REASONABLE_CARB_G)
    target_calories = min(target_calories, dynamic_max_cal)

    # ── Step 5: Build result ───────────────────────────────────────────────────
    macros = MacroTargets(
        bmr=round(bmr, 1),
        tdee=tdee,
        target_calories=target_calories,
        protein_g=protein_g,
        carb_g=carb_g,
        fat_g=fat_g,
    )

    return MacroCalculationResult(
        macros=macros,
        weight_kg=weight_kg,
        height_cm=height_cm,
        age=age,
        gender=gender_clean,
        activity_level=activity_level,
        goal_type=nutrition_goal_type,
        calorie_floor=round(bmr * MINIMUM_CALORIE_FLOOR_FACTOR, 1),
        calories_from_protein=round(protein_g * KCAL_PER_G_PROTEIN, 1),
        calories_from_fat=round(fat_g * KCAL_PER_G_FAT, 1),
        calories_from_carb=round(carb_g * KCAL_PER_G_CARB, 1),
        is_using_floor=is_using_floor,
    )
