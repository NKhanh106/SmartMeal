from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.meal import MealItemCreate
from app.schemas.user_profile import UserProfileCreate
from app.services.meal_service import calculate_item_nutrition


def test_user_profile_rejects_future_birth_date():
    with pytest.raises(ValidationError):
        UserProfileCreate(
            gender="nam",
            date_of_birth=date.today() + timedelta(days=1),
            height_cm=Decimal("175"),
            current_weight_kg=Decimal("70"),
        )


def test_user_profile_rejects_invalid_height():
    with pytest.raises(ValidationError):
        UserProfileCreate(
            gender="nam",
            date_of_birth="1998-06-10",
            height_cm=Decimal("20"),
            current_weight_kg=Decimal("70"),
        )


def test_meal_item_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        MealItemCreate(
            food_nutrition_id=None,
            estimated_weight_g=Decimal("100"),
            confidence=Decimal("1.5"),
        )


def test_calculate_item_nutrition_scales_by_weight():
    food = SimpleNamespace(
        calories_per_100g=200,
        protein_per_100g=10,
        carb_per_100g=20,
        fat_per_100g=5,
    )

    result = calculate_item_nutrition(food, Decimal("150"))

    assert result["calories"] == Decimal("300.00")
    assert result["protein_g"] == Decimal("15.00")
    assert result["carb_g"] == Decimal("30.00")
    assert result["fat_g"] == Decimal("7.50")
