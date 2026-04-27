from decimal import ROUND_HALF_UP, Decimal

from app.models.food_nutrition import FoodNutrition


def round_decimal(value: Decimal, places: str = "0.01") -> Decimal:
    """Làm tròn số thập phân đến n chữ số (mặc định 2 chữ số)."""
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)

def calculate_nutrition_by_weight(food: FoodNutrition, weight_g: Decimal) -> dict:
    """
    Tính dinh dưỡng theo khối lượng thực tế.
    """
    ratio = weight_g / Decimal("100")

    calories = Decimal(str(food.calories_per_100g)) * ratio
    protein_g = Decimal(str(food.protein_per_100g)) * ratio
    carb_g = Decimal(str(food.carb_per_100g)) * ratio
    fat_g = Decimal(str(food.fat_per_100g)) * ratio

    fiber_g = None
    sugar_g = None
    sodium_mg = None

    if food.fiber_per_100g is not None:
        fiber_g = Decimal(str(food.fiber_per_100g)) * ratio

    if food.sugar_per_100g is not None:
        sugar_g = Decimal(str(food.sugar_per_100g)) * ratio

    if food.sodium_mg_per_100g is not None:
        sodium_mg = Decimal(str(food.sodium_mg_per_100g)) * ratio

    return {
        "food_id": food.id,
        "food_name": food.food_name, 
        "weight_g": round_decimal(weight_g),
        "calories": round_decimal(calories),
        "protein_g": round_decimal(protein_g),
        "carb_g": round_decimal(carb_g),
        "fat_g": round_decimal(fat_g),
        "fiber_g": round_decimal(fiber_g) if fiber_g is not None else None,
        "sugar_g": round_decimal(sugar_g) if sugar_g is not None else None,
        "sodium_mg": round_decimal(sodium_mg) if sodium_mg is not None else None,
    }
