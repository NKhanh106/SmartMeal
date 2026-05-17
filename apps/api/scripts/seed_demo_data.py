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
from app.models.user_profile import UserProfile
from app.models.enums import (
    ActivityLevelType,
    DietTypeEnum,
    GenderType,
    ItemSourceType,
    MealTypeEnum,
    NutritionGoalType,
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
    # 1. Béo phì, ít vận động, ăn nhiều snack
    dict(
        full_name="Nguyen Van A",
        gender=GenderType.nam,
        dob=date(1995, 5, 10),
        height_cm=170, weight_kg=95,
        activity=ActivityLevelType.it_van_dong,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.giam_can,
        target_weight=80,
        allergies="dị ứng hải sản nhẹ",
        disliked_foods="rau xanh",
        preferred_foods="thịt heo, đồ chiên, nước ngọt",
        lifestyle_score=2,  # kém
    ),
    # 2. Béo phì, vận động vừa, ăn kiêng
    dict(
        full_name="Tran Thi B",
        gender=GenderType.nu,
        dob=date(1990, 8, 22),
        height_cm=158, weight_kg=78,
        activity=ActivityLevelType.van_dong_vua,
        diet=DietTypeEnum.nhieu_dam,
        goal_type=NutritionGoalType.giam_can,
        target_weight=58,
        allergies=None,
        disliked_foods="đậu phộng",
        preferred_foods="thịt bò, rau củ",
        lifestyle_score=6,
    ),
    # 3. Thiếu cân, ăn ít
    dict(
        full_name="Le Van C",
        gender=GenderType.nam,
        dob=date(1998, 1, 15),
        height_cm=175, weight_kg=52,
        activity=ActivityLevelType.van_dong_nhe,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.tang_co,
        target_weight=68,
        allergies=None,
        disliked_foods="sữa",
        preferred_foods="cơm, thịt",
        lifestyle_score=5,
    ),
    # 4. Thiếu cân nghiêm trọng, sinh hoạt rất kém
    dict(
        full_name="Pham Thi D",
        gender=GenderType.nu,
        dob=date(2000, 11, 3),
        height_cm=162, weight_kg=43,
        activity=ActivityLevelType.it_van_dong,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.tang_co,
        target_weight=52,
        allergies=None,
        disliked_foods="thịt, cá",
        preferred_foods="trái cây, nước ép",
        lifestyle_score=1,  # rất kém - hay thức khuya, bỏ bữa
    ),
    # 5. Bình thường, sinh hoạt tốt
    dict(
        full_name="Hoang Van E",
        gender=GenderType.nam,
        dob=date(1993, 3, 28),
        height_cm=172, weight_kg=68,
        activity=ActivityLevelType.van_dong_nhieu,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.giu_can,
        target_weight=68,
        allergies=None,
        disliked_foods=None,
        preferred_foods="gà, cá hồi, rau xanh",
        lifestyle_score=9,
    ),
    # 6. Người ăn chay
    dict(
        full_name="Nguyen Thi F",
        gender=GenderType.nu,
        dob=date(1997, 7, 14),
        height_cm=155, weight_kg=50,
        activity=ActivityLevelType.van_dong_nhe,
        diet=DietTypeEnum.an_chay,
        goal_type=NutritionGoalType.giu_can,
        target_weight=50,
        allergies=None,
        disliked_foods="thịt, cá, hải sản",
        preferred_foods="đậu, rau củ, nấm",
        lifestyle_score=7,
    ),
    # 7. Vận động viên - tăng cơ
    dict(
        full_name="Do Van G",
        gender=GenderType.nam,
        dob=date(1994, 9, 5),
        height_cm=178, weight_kg=72,
        activity=ActivityLevelType.van_dong_rat_nhieu,
        diet=DietTypeEnum.nhieu_dam,
        goal_type=NutritionGoalType.tang_co,
        target_weight=78,
        allergies=None,
        disliked_foods="đồ ngọt",
        preferred_foods="ức gà, gạo lứt, trứng, sữa",
        lifestyle_score=8,
    ),
    # 8. Nhân viên văn phòng - sinh hoạt không tốt
    dict(
        full_name="Tran Van H",
        gender=GenderType.nam,
        dob=date(1991, 12, 20),
        height_cm=168, weight_kg=76,
        activity=ActivityLevelType.van_dong_nhe,
        diet=DietTypeEnum.it_tinh_bot,
        goal_type=NutritionGoalType.giam_can,
        target_weight=68,
        allergies="dị ứng gluten nhẹ",
        disliked_foods="cá",
        preferred_foods="cơm trắng, thịt heo",
        lifestyle_score=3,  # ngồi nhiều, hay ăn đêm, ít ngủ
    ),
    # 9. Keto - người béo
    dict(
        full_name="Le Thi I",
        gender=GenderType.nu,
        dob=date(1988, 4, 8),
        height_cm=160, weight_kg=85,
        activity=ActivityLevelType.it_van_dong,
        diet=DietTypeEnum.keto,
        goal_type=NutritionGoalType.giam_can,
        target_weight=60,
        allergies=None,
        disliked_foods="bánh kẹo, cơm",
        preferred_foods="thịt bò, trứng, bơ",
        lifestyle_score=4,
    ),
    # 10. Sinh viên - hay bỏ bữa, ăn vặt nhiều
    dict(
        full_name="Pham Van K",
        gender=GenderType.nam,
        dob=date(2003, 6, 30),
        height_cm=171, weight_kg=60,
        activity=ActivityLevelType.van_dong_vua,
        diet=DietTypeEnum.binh_thuong,
        goal_type=NutritionGoalType.giu_can,
        target_weight=68,
        allergies=None,
        disliked_foods="rau",
        preferred_foods="pizza, burger, trà sữa",
        lifestyle_score=3,  # hay bỏ bữa sáng, ăn đêm, trà sữa nhiều
    ),
]


# ─── Tính TDEE & macro target ─────────────────────────────────────────────────

def calc_bmr(weight_kg: float, height_cm: float, age: int, gender: GenderType) -> float:
    if gender == GenderType.nam:
        return 88.362 + 13.397 * weight_kg + 4.799 * height_cm - 5.677 * age
    return 447.593 + 9.247 * weight_kg + 3.098 * height_cm - 4.330 * age

def activity_multiplier(level: ActivityLevelType) -> float:
    mapping = {
        ActivityLevelType.it_van_dong: 1.2,
        ActivityLevelType.van_dong_nhe: 1.375,
        ActivityLevelType.van_dong_vua: 1.55,
        ActivityLevelType.van_dong_nhieu: 1.725,
        ActivityLevelType.van_dong_rat_nhieu: 1.9,
    }
    return mapping.get(level, 1.2)

def calc_targets(user: dict) -> dict:
    weight = user["weight_kg"]
    height = user["height_cm"]
    today = date.today()
    age = today.year - user["dob"].year - ((today.month, today.day) < (user["dob"].month, user["dob"].day))
    bmr = calc_bmr(weight, height, age, user["gender"])
    tdee = bmr * activity_multiplier(user["activity"])
    goal = user["goal_type"]

    if goal == NutritionGoalType.giam_can:
        cal = tdee - 500
    elif goal == NutritionGoalType.tang_co:
        cal = tdee + 350
    else:
        cal = tdee

    protein_ratio = 0.30 if goal == NutritionGoalType.tang_co else 0.25
    fat_ratio = 0.30 if user["diet"] == DietTypeEnum.keto else 0.25
    protein_g = (cal * protein_ratio) / 4
    fat_g = (cal * fat_ratio) / 9
    carb_g = (cal - protein_g * 4 - fat_g * 9) / 4

    return {
        "bmr_kcal": round(bmr, 1),
        "tdee_kcal": round(tdee, 1),
        "daily_calorie_target": round(cal, 1),
        "protein_target_g": round(protein_g, 1),
        "carb_target_g": round(carb_g, 1),
        "fat_target_g": round(fat_g, 1),
    }


# ─── Chọn thực phẩm theo diet type ────────────────────────────────────────────

def pick_foods(diet: DietTypeEnum, meal_type: MealTypeEnum, calorie_budget: float) -> list[dict]:
    pool = []
    if diet == DietTypeEnum.an_chay or diet == DietTypeEnum.thuan_chay:
        pool = CHAY_FOODS
    elif meal_type == MealTypeEnum.bua_sang:
        pool = BREAKFAST_FOODS
    elif meal_type == MealTypeEnum.bua_trua:
        pool = LUNCH_FOODS
    elif meal_type == MealTypeEnum.bua_toi:
        pool = DINNER_FOODS
    else:
        pool = SNACK_FOODS

    selected = []
    total = 0.0
    while pool:
        food_key = random.choice(pool)
        food = FOOD_DB[food_key]
        # Giảm/bớt calo cho phù hợp bữa ăn
        scale = random.uniform(0.6, 1.3)
        cal = food["cal"] * scale
        if total + cal > calorie_budget * 1.1:
            break
        selected.append({
            "name": food_key,
            "cal": round(cal, 1),
            "protein": round(food["protein"] * scale, 1),
            "carb": round(food["carb"] * scale, 1),
            "fat": round(food["fat"] * scale, 1),
            "weight": round(food["weight"] * scale, 1),
        })
        total += cal
    return selected


# ─── Seed logic ───────────────────────────────────────────────────────────────

async def _create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def seed_demo_data():
    """Tạo 10 user, mỗi user 10 ngày dữ liệu (3 bữa chính + bữa phụ)."""
    await _create_tables()

    async with AsyncSessionLocal() as db:
        # Xóa dữ liệu cũ
        await db.execute(text("DELETE FROM conversation_insights"))
        await db.execute(text("DELETE FROM chat_messages"))
        await db.execute(text("DELETE FROM chat_sessions"))
        await db.execute(text("DELETE FROM meal_items"))
        await db.execute(text("DELETE FROM meal_logs"))
        await db.execute(text("DELETE FROM progress_logs"))
        await db.execute(text("DELETE FROM nutrition_goals"))
        await db.execute(text("DELETE FROM user_profiles"))
        await db.execute(text("DELETE FROM users"))
        await db.commit()
        print("Đã xóa dữ liệu cũ.")

        all_users = []

        for idx, udata in enumerate(USERS, 1):
            print(f"\n[{idx}/10] Tạo: {udata['full_name']}")

            # ── User
            user = User(
                email=f"user{idx}@smartmeal.local",
                password_hash="$2b$12$sDASjwOSDOFON/9f687IC.v4rL11cgPyfpvjrnHDnqapKGSOpT5aC",  # Password: SmartMeal123
                full_name=udata["full_name"],
                role="user",
                is_active=True,
                is_verified=True,
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
                activity_level=udata["activity"],
                diet_type=udata["diet"],
                allergies=udata["allergies"],
                disliked_foods=udata["disliked_foods"],
                preferred_foods=udata["preferred_foods"],
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

            # ── 10 ngày dữ liệu
            start_day = date.today() - timedelta(days=9)

            for day_offset in range(10):
                day = start_day + timedelta(days=day_offset)

                # Bữa sáng
                breakfast_budget = targets["daily_calorie_target"] * 0.25
                breakfast_foods = pick_foods(udata["diet"], MealTypeEnum.bua_sang, breakfast_budget)
                await _create_meal(db, user.id, goal.id, MealTypeEnum.bua_sang, day,
                                   hour=7 + random.randint(0, 2), foods=breakfast_foods)

                # Bữa trưa
                lunch_budget = targets["daily_calorie_target"] * 0.35
                lunch_foods = pick_foods(udata["diet"], MealTypeEnum.bua_trua, lunch_budget)
                await _create_meal(db, user.id, goal.id, MealTypeEnum.bua_trua, day,
                                   hour=12 + random.randint(0, 1), foods=lunch_foods)

                # Bữa tối
                dinner_budget = targets["daily_calorie_target"] * 0.30
                dinner_foods = pick_foods(udata["diet"], MealTypeEnum.bua_toi, dinner_budget)
                await _create_meal(db, user.id, goal.id, MealTypeEnum.bua_toi, day,
                                   hour=18 + random.randint(0, 2), foods=dinner_foods)

                # Bữa phụ / ăn vặt (random)
                snack_prob = udata["lifestyle_score"] / 10.0
                if random.random() < snack_prob:
                    # Ăn vặt sáng
                    if random.random() < 0.4:
                        snack_budget = targets["daily_calorie_target"] * 0.05
                        snack_foods = pick_foods(udata["diet"], MealTypeEnum.an_vat, snack_budget)
                        await _create_meal(db, user.id, goal.id, MealTypeEnum.an_vat, day,
                                           hour=10 + random.randint(0, 2), foods=snack_foods)

                    # Ăn vặt chiều
                    if random.random() < 0.4:
                        snack_budget2 = targets["daily_calorie_target"] * 0.05
                        snack_foods2 = pick_foods(udata["diet"], MealTypeEnum.an_vat, snack_budget2)
                        await _create_meal(db, user.id, goal.id, MealTypeEnum.an_vat, day,
                                           hour=15 + random.randint(0, 1), foods=snack_foods2)

                # Người sinh hoạt kém → hay bỏ bữa
                if udata["lifestyle_score"] <= 3:
                    if random.random() < 0.3:
                        pass  # bỏ bữa sáng
                    if random.random() < 0.2:
                        pass  # bỏ bữa trưa
                    # Ăn đêm (lúc 22-23h)
                    if random.random() < 0.35:
                        late_foods = pick_foods(udata["diet"], MealTypeEnum.khac, 200)
                        await _create_meal(db, user.id, goal.id, MealTypeEnum.khac, day,
                                           hour=22 + random.randint(0, 1), foods=late_foods)

            # ── Progress logs (2-3 lần trong 10 ngày, không trùng ngày)
            progress_count = random.randint(2, 3)
            used_days = set()
            for _ in range(progress_count):
                available = [d for d in range(2, 9) if d not in used_days]
                if not available:
                    break
                chosen = random.choice(available)
                used_days.add(chosen)
                p_day = start_day + timedelta(days=chosen)
                weight_variation = random.uniform(-0.5, 0.5)
                log_weight = udata["weight_kg"] + weight_variation
                progress = ProgressLog(
                    user_id=user.id,
                    log_date=p_day,
                    weight_kg=round(log_weight, 2),
                    note=f"Theo dõi ngày {p_day.strftime('%d/%m')}",
                )
                db.add(progress)

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
            chat_pairs = [
                ("user", f"Cho tôi hỏi về chế độ ăn giảm cân hiệu quả"),
                ("assistant", "Để giảm cân hiệu quả, bạn nên..."),
                ("user", f"Tôi bị {udata['allergies'] or 'không có dị ứng'}. Có ảnh hưởng gì không?"),
                ("assistant", "Bạn nên tránh các thực phẩm gây dị ứng..."),
            ]
            for role, content in chat_pairs:
                msg = ChatMessage(
                    session_id=session.id,
                    role=role,
                    content=content,
                )
                db.add(msg)

            # Conversation insight mẫu
            if udata["allergies"]:
                insight = ConversationInsight(
                    user_id=user.id,
                    session_id=session.id,
                    insight_type="health_constraint",
                    key="allergy_seafood" if "hải sản" in udata["allergies"] else "allergy_food",
                    value=udata["allergies"],
                    summary=f"Người dùng {udata['allergies']}",
                    is_active=True,
                )
                db.add(insight)

            all_users.append((user.email, "SmartMeal123"))

        await db.commit()
        print("\n✅ Hoàn tất! Đã tạo 10 users.")
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


if __name__ == "__main__":
    from app.db.session import Base
    asyncio.run(seed_demo_data())
