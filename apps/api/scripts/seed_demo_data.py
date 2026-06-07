"""
Seed script: Tạo 10 người dùng với dữ liệu 10 ngày.
Bao gồm: người béo phì, thiếu cân, sinh hoạt không tốt.

Chạy: python -m scripts.seed_demo_data
"""

import asyncio
import random
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, engine
from app.models.chat import ChatMessage, ChatSession
from app.models.conversation_insight import ConversationInsight
from app.models.meal import MealItem, MealLog
from app.models.nutrition_goal import NutritionGoal
from app.models.progress_log import ProgressLog
from app.models.user import User
from app.models.user_memory import UserMemory
from app.models.user_profile import UserProfile
from app.models.enums import (
    ActivityLevelType,
    CookingPreferenceEnum,
    DietTypeEnum,
    GenderType,
    ItemSourceType,
    MealFrequencyEnum,
    MealTypeEnum,
    NutritionGoalType,
    SleepQualityEnum,
    UsageGoalEnum,
)


# ─── Món ăn với macro ────────────────────────────────────────────────────────

FOOD_DB = {
    # Bữa sáng
    "pho_bo":          {"cal": 450, "protein": 25, "carb": 55, "fat": 14, "weight": 400},
    "banh_mi_thit":    {"cal": 350, "protein": 15, "carb": 40, "fat": 14, "weight": 200},
    "xoi_man":         {"cal": 500, "protein": 12, "carb": 70, "fat": 18, "weight": 350},
    "bun_cha":         {"cal": 480, "protein": 22, "carb": 52, "fat": 18, "weight": 400},
    "com_tam":         {"cal": 550, "protein": 28, "carb": 60, "fat": 20, "weight": 400},
    "banh_bao":        {"cal": 300, "protein": 12, "carb": 40, "fat": 10, "weight": 200},
    "chao_ga":         {"cal": 320, "protein": 18, "carb": 38, "fat": 10, "weight": 350},
    "oatmeal_sua":     {"cal": 280, "protein": 12, "carb": 40, "fat": 7,  "weight": 250},
    "trung_chien_toi": {"cal": 200, "protein": 12, "carb": 3,  "fat": 16, "weight": 120},
    "sua_chua_hoa_qua":{"cal": 180, "protein": 8,  "carb": 25, "fat": 5,  "weight": 200},

    # Bữa trưa / tối
    "com_chay":        {"cal": 420, "protein": 15, "carb": 65, "fat": 10, "weight": 450},
    "thit_kho_trung":  {"cal": 600, "protein": 35, "carb": 30, "fat": 38, "weight": 350},
    "ca_kho_to":       {"cal": 480, "protein": 40, "carb": 20, "fat": 28, "weight": 300},
    "ga_chien":        {"cal": 550, "protein": 35, "carb": 30, "fat": 35, "weight": 350},
    "rau_xao_bo":      {"cal": 320, "protein": 22, "carb": 15, "fat": 18, "weight": 300},
    "sup_ga":          {"cal": 250, "protein": 20, "carb": 15, "fat": 12, "weight": 350},
    "salad_ga":        {"cal": 300, "protein": 25, "carb": 18, "fat": 14, "weight": 350},
    "bun_dau_mam_tom": {"cal": 520, "protein": 22, "carb": 60, "fat": 22, "weight": 450},
    "lau_thai":        {"cal": 700, "protein": 40, "carb": 55, "fat": 35, "weight": 600},
    "nuoc_leo":        {"cal": 350, "protein": 18, "carb": 40, "fat": 12, "weight": 400},

    # Ăn vặt / phụ
    "banh_keo":        {"cal": 150, "protein": 2,  "carb": 25, "fat": 5,  "weight": 50},
    "tra_sua":         {"cal": 300, "protein": 3,  "carb": 55, "fat": 8,  "weight": 400},
    "sua_chua":        {"cal": 120, "protein": 8,  "carb": 15, "fat": 3,  "weight": 180},
    "hoa_qua":         {"cal": 80,  "protein": 1,  "carb": 18, "fat": 0,  "weight": 150},
    "hat_dieu":        {"cal": 200, "protein": 6,  "carb": 8,  "fat": 18, "weight": 40},
    "banh_plan":       {"cal": 180, "protein": 3,  "carb": 28, "fat": 6,  "weight": 50},
    "tra_da":          {"cal": 80,  "protein": 0,  "carb": 18, "fat": 0,  "weight": 400},
    "ca_phe_sua":      {"cal": 200, "protein": 5,  "carb": 25, "fat": 8,  "weight": 250},
    "banh_tet":        {"cal": 350, "protein": 5,  "carb": 55, "fat": 12, "weight": 150},
    "kem":             {"cal": 280, "protein": 4,  "carb": 30, "fat": 16, "weight": 120},

    # Món chay
    "com_chay_chi":    {"cal": 400, "protein": 12, "carb": 60, "fat": 12, "weight": 400},
    "dau_hu_chien":    {"cal": 280, "protein": 18, "carb": 15, "fat": 18, "weight": 200},
    "rau_muong_xao":   {"cal": 180, "protein": 8,  "carb": 10, "fat": 12, "weight": 250},
    "canh_chua":       {"cal": 200, "protein": 12, "carb": 20, "fat": 8,  "weight": 400},
}

BREAKFAST_FOODS   = ["pho_bo", "banh_mi_thit", "xoi_man", "bun_cha", "com_tam",
                     "banh_bao", "chao_ga", "oatmeal_sua", "trung_chien_toi", "sua_chua_hoa_qua"]
LUNCH_FOODS       = ["com_chay", "thit_kho_trung", "ca_kho_to", "ga_chien",
                     "rau_xao_bo", "sup_ga", "salad_ga", "bun_dau_mam_tom", "nuoc_leo"]
DINNER_FOODS      = ["lau_thai", "thit_kho_trung", "ca_kho_to", "ga_chien",
                     "sup_ga", "bun_dau_mam_tom", "com_chay", "salad_ga"]
SNACK_FOODS       = ["banh_keo", "tra_sua", "sua_chua", "hoa_qua", "hat_dieu",
                     "banh_plan", "tra_da", "ca_phe_sua", "banh_tet", "kem"]
CHAY_FOODS        = ["com_chay", "com_chay_chi", "dau_hu_chien", "rau_muong_xao",
                     "canh_chua", "oatmeal_sua", "sua_chua_hoa_qua", "sup_ga"]


# ─── 10 hồ sơ người dùng mẫu ─────────────────────────────────────────────────

USERS = [
    # 1. Béo phì, ít vận động, ăn nhiều snack, nhân viên bán lẻ
    dict(
        full_name="Nguyen Van A",
        gender=GenderType.nam,
        dob=date(1995, 5, 10),
        height_cm=170.0,
        weight_kg=95.0,
        body_fat_percent=32.0,
        waist_cm=102.0,
        neck_cm=40.0,
        activity=ActivityLevelType.it_van_dong,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.giam_can,
        usage_goal=UsageGoalEnum.weight_loss,
        target_weight=80.0,
        # JSONB fields
        allergies=[{"id": "alg_1", "allergen": "hải sản", "severity": "nhẹ", "category": "seafood"}],
        dietary_restrictions=[],
        medications=[],
        health_conditions=[{"id": "cond_1", "name": "prehypertension", "severity": "nhẹ", "status": "managed"}],
        # Lifestyle
        sleep_duration_hours=6.0,
        sleep_quality=SleepQualityEnum.poor,
        sleep_schedule="23:00-06:00",
        stress_level=7,
        meal_frequency=MealFrequencyEnum.three_meals,
        cooking_preference=CookingPreferenceEnum.eat_out,
        wake_up_time="06:30",
        sleep_time="23:30",
        work_schedule="08:00-20:00, 6 ngày/tuần",
        # Taste & food
        taste_preferences={"spicy": "thích", "sweet": "thích", "salty": "thích", "sour": "trung bình", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}],
        disliked_foods=[{"id": "d_1", "food": "rau xanh", "reason": "không thích"}],
        favorite_foods=[{"id": "f_1", "food": "thịt heo chiên giòn", "preference": "rất thích"}, {"id": "f_2", "food": "nước ngọt", "preference": "thích"}, {"id": "f_3", "food": "bánh kẹo", "preference": "thích"}],
        disliked_foods_text="rau xanh",
        preferred_foods_text="thịt heo, đồ chiên, nước ngọt, bánh kẹo",
        allergies_text="dị ứng hải sản nhẹ",
        eating_speed="nhanh",
        chew_difficulty=False,
        # Body / memory
        energy_level="low",
        hydration="low",
        weight_trend="tăng",
        fitness_level="beginner",
        lifestyle_score=2,
        recent_symptoms=[{"date": (date.today() - timedelta(days=3)).isoformat(), "symptom": "mệt buổi chiều", "severity": "nhẹ"}],
        health_events_seed=[{"date": (date.today() - timedelta(days=5)).isoformat(), "type": "symptom", "category": "metabolic", "description": "Uống nhiều nước ngọt, buổi chiều thấy mệt", "severity": "mild", "resolved": True}],
    ),
    # 2. Béo phì, vận động vừa, ăn kiêng, mẹ đơn thân đi làm
    dict(
        full_name="Tran Thi B",
        gender=GenderType.nu,
        dob=date(1990, 8, 22),
        height_cm=158.0,
        weight_kg=78.0,
        body_fat_percent=38.0,
        waist_cm=92.0,
        neck_cm=33.0,
        hip_cm=104.0,
        activity=ActivityLevelType.van_dong_vua,
        diet=DietTypeEnum.nhieu_dam,
        goal_type=NutritionGoalType.giam_can,
        usage_goal=UsageGoalEnum.weight_loss,
        target_weight=58.0,
        allergies=[],
        dietary_restrictions=[],
        medications=[{"id": "med_1", "name": "thuốc tránh thai", "dosage": "hàng ngày", "frequency": "hàng ngày"}],
        health_conditions=[{"id": "cond_1", "name": "postpartum_recovery", "severity": "nhẹ", "status": "recovered"}],
        sleep_duration_hours=5.5,
        sleep_quality=SleepQualityEnum.fair,
        sleep_schedule="22:30-05:30",
        stress_level=8,
        meal_frequency=MealFrequencyEnum.four_meals,
        cooking_preference=CookingPreferenceEnum.home_cooked,
        wake_up_time="05:30",
        sleep_time="22:30",
        work_schedule="07:00-17:00, 5 ngày/tuần",
        taste_preferences={"spicy": "trung bình", "sweet": "không thích", "salty": "trung bình", "sour": "thích", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}, {"id": "c_2", "name": "Hàn Quốc", "preference": "thích"}],
        disliked_foods=[{"id": "d_1", "food": "đậu phộng", "reason": "không thích"}],
        favorite_foods=[{"id": "f_1", "food": "thịt bò", "preference": "rất thích"}, {"id": "f_2", "food": "rau củ", "preference": "thích"}, {"id": "f_3", "food": "cà phê", "preference": "thích"}],
        disliked_foods_text="đậu phộng",
        preferred_foods_text="thịt bò, rau củ, cà phê",
        allergies_text=None,
        eating_speed="bình thường",
        chew_difficulty=False,
        energy_level="normal",
        hydration="normal",
        weight_trend="giảm chậm",
        fitness_level="intermediate",
        lifestyle_score=6,
        recent_symptoms=[],
        health_events_seed=[],
    ),
    # 3. Thiếu cân, ăn ít, sinh viên tự kỷ
    dict(
        full_name="Le Van C",
        gender=GenderType.nam,
        dob=date(1998, 1, 15),
        height_cm=175.0,
        weight_kg=52.0,
        body_fat_percent=12.0,
        waist_cm=68.0,
        neck_cm=34.0,
        activity=ActivityLevelType.van_dong_nhe,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.tang_co,
        usage_goal=UsageGoalEnum.weight_gain,
        target_weight=68.0,
        allergies=[],
        dietary_restrictions=[],
        medications=[],
        health_conditions=[{"id": "cond_1", "name": "underweight", "severity": "vừa", "status": "monitored"}],
        sleep_duration_hours=7.5,
        sleep_quality=SleepQualityEnum.good,
        sleep_schedule="00:00-07:30",
        stress_level=5,
        meal_frequency=MealFrequencyEnum.two_meals,
        cooking_preference=CookingPreferenceEnum.eat_out,
        wake_up_time="07:30",
        sleep_time="00:00",
        work_schedule="08:00-16:00, 5 ngày/tuần (thực tập)",
        taste_preferences={"spicy": "thích", "sweet": "rất thích", "salty": "trung bình", "sour": "trung bình", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}, {"id": "c_2", "name": "Nhanh (fast food)", "preference": "thích"}],
        disliked_foods=[{"id": "d_1", "food": "sữa", "reason": "không thích vị"}],
        favorite_foods=[{"id": "f_1", "food": "cơm", "preference": "rất thích"}, {"id": "f_2", "food": "thịt", "preference": "rất thích"}, {"id": "f_3", "food": "bánh ngọt", "preference": "thích"}],
        disliked_foods_text="sữa",
        preferred_foods_text="cơm, thịt, bánh ngọt",
        allergies_text=None,
        eating_speed="nhanh",
        chew_difficulty=False,
        energy_level="low",
        hydration="normal",
        weight_trend="ổn định",
        fitness_level="beginner",
        lifestyle_score=5,
        recent_symptoms=[{"date": (date.today() - timedelta(days=1)).isoformat(), "symptom": "chóng mặt buổi sáng", "severity": "nhẹ"}],
        health_events_seed=[{"date": (date.today() - timedelta(days=1)).isoformat(), "type": "symptom", "category": "metabolic", "description": "Chóng mặt buổi sáng, có thể do ăn ít", "severity": "mild", "resolved": False}],
    ),
    # 4. Thiếu cân nghiêm trọng, sinh hoạt rất kém, nhân viên nhà hàng
    dict(
        full_name="Pham Thi D",
        gender=GenderType.nu,
        dob=date(2000, 11, 3),
        height_cm=162.0,
        weight_kg=43.0,
        body_fat_percent=14.0,
        waist_cm=62.0,
        neck_cm=30.0,
        activity=ActivityLevelType.it_van_dong,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.tang_co,
        usage_goal=UsageGoalEnum.weight_gain,
        target_weight=52.0,
        allergies=[],
        dietary_restrictions=[],
        medications=[],
        health_conditions=[
            {"id": "cond_1", "name": "underweight", "severity": "nghiêm trọng", "status": "monitored"},
            {"id": "cond_2", "name": "irregular_periods", "severity": "nhẹ", "status": "present"},
        ],
        sleep_duration_hours=4.5,
        sleep_quality=SleepQualityEnum.poor,
        sleep_schedule="02:00-07:30",
        stress_level=9,
        meal_frequency=MealFrequencyEnum.two_meals,
        cooking_preference=CookingPreferenceEnum.eat_out,
        wake_up_time="07:30",
        sleep_time="02:30",
        work_schedule="10:00-23:00, 6 ngày/tuần",
        taste_preferences={"spicy": "rất thích", "sweet": "rất thích", "salty": "trung bình", "sour": "thích", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}, {"id": "c_2", "name": "Trung Quốc", "preference": "thích"}],
        disliked_foods=[{"id": "d_1", "food": "thịt", "reason": "không thích mùi"}, {"id": "d_2", "food": "cá", "reason": "không thích mùi tanh"}],
        favorite_foods=[{"id": "f_1", "food": "trái cây", "preference": "rất thích"}, {"id": "f_2", "food": "nước ép", "preference": "rất thích"}, {"id": "f_3", "food": "bánh ngọt", "preference": "thích"}],
        disliked_foods_text="thịt, cá",
        preferred_foods_text="trái cây, nước ép, bánh ngọt",
        allergies_text=None,
        eating_speed="nhanh",
        chew_difficulty=False,
        energy_level="low",
        hydration="low",
        weight_trend="giảm",
        fitness_level="beginner",
        lifestyle_score=1,
        recent_symptoms=[
            {"date": (date.today() - timedelta(days=2)).isoformat(), "symptom": "kinh nguyệt không đều", "severity": "vừa"},
            {"date": (date.today() - timedelta(days=4)).isoformat(), "symptom": "mệt mỏi", "severity": "vừa"},
        ],
        health_events_seed=[
            {"date": (date.today() - timedelta(days=2)).isoformat(), "type": "symptom", "category": "metabolic", "description": "Kinh nguyệt không đều, có thể do thiếu cân nghiêm trọng", "severity": "moderate", "resolved": False},
            {"date": (date.today() - timedelta(days=4)).isoformat(), "type": "symptom", "category": "metabolic", "description": "Mệt mỏi, chóng mặt thường xuyên", "severity": "moderate", "resolved": False},
        ],
    ),
    # 5. Bình thường, sinh hoạt tốt, vận động viên chạy bộ
    dict(
        full_name="Hoang Van E",
        gender=GenderType.nam,
        dob=date(1993, 3, 28),
        height_cm=172.0,
        weight_kg=68.0,
        body_fat_percent=16.0,
        waist_cm=78.0,
        neck_cm=38.0,
        activity=ActivityLevelType.van_dong_nhieu,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.giu_can,
        usage_goal=UsageGoalEnum.maintain_shape,
        target_weight=68.0,
        allergies=[],
        dietary_restrictions=[],
        medications=[],
        health_conditions=[],
        sleep_duration_hours=8.0,
        sleep_quality=SleepQualityEnum.excellent,
        sleep_schedule="22:00-06:00",
        stress_level=3,
        meal_frequency=MealFrequencyEnum.five_plus,
        cooking_preference=CookingPreferenceEnum.home_cooked,
        wake_up_time="05:30",
        sleep_time="22:00",
        work_schedule="08:00-17:00, 5 ngày/tuần",
        taste_preferences={"spicy": "trung bình", "sweet": "trung bình", "salty": "trung bình", "sour": "trung bình", "bitter": "trung bình"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}, {"id": "c_2", "name": "Nhật Bản", "preference": "thích"}, {"id": "c_3", "name": "Ý", "preference": "thích"}],
        disliked_foods=[],
        favorite_foods=[{"id": "f_1", "food": "ức gà", "preference": "rất thích"}, {"id": "f_2", "food": "cá hồi", "preference": "rất thích"}, {"id": "f_3", "food": "rau xanh", "preference": "rất thích"}, {"id": "f_4", "food": "gạo lứt", "preference": "thích"}, {"id": "f_5", "food": "trứng", "preference": "thích"}],
        disliked_foods_text=None,
        preferred_foods_text="ức gà, cá hồi, rau xanh, gạo lứt, trứng",
        allergies_text=None,
        eating_speed="bình thường",
        chew_difficulty=False,
        energy_level="high",
        hydration="normal",
        weight_trend="ổn định",
        fitness_level="advanced",
        lifestyle_score=9,
        recent_symptoms=[],
        health_events_seed=[],
    ),
    # 6. Người ăn chay, nhân viên văn phòng, yoga
    dict(
        full_name="Nguyen Thi F",
        gender=GenderType.nu,
        dob=date(1997, 7, 14),
        height_cm=155.0,
        weight_kg=50.0,
        body_fat_percent=22.0,
        waist_cm=68.0,
        neck_cm=31.0,
        hip_cm=92.0,
        activity=ActivityLevelType.van_dong_nhe,
        diet=DietTypeEnum.an_chay,
        goal_type=NutritionGoalType.giu_can,
        usage_goal=UsageGoalEnum.balanced_lifestyle,
        target_weight=50.0,
        allergies=[],
        dietary_restrictions=[{"id": "dr_1", "restriction": "vegetarian", "strictness": "strict", "reason": "tự nguyện"}],
        medications=[],
        health_conditions=[],
        sleep_duration_hours=7.0,
        sleep_quality=SleepQualityEnum.good,
        sleep_schedule="22:30-06:00",
        stress_level=4,
        meal_frequency=MealFrequencyEnum.three_meals,
        cooking_preference=CookingPreferenceEnum.home_cooked,
        wake_up_time="06:00",
        sleep_time="22:30",
        work_schedule="08:30-17:30, 5 ngày/tuần",
        taste_preferences={"spicy": "trung bình", "sweet": "thích", "salty": "trung bình", "sour": "thích", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}, {"id": "c_2", "name": "Ấn Độ", "preference": "thích"}],
        disliked_foods=[{"id": "d_1", "food": "thịt", "reason": "ăn chay"}, {"id": "d_2", "food": "cá", "reason": "ăn chay"}, {"id": "d_3", "food": "hải sản", "reason": "ăn chay"}],
        favorite_foods=[{"id": "f_1", "food": "đậu", "preference": "rất thích"}, {"id": "f_2", "food": "rau củ", "preference": "rất thích"}, {"id": "f_3", "food": "nấm", "preference": "thích"}, {"id": "f_4", "food": "tofu", "preference": "thích"}],
        disliked_foods_text="thịt, cá, hải sản",
        preferred_foods_text="đậu, rau củ, nấm, tofu",
        allergies_text=None,
        eating_speed="bình thường",
        chew_difficulty=False,
        energy_level="normal",
        hydration="normal",
        weight_trend="ổn định",
        fitness_level="intermediate",
        lifestyle_score=7,
        recent_symptoms=[],
        health_events_seed=[],
    ),
    # 7. Vận động viên gym - tăng cơ, gym 5 ngày/tuần
    dict(
        full_name="Do Van G",
        gender=GenderType.nam,
        dob=date(1994, 9, 5),
        height_cm=178.0,
        weight_kg=72.0,
        body_fat_percent=14.0,
        waist_cm=80.0,
        neck_cm=40.0,
        activity=ActivityLevelType.van_dong_rat_nhieu,
        diet=DietTypeEnum.nhieu_dam,
        goal_type=NutritionGoalType.tang_co,
        usage_goal=UsageGoalEnum.muscle_gain,
        target_weight=78.0,
        allergies=[],
        dietary_restrictions=[],
        medications=[],
        health_conditions=[],
        sleep_duration_hours=7.5,
        sleep_quality=SleepQualityEnum.good,
        sleep_schedule="22:30-05:30",
        stress_level=4,
        meal_frequency=MealFrequencyEnum.five_plus,
        cooking_preference=CookingPreferenceEnum.meal_prep,
        wake_up_time="05:00",
        sleep_time="22:30",
        work_schedule="09:00-18:00, 5 ngày/tuần ( freelancer )",
        taste_preferences={"spicy": "trung bình", "sweet": "không thích", "salty": "trung bình", "sour": "trung bình", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "thích"}, {"id": "c_2", "name": "Healthy/clean eating", "preference": "rất thích"}],
        disliked_foods=[{"id": "d_1", "food": "đồ ngọt", "reason": "kiêng để giữ dáng"}],
        favorite_foods=[{"id": "f_1", "food": "ức gà", "preference": "rất thích"}, {"id": "f_2", "food": "gạo lứt", "preference": "rất thích"}, {"id": "f_3", "food": "trứng", "preference": "rất thích"}, {"id": "f_4", "food": "sữa", "preference": "rất thích"}, {"id": "f_5", "food": "thịt bò", "preference": "thích"}, {"id": "f_6", "food": "khoai lang", "preference": "thích"}],
        disliked_foods_text="đồ ngọt",
        preferred_foods_text="ức gà, gạo lứt, trứng, sữa, thịt bò, khoai lang",
        allergies_text=None,
        eating_speed="bình thường",
        chew_difficulty=False,
        energy_level="high",
        hydration="high",
        weight_trend="tăng dần",
        fitness_level="advanced",
        lifestyle_score=8,
        recent_symptoms=[{"date": (date.today() - timedelta(days=1)).isoformat(), "symptom": "đau cơ nhẹ sau tập", "severity": "nhẹ"}],
        health_events_seed=[{"date": (date.today() - timedelta(days=1)).isoformat(), "type": "symptom", "category": "muscular", "description": "Đau cơ nhẹ sau buổi tập ngực", "severity": "mild", "resolved": False}],
    ),
    # 8. Nhân viên văn phòng - ít vận động, hay ăn đêm, ngồi nhiều
    dict(
        full_name="Tran Van H",
        gender=GenderType.nam,
        dob=date(1991, 12, 20),
        height_cm=168.0,
        weight_kg=76.0,
        body_fat_percent=26.0,
        waist_cm=94.0,
        neck_cm=39.0,
        activity=ActivityLevelType.van_dong_nhe,
        diet=DietTypeEnum.it_tinh_bot,
        goal_type=NutritionGoalType.giam_can,
        usage_goal=UsageGoalEnum.weight_loss,
        target_weight=68.0,
        allergies=[{"id": "alg_1", "allergen": "gluten", "severity": "nhẹ", "category": "other"}],
        dietary_restrictions=[],
        medications=[],
        health_conditions=[{"id": "cond_1", "name": "sedentary_lifestyle", "severity": "nhẹ", "status": "present"}],
        sleep_duration_hours=6.0,
        sleep_quality=SleepQualityEnum.fair,
        sleep_schedule="01:00-07:00",
        stress_level=7,
        meal_frequency=MealFrequencyEnum.three_meals,
        cooking_preference=CookingPreferenceEnum.eat_out,
        wake_up_time="07:00",
        sleep_time="01:00",
        work_schedule="09:00-18:00, 5 ngày/tuần",
        taste_preferences={"spicy": "thích", "sweet": "thích", "salty": "thích", "sour": "trung bình", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}],
        disliked_foods=[{"id": "d_1", "food": "cá", "reason": "không thích mùi"}],
        favorite_foods=[{"id": "f_1", "food": "cơm trắng", "preference": "rất thích"}, {"id": "f_2", "food": "thịt heo", "preference": "rất thích"}, {"id": "f_3", "food": "bánh mì", "preference": "thích"}, {"id": "f_4", "food": "trà sữa", "preference": "thích"}],
        disliked_foods_text="cá",
        preferred_foods_text="cơm trắng, thịt heo, bánh mì, trà sữa",
        allergies_text="dị ứng gluten nhẹ",
        eating_speed="nhanh",
        chew_difficulty=False,
        energy_level="normal",
        hydration="low",
        weight_trend="tăng",
        fitness_level="beginner",
        lifestyle_score=3,
        recent_symptoms=[{"date": (date.today() - timedelta(days=2)).isoformat(), "symptom": "đau lưng dưới", "severity": "nhẹ"}],
        health_events_seed=[{"date": (date.today() - timedelta(days=2)).isoformat(), "type": "symptom", "category": "muscular", "description": "Đau lưng dưới do ngồi nhiều", "severity": "mild", "resolved": False}],
    ),
    # 9. Keto - người béo phì, tiểu đường type 2 kiểm soát bằng ăn uống
    dict(
        full_name="Le Thi I",
        gender=GenderType.nu,
        dob=date(1988, 4, 8),
        height_cm=160.0,
        weight_kg=85.0,
        body_fat_percent=40.0,
        waist_cm=100.0,
        neck_cm=36.0,
        hip_cm=110.0,
        activity=ActivityLevelType.it_van_dong,
        diet=DietTypeEnum.keto,
        goal_type=NutritionGoalType.giam_can,
        usage_goal=UsageGoalEnum.weight_loss,
        target_weight=60.0,
        allergies=[],
        dietary_restrictions=[],
        medications=[{"id": "med_1", "name": "metformin", "dosage": "500mg", "frequency": "2 lần/ngày"}],
        health_conditions=[
            {"id": "cond_1", "name": "type2_diabetes", "severity": "vừa", "status": "controlled"},
            {"id": "cond_2", "name": "hypertension", "severity": "nhẹ", "status": "controlled"},
        ],
        sleep_duration_hours=6.5,
        sleep_quality=SleepQualityEnum.fair,
        sleep_schedule="23:00-06:00",
        stress_level=6,
        meal_frequency=MealFrequencyEnum.three_meals,
        cooking_preference=CookingPreferenceEnum.home_cooked,
        wake_up_time="06:00",
        sleep_time="23:00",
        work_schedule="08:00-16:00, 5 ngày/tuần (bán thời gian)",
        taste_preferences={"spicy": "thích", "sweet": "không thích", "salty": "trung bình", "sour": "trung bình", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "rất thích"}, {"id": "c_2", "name": "Keto-friendly", "preference": "rất thích"}],
        disliked_foods=[{"id": "d_1", "food": "bánh kẹo", "reason": "kiêng keto"}, {"id": "d_2", "food": "cơm", "reason": "kiêng tinh bột"}],
        favorite_foods=[{"id": "f_1", "food": "thịt bò", "preference": "rất thích"}, {"id": "f_2", "food": "trứng", "preference": "rất thích"}, {"id": "f_3", "food": "bơ", "preference": "rất thích"}, {"id": "f_4", "food": "dầu dừa", "preference": "thích"}],
        disliked_foods_text="bánh kẹo, cơm",
        preferred_foods_text="thịt bò, trứng, bơ, dầu dừa",
        allergies_text=None,
        eating_speed="bình thường",
        chew_difficulty=False,
        energy_level="normal",
        hydration="normal",
        weight_trend="giảm chậm",
        fitness_level="beginner",
        lifestyle_score=4,
        recent_symptoms=[],
        health_events_seed=[{"date": (date.today() - timedelta(days=7)).isoformat(), "type": "measurement", "category": "metabolic", "description": "Đường huyết lúc đói 118 mg/dL, kiểm soát tốt với chế độ ăn", "severity": "mild", "resolved": True}],
    ),
    # 10. Sinh viên - hay bỏ bữa, ăn vặt nhiều, chơi game khuya
    dict(
        full_name="Pham Van K",
        gender=GenderType.nam,
        dob=date(2003, 6, 30),
        height_cm=171.0,
        weight_kg=60.0,
        body_fat_percent=18.0,
        waist_cm=74.0,
        neck_cm=35.0,
        activity=ActivityLevelType.van_dong_vua,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.giu_can,
        usage_goal=UsageGoalEnum.maintain_shape,
        target_weight=68.0,
        allergies=[],
        dietary_restrictions=[],
        medications=[],
        health_conditions=[{"id": "cond_1", "name": "irregular_eating", "severity": "nhẹ", "status": "present"}],
        sleep_duration_hours=5.0,
        sleep_quality=SleepQualityEnum.poor,
        sleep_schedule="03:00-08:30",
        stress_level=6,
        meal_frequency=MealFrequencyEnum.two_meals,
        cooking_preference=CookingPreferenceEnum.eat_out,
        wake_up_time="08:30",
        sleep_time="03:00",
        work_schedule="08:00-17:00 (ca học), tự do buổi tối",
        taste_preferences={"spicy": "rất thích", "sweet": "rất thích", "salty": "thích", "sour": "trung bình", "bitter": "không thích"},
        cuisine_preferences=[{"id": "c_1", "name": "Việt Nam", "preference": "thích"}, {"id": "c_2", "name": "Fast food", "preference": "rất thích"}, {"id": "c_3", "name": "Nhanh (quick meals)", "preference": "rất thích"}],
        disliked_foods=[{"id": "d_1", "food": "rau", "reason": "không thích"}],
        favorite_foods=[{"id": "f_1", "food": "pizza", "preference": "rất thích"}, {"id": "f_2", "food": "burger", "preference": "rất thích"}, {"id": "f_3", "food": "trà sữa", "preference": "rất thích"}, {"id": "f_4", "food": "bánh ngọt", "preference": "thích"}],
        disliked_foods_text="rau",
        preferred_foods_text="pizza, burger, trà sữa, bánh ngọt",
        allergies_text=None,
        eating_speed="rất nhanh",
        chew_difficulty=False,
        energy_level="normal",
        hydration="low",
        weight_trend="tăng nhẹ",
        fitness_level="beginner",
        lifestyle_score=3,
        recent_symptoms=[{"date": (date.today() - timedelta(days=3)).isoformat(), "symptom": "nổi mụn nhiều", "severity": "nhẹ"}],
        health_events_seed=[
            {"date": (date.today() - timedelta(days=3)).isoformat(), "type": "symptom", "category": "other", "description": "Nổi mụn nhiều, có thể do ăn nhiều đồ ngọt và thiếu ngủ", "severity": "mild", "resolved": False},
            {"date": (date.today() - timedelta(days=8)).isoformat(), "type": "symptom", "category": "metabolic", "description": "Đau bụng sau khi ăn pizza và uống trà sữa", "severity": "mild", "resolved": True},
        ],
    ),
]


# ─── Tính TDEE & macro target ───────────────────────────────────

def calc_targets(udata: dict) -> dict:
    """Tính BMR, TDEE, calorie target và macro targets."""
    weight = udata["weight_kg"]
    height = udata["height_cm"]
    age = (date.today() - udata["dob"]).days // 365
    gender = udata["gender"]
    activity = udata["activity"]
    goal_type = udata["goal_type"]

    # Mifflin-St Jeor
    if gender == GenderType.nam:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Activity multiplier
    activity_multipliers = {
        ActivityLevelType.it_van_dong: 1.20,
        ActivityLevelType.van_dong_nhe: 1.375,
        ActivityLevelType.van_dong_vua: 1.55,
        ActivityLevelType.van_dong_nhieu: 1.725,
        ActivityLevelType.van_dong_rat_nhieu: 1.9,
    }
    tdee = bmr * activity_multipliers.get(activity, 1.55)

    # Goal adjustment
    goal_adjustments = {
        NutritionGoalType.giam_can: -500,
        NutritionGoalType.tang_co: 300,
        NutritionGoalType.giu_can: 0,
    }
    daily_cal = tdee + goal_adjustments.get(goal_type, 0)

    # Macro split
    if udata["diet"] == DietTypeEnum.keto:
        protein_pct, carb_pct, fat_pct = 0.25, 0.05, 0.70
    elif udata["diet"] == DietTypeEnum.nhieu_dam:
        protein_pct, carb_pct, fat_pct = 0.35, 0.40, 0.25
    elif udata["diet"] == DietTypeEnum.it_tinh_bot:
        protein_pct, carb_pct, fat_pct = 0.25, 0.25, 0.50
    elif udata["diet"] == DietTypeEnum.an_chay:
        protein_pct, carb_pct, fat_pct = 0.20, 0.55, 0.25
    else:
        protein_pct, carb_pct, fat_pct = 0.30, 0.40, 0.30

    return {
        "bmr_kcal": round(bmr, 1),
        "tdee_kcal": round(tdee, 1),
        "daily_calorie_target": round(daily_cal),
        "protein_target_g": round(daily_cal * protein_pct / 4),
        "carb_target_g": round(daily_cal * carb_pct / 4),
        "fat_target_g": round(daily_cal * fat_pct / 9),
    }


def pick_foods(diet: DietTypeEnum, meal_type: MealTypeEnum, cal_budget: float) -> list[dict]:
    """Chọn ngẫu nhiên các món ăn phù hợp trong budget."""
    if meal_type == MealTypeEnum.bua_sang:
        pool = BREAKFAST_FOODS if diet != DietTypeEnum.an_chay else CHAY_FOODS
    elif meal_type == MealTypeEnum.bua_trua or meal_type == MealTypeEnum.bua_toi:
        pool = LUNCH_FOODS if diet != DietTypeEnum.an_chay else CHAY_FOODS
    else:
        pool = SNACK_FOODS if diet != DietTypeEnum.an_chay else CHAY_FOODS

    selected = []
    total_cal = 0.0
    remaining = cal_budget

    candidates = list(FOOD_DB.keys())
    random.shuffle(candidates)

    for key in candidates:
        if key not in FOOD_DB:
            continue
        food = FOOD_DB[key]
        food_cal = food["cal"]
        portion = min(1.0, remaining / food_cal) if food_cal > 0 else 0
        if portion < 0.3:
            continue

        selected.append({
            "name": key,
            "cal": round(food_cal * portion),
            "protein": round(food["protein"] * portion, 1),
            "carb": round(food["carb"] * portion, 1),
            "fat": round(food["fat"] * portion, 1),
            "weight": round(food["weight"] * portion),
        })
        total_cal += food_cal * portion
        remaining -= food_cal * portion

        if total_cal >= cal_budget * 0.9:
            break

    return selected


async def seed_demo_data():
    """Main seed function."""

    async with AsyncSessionLocal() as db:
        # Xóa dữ liệu cũ
        await db.execute(text("DELETE FROM conversation_insights"))
        await db.execute(text("DELETE FROM chat_messages"))
        await db.execute(text("DELETE FROM chat_sessions"))
        await db.execute(text("DELETE FROM meal_items"))
        await db.execute(text("DELETE FROM meal_logs"))
        await db.execute(text("DELETE FROM progress_logs"))
        await db.execute(text("DELETE FROM nutrition_goals"))
        await db.execute(text("DELETE FROM user_memory"))
        await db.execute(text("DELETE FROM user_profiles"))
        await db.execute(text("DELETE FROM users"))
        await db.commit()
        print("Đã xóa dữ liệu cũ.")

        all_users = []

        for idx, udata in enumerate(USERS, 1):
            print(f"\n[{idx}/10] Tạo: {udata['full_name']}")

            # ── User
            now_ts = datetime.now(timezone.utc)
            user = User(
                email=f"user{idx}@smartmeal.local",
                password_hash="$2b$12$sDASjwOSDOFON/9f687IC.v4rL11cgPyfpvjrnHDnqapKGSOpT5aC",  # Password: SmartMeal123
                full_name=udata["full_name"],
                role="user",
                is_active=True,
                is_verified=True,
                failed_login_attempts=0,
                login_allowed_at=now_ts,
            )
            db.add(user)
            await db.flush()

            # ── Profile
            profile = UserProfile(
                user_id=user.id,
                gender=udata["gender"],
                date_of_birth=udata["dob"],
                height_cm=udata["height_cm"],
                current_weight_kg=udata["weight_kg"],
                current_body_fat_percent=udata.get("body_fat_percent"),
                current_waist_cm=udata.get("waist_cm"),
                current_neck_cm=udata.get("neck_cm"),
                current_hip_cm=udata.get("hip_cm"),
                current_chest_cm=udata.get("chest_cm"),
                activity_level=udata["activity"],
                diet_type=udata["diet"],
                usage_goal=udata.get("usage_goal"),
                usage_goal_note=udata.get("usage_goal_note"),
                allergies_text=udata.get("allergies_text"),
                disliked_foods_text=udata.get("disliked_foods_text"),
                preferred_foods_text=udata.get("preferred_foods_text"),
                health_note=None,
                # JSONB fields
                allergies=udata.get("allergies"),
                dietary_restrictions=udata.get("dietary_restrictions"),
                medications=udata.get("medications"),
                health_conditions=udata.get("health_conditions"),
                # Lifestyle
                sleep_duration_hours=udata.get("sleep_duration_hours"),
                sleep_quality=udata.get("sleep_quality"),
                sleep_schedule=udata.get("sleep_schedule"),
                stress_level=udata.get("stress_level"),
                meal_frequency=udata.get("meal_frequency"),
                cooking_preference=udata.get("cooking_preference"),
                wake_up_time=udata.get("wake_up_time"),
                sleep_time=udata.get("sleep_time"),
                work_schedule=udata.get("work_schedule"),
                # Taste & food
                taste_preferences=udata.get("taste_preferences"),
                cuisine_preferences=udata.get("cuisine_preferences"),
                disliked_foods=udata.get("disliked_foods"),
                favorite_foods=udata.get("favorite_foods"),
                eating_speed=udata.get("eating_speed"),
                chew_difficulty=udata.get("chew_difficulty"),
            )
            db.add(profile)

            # ── Nutrition Goal
            targets = calc_targets(udata)
            goal = NutritionGoal(
                user_id=user.id,
                goal_type=udata["goal_type"],
                target_weight_kg=udata["target_weight"],
                start_date=date.today() - timedelta(days=10),
                bmr_kcal=targets["bmr_kcal"],
                tdee_kcal=targets["tdee_kcal"],
                daily_calorie_target=targets["daily_calorie_target"],
                protein_target_g=targets["protein_target_g"],
                carb_target_g=targets["carb_target_g"],
                fat_target_g=targets["fat_target_g"],
                is_active=True,
            )
            db.add(goal)
            await db.flush()

            print(f"  Cal target: {targets['daily_calorie_target']} kcal | "
                  f"P/C/F: {targets['protein_target_g']:.0f}/{targets['carb_target_g']:.0f}/{targets['fat_target_g']:.0f}g")

            # ── 60 ngày dữ liệu ăn uống
            start_day = date.today() - timedelta(days=59)
            DAYS = 60

            # ── Weekly calorie modifiers theo profile đặc trưng
            # mỗi tuple = (weekday modifier, weekend modifier)
            # modifier > 1.0 = ăn nhiều hơn target, < 1.0 = ăn ít hơn
            WEEKDAY_MOD, WEEKEND_MOD = 0, 1
            calorie_patterns = {
                1: (0.80, 0.95),   # A: ngày thường tiết kiệm, cuối tuần放纵
                2: (0.75, 0.90),   # B: nghiêm ngặt cả tuần, ít cheat
                3: (1.10, 1.25),   # C: ăn không kiểm soát được, hay ăn vặt
                4: (0.85, 0.95),   # D: bỏ bữa thất thường, thiếu ăn
                5: (0.97, 1.03),   # E: rất đều đặn, cuối tuần ăn thoải mái
                6: (0.90, 1.05),   # F: ăn chay có kiểm soát, cuối tuần nấu nhiều
                7: (1.15, 1.35),   # G: tăng cơ ăn nhiều, gym nhiều ăn nhiều
                8: (0.70, 1.10),   # H: ngày làm ăn rất ít, cuối tuần ăn bù
                9: (0.80, 0.90),   # I: keto nghiêm ngặt, cuối tuần dễ vỡ diet
                10: (0.75, 1.20),  # K: sinh viên bỏ bữa ngày thường, cuối tuần ăn free
            }
            weekday_mod, weekend_mod = calorie_patterns[idx]

            # Ăn vặt probability theo lifestyle
            # lifestyle cao → ít ăn vặt, lifestyle thấp → nhiều snack đặc trưng
            snack_prob_configs = {
                1: (0.50, 0.50),   # (prob sáng, prob chiều) — gần như luôn có
                2: (0.15, 0.15),
                3: (0.60, 0.70),   # hay đói nên ăn vặt nhiều
                4: (0.25, 0.30),
                5: (0.10, 0.10),
                6: (0.20, 0.25),
                7: (0.15, 0.20),   # gym nên có protein snack
                8: (0.60, 0.70),   # nhàn rỗi → nhiều snack
                9: (0.05, 0.10),   # keto rất ít snack
                10: (0.40, 0.60),  # sinh viên hay ăn vặt
            }
            snack_prob_am, snack_prob_pm = snack_prob_configs[idx]

            # Meal frequency per user
            skip_breakfast_prob = {
                1: 0.15,  # A: hay ăn sáng nhanh
                2: 0.60,  # B: chỉ uống cà phê sáng
                3: 0.20,  # C: dậy muộn bỏ bữa
                4: 0.55,  # D: thức khuya bỏ bữa sáng
                5: 0.05,  # E: discipline cao
                6: 0.10,  # F: ăn chay đúng giờ
                7: 0.05,  # G: dậy sớm tập gym
                8: 0.35,  # H: ngủ khuya dậy muộn
                9: 0.20,  # I: keto breakfast
                10: 0.60, # K: sinh viên hay ngủ đến trưa
            }[idx]

            skip_lunch_prob = {
                1: 0.05, 2: 0.05, 3: 0.30, 4: 0.40,
                5: 0.02, 6: 0.05, 7: 0.05, 8: 0.10,
                9: 0.05, 10: 0.20,
            }[idx]

            # Late night eating
            late_night_prob = {
                1: 0.25, 2: 0.05, 3: 0.15, 4: 0.45,
                5: 0.05, 6: 0.08, 7: 0.05, 8: 0.50,
                9: 0.10, 10: 0.60,
            }[idx]

            # Snack food pools đặc trưng theo user
            SNACK_PREFERENCES = {
                1: ["tra_sua", "banh_keo", "banh_plan", "ca_phe_sua"],
                2: ["hoa_qua", "sua_chua", "ca_phe_sua"],
                3: ["banh_keo", "kem", "banh_tet", "tra_sua"],
                4: ["hoa_qua", "sua_chua"],
                5: ["hat_dieu", "hoa_qua", "sua_chua"],
                6: ["hoa_qua", "sua_chua_hoa_qua", "hat_dieu"],
                7: ["sua_chua", "hat_dieu", "tra_sua", "hoa_qua"],
                8: ["tra_sua", "banh_keo", "kem", "banh_plan", "banh_tet"],
                9: ["hat_dieu", "hoa_qua", "sua_chua"],
                10: ["tra_sua", "kem", "banh_keo", "banh_plan", "banh_tet", "banh_tet"],
            }
            user_snack_pool = SNACK_PREFERENCES[idx]

            # Track cho weight change và recent_meals
            daily_cals = []
            recent_meals_memory = []

            # Đếm tuần để xác định weekday vs weekend
            # Ngày hôm nay trong tuần: 0=Mon, 6=Sun
            today_weekday = date.today().weekday()

            for day_offset in range(DAYS):
                day = start_day + timedelta(days=day_offset)
                day_of_week = day.weekday()  # 0=Mon, 6=Sun

                is_weekend = day_of_week >= 5
                cal_mod = weekend_mod if is_weekend else weekday_mod

                # Wobbly daily variation ±8%
                daily_noise = random.uniform(0.92, 1.08)
                effective_mod = cal_mod * daily_noise

                base_cal = targets["daily_calorie_target"]

                # ── Bữa sáng ───────────────────────────────
                if random.random() >= skip_breakfast_prob:
                    breakfast_budget = base_cal * 0.25 * effective_mod
                    breakfast_foods = pick_foods(
                        udata["diet"], MealTypeEnum.bua_sang, breakfast_budget
                    )
                    await _create_meal(
                        db, user.id, goal.id, MealTypeEnum.bua_sang, day,
                        hour=_breakfast_hour(idx), foods=breakfast_foods
                    )
                    for f in breakfast_foods:
                        recent_meals_memory.append({
                            "date": day.isoformat(), "meal_type": "bua_sang",
                            "items": [f["name"]], "estimated_kcal": f["cal"],
                            "confidence": "high",
                        })

                # ── Bữa trưa ───────────────────────────────
                if random.random() >= skip_lunch_prob:
                    lunch_budget = base_cal * 0.35 * effective_mod
                    lunch_foods = pick_foods(
                        udata["diet"], MealTypeEnum.bua_trua, lunch_budget
                    )
                    await _create_meal(
                        db, user.id, goal.id, MealTypeEnum.bua_trua, day,
                        hour=_lunch_hour(idx), foods=lunch_foods
                    )
                    for f in lunch_foods:
                        recent_meals_memory.append({
                            "date": day.isoformat(), "meal_type": "bua_trua",
                            "items": [f["name"]], "estimated_kcal": f["cal"],
                            "confidence": "high",
                        })

                # ── Bữa tối ───────────────────────────────
                dinner_budget = base_cal * 0.30 * effective_mod
                dinner_foods = pick_foods(
                    udata["diet"], MealTypeEnum.bua_toi, dinner_budget
                )
                await _create_meal(
                    db, user.id, goal.id, MealTypeEnum.bua_toi, day,
                    hour=_dinner_hour(idx), foods=dinner_foods
                )
                for f in dinner_foods:
                    recent_meals_memory.append({
                        "date": day.isoformat(), "meal_type": "bua_toi",
                        "items": [f["name"]], "estimated_kcal": f["cal"],
                        "confidence": "high",
                    })

                # ── Bữa phụ sáng ──────────────────────────
                if random.random() < snack_prob_am:
                    snack_budget = base_cal * random.uniform(0.03, 0.06)
                    snack_foods = _pick_snacks(user_snack_pool, snack_budget)
                    if snack_foods:
                        await _create_meal(
                            db, user.id, goal.id, MealTypeEnum.an_vat, day,
                            hour=10, foods=snack_foods
                        )
                        for f in snack_foods:
                            recent_meals_memory.append({
                                "date": day.isoformat(), "meal_type": "an_vat_sang",
                                "items": [f["name"]], "estimated_kcal": f["cal"],
                                "confidence": "medium",
                            })

                # ── Bữa phụ chiều ─────────────────────────
                if random.random() < snack_prob_pm:
                    snack_budget2 = base_cal * random.uniform(0.03, 0.06)
                    snack_foods2 = _pick_snacks(user_snack_pool, snack_budget2)
                    if snack_foods2:
                        await _create_meal(
                            db, user.id, goal.id, MealTypeEnum.an_vat, day,
                            hour=15, foods=snack_foods2
                        )
                        for f in snack_foods2:
                            recent_meals_memory.append({
                                "date": day.isoformat(), "meal_type": "an_vat_chieu",
                                "items": [f["name"]], "estimated_kcal": f["cal"],
                                "confidence": "medium",
                            })

                # ── Ăn đêm ────────────────────────────────
                if random.random() < late_night_prob:
                    late_budget = base_cal * random.uniform(0.08, 0.15)
                    late_foods = pick_foods(udata["diet"], MealTypeEnum.khac, late_budget)
                    if late_foods:
                        await _create_meal(
                            db, user.id, goal.id, MealTypeEnum.khac, day,
                            hour=random.randint(22, 23), foods=late_foods
                        )
                        for f in late_foods:
                            recent_meals_memory.append({
                                "date": day.isoformat(), "meal_type": "an_dem",
                                "items": [f["name"]], "estimated_kcal": f["cal"],
                                "confidence": "low",
                            })

            # ── Progress logs: mỗi tuần 1 lần trong 60 ngày ──
            weight_now = udata["weight_kg"]
            # Ước tính weight change sau 60 ngày dựa trên calorie surplus/deficit
            avg_daily_ratio = (weekday_mod + weekend_mod) / 2
            avg_daily_cal = targets["daily_calorie_target"] * avg_daily_ratio
            cal_surplus_per_day = avg_daily_cal - targets["daily_calorie_target"]
            # ~7700 kcal ≈ 1 kg body weight
            kg_change = (cal_surplus_per_day * 60) / 7700
            weight_end = round(weight_now + kg_change, 2)
            weight_start = weight_now

            progress_days = [7, 14, 21, 28, 35, 42, 49, 56]  # mỗi tuần
            for pday in progress_days:
                progress_date = start_day + timedelta(days=pday)
                t = pday / 60.0  # 0 → 1
                eased_t = t ** 0.8  # weight change thường chậm đầu rồi nhanh dần
                log_weight = round(weight_start + (weight_end - weight_start) * eased_t + random.uniform(-0.3, 0.3), 2)
                note = f"Theo dõi tuần {pday // 7 + 1}"
                if udata["goal_type"] == NutritionGoalType.giam_can:
                    note += f" | Mục tiêu: giảm cân"
                elif udata["goal_type"] == NutritionGoalType.tang_co:
                    note += f" | Mục tiêu: tăng cân"
                else:
                    note += f" | Mục tiêu: giữ cân"

                progress = ProgressLog(
                    user_id=user.id,
                    log_date=progress_date,
                    weight_kg=log_weight,
                    note=note,
                )
                db.add(progress)

            # ── UserMemory
            # weight change tính từ modifier đã có ở trên (weekday_mod, weekend_mod)
            avg_ratio = (weekday_mod * 5 + weekend_mod * 2) / 7
            avg_cal = targets["daily_calorie_target"] * avg_ratio
            kg_change = ((avg_cal - targets["daily_calorie_target"]) * 60) / 7700
            end_weight = round(udata["weight_kg"] + kg_change, 2)

            body_snapshot = {
                "weight": end_weight,
                "weight_updated_at": date.today().isoformat(),
                "energy_level": udata.get("energy_level", "normal"),
                "sleep_last_night": udata.get("sleep_duration_hours", 7.0),
                "digestion_status": "normal",
                "muscle_status": {"sore_areas": [], "injury_areas": [], "last_workout": None},
                "hydration": udata.get("hydration", "normal"),
                "weight_trend": udata.get("weight_trend", "unknown"),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

            # recent_meals_memory được ghi trong vòng 60 ngày bên trên
            nutrition_memory = {
                "recent_meals": recent_meals_memory[-30:],  # last 30 meal entries
                "avg_daily_kcal_7d": _calc_avg_kcal_7d(idx, targets),
                "protein_adequacy": "adequate",
                "common_deficiencies": [],
                "foods_to_avoid": [
                    {"food": a["allergen"], "reason": "dị ứng", "confidence": "high"}
                    for a in (udata.get("allergies") or [])
                ],
                "preferred_foods": [f["food"] for f in (udata.get("favorite_foods") or [])],
                "meal_pattern": str(udata.get("meal_frequency", "three_meals")).replace("MealFrequencyEnum.", ""),
            }

            fitness_level_map = {
                "beginner": "beginner",
                "intermediate": "intermediate",
                "advanced": "advanced",
            }
            fitness_memory = {
                "fitness_level": fitness_level_map.get(udata.get("fitness_level", "intermediate"), "intermediate"),
                "last_workout_date": None,
                "workout_frequency_7d": 0,
                "preferred_workout_types": [],
                "current_restrictions": [],
                "recent_achievements": [],
            }

            key_facts = []
            if udata.get("allergies"):
                for a in udata["allergies"]:
                    key_facts.append({
                        "fact": f"Bị dị ứng {a['allergen']}",
                        "confidence": "high",
                        "first_seen": date.today().isoformat(),
                        "category": "allergy",
                    })
            if udata.get("health_conditions"):
                for c in udata["health_conditions"]:
                    key_facts.append({
                        "fact": f"Tình trạng sức khỏe: {c['name']} (mức độ {c.get('severity', 'không rõ')})",
                        "confidence": "high",
                        "first_seen": date.today().isoformat(),
                        "category": "health_condition",
                    })
            if udata.get("favorite_foods"):
                key_facts.append({
                    "fact": f"Yêu thích: {', '.join(f['food'] for f in udata['favorite_foods'][:3])}",
                    "confidence": "high",
                    "first_seen": date.today().isoformat(),
                    "category": "food_preference",
                })
            if udata.get("disliked_foods"):
                for d in udata["disliked_foods"]:
                    key_facts.append({
                        "fact": f"Không thích ăn: {d['food']}",
                        "confidence": "high",
                        "first_seen": date.today().isoformat(),
                        "category": "food_preference",
                    })
            key_facts.append({
                "fact": f"Chế độ ăn: {udata['diet'].value}. Tốc độ ăn: {udata.get('eating_speed', 'bình thường')}",
                "confidence": "medium",
                "first_seen": date.today().isoformat(),
                "category": "habit",
            })

            memory = UserMemory(
                user_id=user.id,
                body_snapshot=body_snapshot,
                health_events=udata.get("health_events_seed") or [],
                nutrition_memory=nutrition_memory,
                fitness_memory=fitness_memory,
                conversation_summary=(
                    f"User tên {udata['full_name']}, "
                    f"mục tiêu {udata.get('usage_goal', 'unknown').value if udata.get('usage_goal') else 'unknown'}, "
                    f"chế độ ăn {udata['diet'].value}, "
                    f"tập thể dục {udata.get('fitness_level', 'intermediate')}. "
                    f"Lịch sinh hoạt: ngủ {udata.get('sleep_schedule', 'không rõ')}, "
                    f"thức dậy {udata.get('wake_up_time', 'không rõ')}, "
                    f"giờ làm việc {udata.get('work_schedule', 'không rõ')}."
                ),
                key_facts=key_facts,
            )
            db.add(memory)

            # ── Chat session mẫu
            session = ChatSession(
                user_id=user.id,
                title="Hỏi về chế độ ăn",
                status="active",
                last_message_at=datetime.now(timezone.utc),
            )
            db.add(session)
            await db.flush()

            # Tin nhắn chat mẫu
            allergies_list = udata.get("allergies") or []
            allergy_str = ", ".join(a["allergen"] for a in allergies_list) or "không có dị ứng"
            chat_pairs = [
                ("user", "Cho tôi hỏi về chế độ ăn giảm cân hiệu quả"),
                ("assistant", "Để giảm cân hiệu quả, bạn nên kiểm soát lượng calorie nạp vào, ăn đủ protein và tập thể dục đều đặn."),
                ("user", f"Tôi bị {allergy_str}. Có ảnh hưởng gì không?"),
                ("assistant", f"Bạn nên tránh các thực phẩm gây dị ứng {allergy_str}. Tôi sẽ lưu ý khi đưa ra lời khuyên dinh dưỡng cho bạn."),
            ]
            for role, content in chat_pairs:
                msg = ChatMessage(
                    session_id=session.id,
                    role=role,
                    content=content,
                )
                db.add(msg)

            # Conversation insight mẫu (dị ứng từ allergies JSONB)
            for a in allergies_list:
                allergen_name = a.get("allergen", "")
                key = f"allergy_{allergen_name.replace(' ', '_').lower()}"
                insight = ConversationInsight(
                    user_id=user.id,
                    session_id=session.id,
                    insight_type="health_constraint",
                    key=key,
                    value=allergen_name,
                    summary=f"Người dùng bị dị ứng {allergen_name}, mức độ {a.get('severity', 'không rõ')}",
                    is_active=True,
                )
                db.add(insight)

            all_users.append((user.email, "SmartMeal123"))

        await db.commit()
        print("\nHoàn tất! Đã tạo 10 users.")
        print("\nTài khoản đăng nhập:")
        for email, pw in all_users:
            print(f"  {email} / {pw}")

        print("\nBMI và phân loại:")
        for udata in USERS:
            bmi = udata["weight_kg"] / ((udata["height_cm"] / 100) ** 2)
            cat = "Béo phì" if bmi >= 30 else "Thừa cân" if bmi >= 25 else "Thiếu cân" if bmi < 18.5 else "Bình thường"
            print(f"  {udata['full_name']}: BMI={bmi:.1f} ({cat}), lifestyle={udata['lifestyle_score']}/10")


async def _create_meal(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    meal_type: MealTypeEnum,
    day: date,
    hour: int,
    foods: list[dict],
):
    """Tạo một MealLog và các MealItem tương ứng."""
    if not foods:
        return

    meal_dt = datetime(day.year, day.month, day.day, hour, random.randint(0, 59), tzinfo=timezone.utc)

    meal = MealLog(
        user_id=user_id,
        nutrition_goal_id=goal_id,
        meal_type=meal_type,
        meal_time=meal_dt,
        total_calories=sum(f["cal"] for f in foods),
        total_protein_g=sum(f["protein"] for f in foods),
        total_carb_g=sum(f["carb"] for f in foods),
        total_fat_g=sum(f["fat"] for f in foods),
        note=None,
    )
    db.add(meal)
    await db.flush()

    for f in foods:
        item = MealItem(
            meal_log_id=meal.id,
            detected_food_name=f["name"],
            display_food_name=f["name"].replace("_", " ").title(),
            estimated_weight_g=f["weight"],
            calories=f["cal"],
            protein_g=f["protein"],
            carb_g=f["carb"],
            fat_g=f["fat"],
            source=ItemSourceType.nhap_thu_cong,
        )
        db.add(item)


def _pick_snacks(pool: list[str], budget: float) -> list[dict]:
    """Chọn snack từ pool ưu tiên của user trong budget."""
    if budget < 50:
        return []
    selected = []
    total_cal = 0.0
    candidates = list(pool)
    random.shuffle(candidates)
    for key in candidates:
        if key not in FOOD_DB:
            continue
        food = FOOD_DB[key]
        food_cal = food["cal"]
        portion = min(1.0, (budget - total_cal) / food_cal) if food_cal > 0 else 0
        if portion < 0.3:
            continue
        selected.append({
            "name": key,
            "cal": round(food_cal * portion),
            "protein": round(food["protein"] * portion, 1),
            "carb": round(food["carb"] * portion, 1),
            "fat": round(food["fat"] * portion, 1),
            "weight": round(food["weight"] * portion),
        })
        total_cal += food_cal * portion
        if total_cal >= budget * 0.85:
            break
    return selected


def _breakfast_hour(user_idx: int) -> int:
    """Giờ ăn sáng đặc trưng theo profile."""
    hours = {1: 7, 2: 9, 3: 10, 4: 10, 5: 6, 6: 7, 7: 6, 8: 9, 9: 7, 10: 10}
    return min(hours.get(user_idx, 7) + random.randint(0, 1), 23)


def _lunch_hour(user_idx: int) -> int:
    hours = {1: 12, 2: 12, 3: 12, 4: 14, 5: 12, 6: 12, 7: 12, 8: 12, 9: 12, 10: 12}
    return min(hours.get(user_idx, 12) + random.randint(0, 1), 23)


def _dinner_hour(user_idx: int) -> int:
    """Giờ ăn tối đặc trưng: người khuya ăn muộn hơn."""
    hours = {1: 19, 2: 19, 3: 20, 4: 22, 5: 19, 6: 19, 7: 19, 8: 20, 9: 19, 10: 21}
    return min(hours.get(user_idx, 19) + random.randint(0, 2), 23)


def _calc_avg_kcal_7d(idx: int, targets: dict) -> float:
    """Tính avg kcal 7 ngày gần nhất dựa trên pattern của user."""
    weekday_mod, weekend_mod = (
        (0.80, 0.95), (0.75, 0.90), (1.10, 1.25), (0.85, 0.95),
        (0.97, 1.03), (0.90, 1.05), (1.15, 1.35), (0.70, 1.10),
        (0.80, 0.90), (0.75, 1.20),
    )[idx - 1]
    avg_mod = (weekday_mod * 5 + weekend_mod * 2) / 7
    return round(targets["daily_calorie_target"] * avg_mod)


if __name__ == "__main__":
    from app.db.session import Base
    asyncio.run(seed_demo_data())
