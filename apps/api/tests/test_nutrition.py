"""Unit tests cho nutrition_service.py — không cần DB, chỉ test logic tính toán."""
from datetime import date
from unittest.mock import MagicMock

from app.models.enums import ActivityLevelType, GenderType, NutritionGoalType
from app.services.nutrition_service import (
    calculate_age,
    calculate_bmr,
    calculate_nutrition_targets,
    calculate_tdee,
)


class TestCalculateAge:
    def test_age_exact_birthday(self):
        today = date.today()
        dob = date(today.year - 25, today.month, today.day)
        assert calculate_age(dob) == 25

    def test_age_before_birthday(self):
        today = date.today()
        # Sinh nhật chưa tới trong năm nay
        if today.month < 12:
            dob = date(today.year - 25, today.month + 1, 1)
            assert calculate_age(dob) == 24
        else:
            dob = date(today.year - 25, 1, 1)
            assert calculate_age(dob) == 25


class TestCalculateBMR:
    def test_bmr_male(self):
        """Mifflin-St Jeor: nam 70kg, 175cm, 25t = 10*70 + 6.25*175 - 5*25 + 5 = 1_673.75"""
        bmr = calculate_bmr(70, 175, 25, GenderType.nam)
        assert abs(bmr - 1673.75) < 0.01

    def test_bmr_female(self):
        """Nữ: 10*55 + 6.25*160 - 5*30 - 161 = 1_239"""
        bmr = calculate_bmr(55, 160, 30, GenderType.nu)
        assert abs(bmr - 1239.0) < 0.01

    def test_bmr_other_gender(self):
        """Khác: trung bình nam-nữ → base - 78"""
        bmr = calculate_bmr(70, 175, 25, GenderType.khac)
        expected = (10 * 70) + (6.25 * 175) - (5 * 25) - 78
        assert abs(bmr - expected) < 0.01


class TestCalculateTDEE:
    def test_sedentary(self):
        assert calculate_tdee(1500, ActivityLevelType.it_van_dong) == 1500 * 1.2

    def test_very_active(self):
        assert calculate_tdee(1500, ActivityLevelType.van_dong_rat_nhieu) == 1500 * 1.9


class TestCalculateNutritionTargets:
    def _make_profile(self, gender=GenderType.nam, weight=70, height=175, age_years=25,
                      activity=ActivityLevelType.van_dong_vua):
        """Tạo mock UserProfile."""
        profile = MagicMock()
        profile.gender = gender
        profile.current_weight_kg = weight
        profile.height_cm = height
        today = date.today()
        profile.date_of_birth = date(today.year - age_years, today.month, today.day)
        profile.activity_level = activity
        return profile

    def test_weight_loss_calories_below_tdee(self):
        profile = self._make_profile()
        result = calculate_nutrition_targets(profile, NutritionGoalType.giam_can)
        assert result["daily_calorie_target"] < result["tdee_kcal"]
        assert result["daily_calorie_target"] == round(result["tdee_kcal"] - 500)

    def test_muscle_gain_calories_above_tdee(self):
        profile = self._make_profile()
        result = calculate_nutrition_targets(profile, NutritionGoalType.tang_co)
        assert result["daily_calorie_target"] > result["tdee_kcal"]

    def test_maintain_calories_equals_tdee(self):
        profile = self._make_profile()
        result = calculate_nutrition_targets(profile, NutritionGoalType.giu_can)
        assert result["daily_calorie_target"] == round(result["tdee_kcal"])

    def test_minimum_safe_calories_female(self):
        """Nữ không được dưới 1200 kcal."""
        profile = self._make_profile(gender=GenderType.nu, weight=45, height=150, age_years=50,
                                     activity=ActivityLevelType.it_van_dong)
        result = calculate_nutrition_targets(profile, NutritionGoalType.giam_can)
        assert result["daily_calorie_target"] >= 1200

    def test_minimum_safe_calories_male(self):
        """Nam không được dưới 1500 kcal."""
        profile = self._make_profile(gender=GenderType.nam, weight=55, height=160, age_years=60,
                                     activity=ActivityLevelType.it_van_dong)
        result = calculate_nutrition_targets(profile, NutritionGoalType.giam_can)
        assert result["daily_calorie_target"] >= 1500

    def test_macros_sum_to_total_calories(self):
        """Protein*4 + Carb*4 + Fat*9 ≈ daily_calorie_target."""
        profile = self._make_profile()
        result = calculate_nutrition_targets(profile, NutritionGoalType.giu_can)

        protein_cals = result["protein_target_g"] * 4
        carb_cals = result["carb_target_g"] * 4
        fat_cals = result["fat_target_g"] * 9
        total = protein_cals + carb_cals + fat_cals

        # Allow rounding tolerance of ±10 kcal
        assert abs(total - result["daily_calorie_target"]) < 10

    def test_result_has_all_keys(self):
        profile = self._make_profile()
        result = calculate_nutrition_targets(profile, NutritionGoalType.giu_can)
        expected_keys = {"bmi", "bmr_kcal", "tdee_kcal", "daily_calorie_target",
                         "protein_target_g", "carb_target_g", "fat_target_g"}
        assert expected_keys == set(result.keys())
