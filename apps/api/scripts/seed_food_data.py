#!/usr/bin/env python3
"""
Seed script for SmartMeal food_nutrition database.

Run with:
    python scripts/seed_food_data.py

This script is IDEMPOTENT — running it multiple times will not create duplicates.
It uses INSERT ... ON CONFLICT DO NOTHING to upsert based on food_name.

All nutrition values are sample estimates for demo purposes.
Values are based on general nutritional data and may not reflect exact
restaurant-specific preparations. For production use, cross-reference
with authoritative sources (USDA, Vietnamese food composition tables).
"""

import asyncio
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Add project root to path so we can import app modules
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models.enums import FoodSourceType  # noqa: E402


def _build_engine():
    return create_async_engine(settings.ASYNC_DATABASE_URL, echo=False)

# ─── Seed data ────────────────────────────────────────────────────────────────
# Format: (food_name, food_name_vi, food_name_en, category, serving_size_g,
#          calories, protein, carbs, fat, fiber, sugar, sodium)
#
# All values per 100g (except serving_size_g which is the reference serving).
# Values are SAMPLE ESTIMATES for demo purposes.

VIETNAMESE_FOODS = [
    # ── Phở & nui ────────────────────────────────────────────────────────────
    ("Pho bo", "Phở bò", "Beef pho", "Phở & nui", 100, 110, 7.5, 14.0, 2.5, 0.8, 1.5, 350),
    ("Pho ga", "Phở gà", "Chicken pho", "Phở & nui", 100, 95, 8.0, 13.0, 1.8, 0.6, 1.0, 320),
    ("Hu tieu", "Hủ tiếu", "Hue-style noodle soup", "Phở & nui", 100, 105, 6.5, 15.0, 2.2, 0.7, 1.2, 380),
    ("Mi quang", "Mì Quảng", "Quang noodle", "Phở & nui", 100, 130, 8.5, 17.0, 3.5, 0.8, 2.0, 420),
    ("Bun rieu", "Bún riêu", "Crab tofu noodle soup", "Phở & nui", 100, 100, 7.0, 14.5, 2.0, 0.6, 1.5, 400),
    ("Bun bo Hue", "Bún bò Huế", "Hue beef noodle soup", "Phở & nui", 100, 125, 9.0, 15.5, 3.2, 0.7, 1.8, 450),
    ("Cao lau", "Cao lầu", "Cao lau noodle", "Phở & nui", 100, 145, 5.5, 25.0, 3.0, 1.0, 0.5, 300),
    ("Mien luoc", "Miến lọc", "Cellophane noodle", "Phở & nui", 100, 90, 1.5, 20.0, 0.3, 0.3, 0.1, 200),

    # ── Cơm ───────────────────────────────────────────────────────────────────
    ("Com trang", "Cơm trắng", "Plain white rice", "Cơm", 100, 130, 2.7, 28.0, 0.3, 0.4, 0.1, 1),
    ("Com tam", "Cơm tấm", "Broken rice", "Cơm", 100, 135, 2.8, 29.0, 0.4, 0.4, 0.1, 2),
    ("Com ga", "Cơm gà", "Chicken rice", "Cơm", 100, 165, 10.0, 22.0, 4.0, 0.5, 0.3, 3),
    ("Com suon bi cha", "Cơm sườn bì chả", "Pork chop with shredded pork & pâté on rice", "Cơm", 100, 180, 11.0, 22.0, 5.5, 0.4, 1.5, 450),
    ("Com chay", "Cơm chay", "Vegetarian rice", "Cơm", 100, 120, 2.5, 26.0, 0.5, 0.8, 0.2, 5),
    ("Com chien duong cong", "Cơm chiên Dương Châu", "Yangzhou fried rice", "Cơm", 100, 180, 5.5, 25.0, 6.5, 0.8, 1.0, 380),
    ("Xoi ga", "Xôi gà", "Chicken sticky rice", "Xôi", 100, 200, 9.0, 30.0, 5.0, 0.6, 1.0, 320),
    ("Xoi man", "Xôi mặn", "Savory sticky rice", "Xôi", 100, 190, 7.0, 32.0, 4.5, 0.7, 1.2, 380),
    ("Xoi lac", "Xôi lạc", "Sticky rice with peanuts", "Xôi", 100, 185, 5.0, 33.0, 4.0, 1.5, 2.0, 50),
    ("Che troi nuoc", "Chè trôi nước", "Sweet glutinous rice balls", "Chè & tráng miệng", 100, 175, 3.5, 30.0, 4.0, 1.0, 12.0, 40),

    # ── Bún & bánh hỏi ───────────────────────────────────────────────────────
    ("Bun thit nuong", "Bún thịt nướng", "Grilled pork noodle bowl", "Bún", 100, 145, 10.0, 18.0, 3.5, 1.0, 3.0, 400),
    ("Bun cha", "Bún chả", "Grilled pork & noodle soup (Hanoi style)", "Bún", 100, 155, 11.0, 17.0, 4.5, 0.8, 2.5, 420),
    ("Bun nem", "Bún nem", "Noodle with nem chua (fermented pork)", "Bún", 100, 150, 12.0, 16.0, 5.0, 0.6, 1.8, 500),
    ("Banh hoi", "Bánh hỏi", "Fine rice vermicelli sheets", "Bún", 100, 75, 2.0, 16.0, 0.3, 0.3, 0.1, 5),

    # ── Bánh mì & bánh bao ───────────────────────────────────────────────────
    ("Banh mi thit", "Bánh mì thịt", "Vietnamese pork sandwich", "Bánh mì", 100, 220, 10.0, 25.0, 8.0, 1.2, 3.5, 480),
    ("Banh mi cha ca", "Bánh mì chả cá", "Fish cake banh mi", "Bánh mì", 100, 195, 9.5, 26.0, 6.0, 1.0, 2.8, 420),
    ("Banh bao", "Bánh bao", "Steamed buns", "Bánh mì", 100, 180, 6.0, 30.0, 3.5, 1.2, 4.0, 350),
    ("Banh pat", "Bánh pía", "Bánh pía (pastry with mung bean)", "Bánh mì", 100, 210, 4.5, 32.0, 6.5, 1.5, 8.0, 180),

    # ── Món chiên & xào ──────────────────────────────────────────────────────
    ("Cha gio", "Chả giò", "Fried spring roll (Nem rán)", "Chiên & xào", 100, 220, 7.0, 22.0, 11.0, 1.5, 2.0, 350),
    ("Nom thit", "Nộm thịt", "Spicy pork salad", "Chiên & xào", 100, 135, 14.0, 8.0, 5.5, 2.0, 3.0, 550),
    ("Rau muong xao", "Rau muống xào", "Stir-fried water spinach", "Chiên & xào", 100, 65, 3.0, 7.0, 2.8, 2.5, 0.5, 400),
    ("Ca kho to", "Cá kho tộ", "Braised fish in clay pot", "Kho & rim", 100, 165, 18.0, 8.0, 7.0, 0.3, 4.5, 650),
    ("Thit kho trung", "Thịt kho trứng", "Braised pork belly with eggs", "Kho & rim", 100, 250, 14.0, 6.0, 18.0, 0.2, 3.0, 500),
    ("Canh chua", "Canh chua", "Sour soup (with fish & vegetables)", "Canh & súp", 100, 45, 5.0, 4.0, 1.2, 0.8, 1.5, 280),
    ("Canh rau", "Canh rau", "Vegetable soup", "Canh & súp", 100, 30, 1.5, 4.5, 0.8, 1.0, 1.0, 180),

    # ── Gỏi cuốn & đồ ăn vặt ────────────────────────────────────────────────
    ("Goi cuon", "Gỏi cuốn", "Fresh spring roll", "Gỏi & cuốn", 100, 90, 6.0, 13.0, 1.5, 1.2, 2.0, 220),
    ("Goi cuon chay", "Gỏi cuốn chay", "Vegetarian fresh spring roll", "Gỏi & cuốn", 100, 80, 3.0, 14.0, 1.2, 1.5, 2.5, 150),
    ("Cha la lot", "Chả lụa", "Vietnamese pork roll", "Gỏi & cuốn", 100, 230, 13.0, 2.0, 18.0, 0.0, 0.5, 650),
    ("Cha bong", "Chả bông", "Shredded pork floss", "Gỏi & cuốn", 100, 280, 28.0, 8.0, 15.0, 0.0, 0.0, 900),
    ("Miến tron", "Miến trộn", "Mixed cellophane noodle salad", "Gỏi & cuốn", 100, 160, 5.0, 24.0, 5.0, 1.0, 3.5, 450),

    # ── Gà ───────────────────────────────────────────────────────────────────
    ("Ga ran", "Gà rán", "Fried chicken", "Gà", 100, 240, 18.0, 10.0, 14.0, 0.3, 0.0, 350),
    ("Ga nuong", "Gà nướng", "Grilled chicken", "Gà", 100, 170, 22.0, 5.0, 8.0, 0.2, 0.0, 280),
    ("Ga xien", "Gà xèo", "Sizzling chicken", "Gà", 100, 195, 21.0, 6.0, 10.0, 0.3, 0.5, 320),
    ("Chao ga", "Cháo gà", "Chicken congee", "Cháo", 100, 85, 5.0, 13.0, 1.5, 0.5, 0.8, 200),

    # ── Thịt bò ──────────────────────────────────────────────────────────────
    ("Bo kho", "Bò kho", "Beef stew", "Thịt bò", 100, 155, 16.0, 8.0, 6.5, 0.8, 1.5, 400),
    ("Bo luc lac", "Bò lúc lắc", "Shaking beef", "Thịt bò", 100, 200, 22.0, 5.0, 10.0, 0.3, 1.0, 350),
    ("Tai ga", "Tái gà", "Rare chicken (blood & tendon)", "Gà", 100, 160, 20.0, 3.0, 8.0, 0.0, 0.0, 280),

    # ── Đồ uống & sữa ────────────────────────────────────────────────────────
    ("Sua chua", "Sữa chua", "Yogurt", "Sữa & đồ uống", 100, 85, 5.0, 11.0, 2.0, 0.0, 8.0, 55),
    ("Sua dac", "Sữa đặc", "Condensed milk", "Sữa & đồ uống", 100, 320, 8.0, 54.0, 8.7, 0.0, 52.0, 130),
    ("Sua tuoi", "Sữa tươi", "Fresh milk", "Sữa & đồ uống", 100, 60, 3.2, 4.8, 3.3, 0.0, 5.0, 40),
    ("Yen mach", "Yến mạch", "Oatmeal", "Sữa & đồ uống", 100, 68, 2.4, 12.0, 1.4, 1.7, 0.5, 3),
    ("Nuoc cam", "Nước cam", "Orange juice", "Sữa & đồ uống", 100, 45, 0.7, 10.5, 0.2, 0.2, 8.4, 1),
    ("Ca phe sua da", "Cà phê sữa đá", "Iced coffee with milk", "Sữa & đồ uống", 100, 55, 1.5, 9.0, 1.5, 0.0, 7.0, 20),
    ("Tra da", "Trà đá", "Iced tea", "Sữa & đồ uống", 100, 1, 0.0, 0.3, 0.0, 0.0, 0.0, 2),

    # ── Trứng ─────────────────────────────────────────────────────────────────
    ("Trung chien", "Trứng chiên", "Fried egg", "Trứng", 100, 196, 14.0, 1.0, 15.0, 0.0, 1.0, 350),
    ("Trung luoc", "Trứng luộc", "Boiled egg", "Trứng", 100, 155, 13.0, 1.1, 11.0, 0.0, 1.1, 140),
    ("Trung cut chien", "Trứng cút chiên", "Quail egg fried", "Trứng", 100, 220, 18.0, 2.0, 15.0, 0.0, 2.0, 380),

    # ── Thực phẩm cơ bản ────────────────────────────────────────────────────
    ("Ucs gia", "Ức gà", "Chicken breast", "Thịt & cá", 100, 110, 23.0, 0.0, 1.2, 0.0, 0.0, 74),
    ("Thit lon", "Thịt lợn nạc", "Lean pork", "Thịt & cá", 100, 145, 21.0, 0.0, 6.5, 0.0, 0.0, 62),
    ("Thit bo", "Thịt bò nạc", "Lean beef", "Thịt & cá", 100, 135, 22.0, 0.0, 5.0, 0.0, 0.0, 55),
    ("Ca loc", "Cá lóc", "Snakehead fish", "Thịt & cá", 100, 95, 18.0, 0.0, 2.5, 0.0, 0.0, 65),
    ("Ca hoi", "Cá hồi", "Salmon", "Thịt & cá", 100, 208, 20.0, 0.0, 13.0, 0.0, 0.0, 59),

    # ── Rau củ quả ───────────────────────────────────────────────────────────
    ("Khoai lang", "Khoai lang", "Sweet potato", "Rau củ", 100, 86, 1.6, 20.0, 0.1, 3.0, 4.2, 28),
    ("Chuoi", "Chuối", "Banana", "Rau củ", 100, 89, 1.1, 23.0, 0.3, 2.6, 12.0, 1),
    ("Xoai", "Xoài", "Mango", "Rau củ", 100, 60, 0.8, 15.0, 0.4, 1.6, 14.0, 1),
    ("Dua chuot", "Dưa chuột", "Cucumber", "Rau củ", 100, 15, 0.7, 3.6, 0.1, 0.5, 1.7, 2),
    ("Ca chua", "Cà chua", "Tomato", "Rau củ", 100, 18, 0.9, 3.9, 0.2, 1.2, 2.5, 5),
    ("Rau muong", "Rau muống", "Water spinach (morning glory)", "Rau củ", 100, 23, 2.6, 3.1, 0.4, 2.1, 0.9, 85),
    ("Dau hu", "Đậu hũ", "Tofu", "Đậu & ngũ cốc", 100, 76, 8.0, 1.9, 4.8, 0.3, 0.7, 7),
    ("Dau xanh", "Đậu xanh", "Mung bean", "Đậu & ngũ cốc", 100, 100, 7.0, 18.0, 0.4, 3.8, 1.2, 2),
    ("Gao lua", "Gạo lứt", "Brown rice", "Đậu & ngũ cốc", 100, 111, 2.6, 23.0, 0.9, 1.8, 0.4, 4),
]


async def seed_food_data():
    """Insert seed foods into the food_nutrition table."""
    engine = _build_engine()
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Check how many foods already exist
        count_result = await session.execute(text("SELECT COUNT(*) FROM food_nutrition"))
        existing_count = count_result.scalar()
        logger.info("[Seed] Current food_nutrition count: %s", existing_count)

        # Upsert each food — idempotent
        inserted = 0
        skipped = 0
        for food in VIETNAMESE_FOODS:
            (
                food_name, food_name_vi, food_name_en, category,
                serving_size_g, calories, protein, carbs, fat,
                fiber, sugar, sodium
            ) = food

            result = await session.execute(
                text("""
                    INSERT INTO food_nutrition
                        (food_name, food_name_vi, food_name_en, category, serving_size_g,
                         calories_per_100g, protein_per_100g, carb_per_100g, fat_per_100g,
                         fiber_per_100g, sugar_per_100g, sodium_mg_per_100g,
                         source, is_verified)
                    VALUES
                        (:food_name, :food_name_vi, :food_name_en, :category, :serving_size_g,
                         :calories, :protein, :carbs, :fat,
                         :fiber, :sugar, :sodium,
                         :source, :is_verified)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """),
                {
                    "food_name": food_name,
                    "food_name_vi": food_name_vi,
                    "food_name_en": food_name_en,
                    "category": category,
                    "serving_size_g": serving_size_g,
                    "calories": calories,
                    "protein": protein,
                    "carbs": carbs,
                    "fat": fat,
                    "fiber": fiber,
                    "sugar": sugar,
                    "sodium": sodium,
                    "source": FoodSourceType.he_thong.value,
                    "is_verified": True,
                },
            )
            row = result.fetchone()
            if row:
                inserted += 1
            else:
                skipped += 1

        await session.commit()

        final_count_result = await session.execute(text("SELECT COUNT(*) FROM food_nutrition"))
        final_count = final_count_result.scalar()
        logger.info("[Seed] Done. Inserted: %d, Skipped (already existed): %d", inserted, skipped)
        logger.info("[Seed] New total count: %s", final_count)

    await engine.dispose()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("SmartMeal Food Nutrition Seed Script (idempotent)")
    logger.info("NOTE: All nutrition values are SAMPLE ESTIMATES for demo.")

    env = settings.ENVIRONMENT.lower()
    if env in {"production", "prod"}:
        logger.error("Refusing to run seed in production mode.")
        logger.error("Set ENVIRONMENT=development in your .env to run seeds.")
        sys.exit(1)

    asyncio.run(seed_food_data())
    logger.info("[Seed] Complete.")


if __name__ == "__main__":
    main()
