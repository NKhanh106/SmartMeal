from datetime import date
from typing import Any, Dict

from app.models.enums import ActivityLevelType, GenderType, NutritionGoalType
from app.models.user_profile import UserProfile


def calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: GenderType) -> float:
    """Công thức Mifflin-St Jeor"""
    # Base: 10 * weight + 6.25 * height - 5 * age
    base_bmr = (10.0 * float(weight_kg)) + (6.25 * float(height_cm)) - (5.0 * age)
    
    if gender == GenderType.nam:
        return base_bmr + 5
    elif gender == GenderType.nu:
        return base_bmr - 161
    else:
        # Trung hòa cho 'khac' hoặc 'khong_muon_noi'
        return base_bmr - 78

def calculate_tdee(bmr: float, activity_level: ActivityLevelType) -> float:
    # Sedentary (Ít vận động)
    if activity_level == ActivityLevelType.it_van_dong:
        return bmr * 1.2
    # Lightly active (Vận động nhẹ: 1-3 ngày/tuần)
    elif activity_level == ActivityLevelType.van_dong_nhe:
        return bmr * 1.375
    # Moderately active (Vận động vừa: 3-5 ngày/tuần)
    elif activity_level == ActivityLevelType.van_dong_vua:
        return bmr * 1.55
    # Very active (Vận động nhiều: 6-7 ngày/tuần)
    elif activity_level == ActivityLevelType.van_dong_nhieu:
        return bmr * 1.725
    # Extra active (Vận động rất nhiều: PT, Vận động viên)
    elif activity_level == ActivityLevelType.van_dong_rat_nhieu:
        return bmr * 1.9
    
    return bmr * 1.2

def calculate_nutrition_targets(profile: UserProfile, goal_type: NutritionGoalType) -> Dict[str, Any]:
    """Tính toán toàn bộ các chỉ số về calo và macros dựa trên profile"""
    
    age = calculate_age(profile.date_of_birth)
    weight = float(profile.current_weight_kg)
    height = float(profile.height_cm)
    
    # 1. BMI
    height_m = height / 100.0
    bmi = weight / (height_m ** 2)
    
    # 2. BMR & TDEE
    bmr = calculate_bmr(weight, height, age, profile.gender)
    tdee = calculate_tdee(bmr, profile.activity_level)
    
    # 3. Calo mục tiêu
    target_calories = tdee
    if goal_type == NutritionGoalType.giam_can:
        target_calories = tdee - 500
    elif goal_type == NutritionGoalType.tang_co:
        target_calories = tdee + 300
    # giu_can giữ nguyên TDEE
    
    # Không để calo xuống mức quá nguy hiểm (vd: < 1200 cho nữ, < 1500 cho nam)
    min_safe_cals = 1500 if profile.gender == GenderType.nam else 1200
    target_calories = max(target_calories, min_safe_cals)
    
    # 4. Tính Macros an toàn (Rule đơn giản như yêu cầu MVP)
    # Protein = 2.0g x weight_kg (Góp phần tăng cơ / giữ cơ khi giảm mỡ)
    protein_g = 2.0 * weight
    protein_cals = protein_g * 4
    
    # Fat = 25% tổng calo = target_calories * 0.25 / 9
    fat_cals = target_calories * 0.25
    fat_g = fat_cals / 9
    
    # Carb = Calo còn lại / 4
    carb_cals = target_calories - protein_cals - fat_cals
    carb_g = carb_cals / 4 if carb_cals > 0 else 0
    
    return {
        "bmi": round(bmi, 2),
        "bmr_kcal": round(bmr),
        "tdee_kcal": round(tdee),
        "daily_calorie_target": round(target_calories),
        "protein_target_g": round(protein_g),
        "carb_target_g": round(carb_g),
        "fat_target_g": round(fat_g)
    }
