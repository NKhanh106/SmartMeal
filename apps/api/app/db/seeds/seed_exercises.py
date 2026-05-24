"""
Seed script — migrate hardcoded exercises from workout_plans.py into the DB.

Run once:
    python -m app.db.seeds.seed_exercises

Or import and call seed_exercises() directly.
"""

import asyncio
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, AsyncSessionLocal

logger = logging.getLogger(__name__)


def _infer_sets(exercise: dict) -> int:
    sets_str = str(exercise.get("sets", 3))
    if sets_str.isdigit():
        return int(sets_str)
    return 3


def _infer_reps(exercise: dict) -> int:
    reps_str = str(exercise.get("reps", 12))
    if reps_str.isdigit():
        return int(reps_str)
    return 12


def _infer_rest(exercise: dict) -> int:
    rest_str = str(exercise.get("rest_seconds", 60))
    if rest_str.isdigit():
        return int(rest_str)
    return 60


EXERCISES_DATA = [
    # ── Weight Loss (giam_can) ──────────────────────────────────────────────────
    {"name": "Push-ups", "category": "strength", "muscle_group": "Full Body", "difficulty": "nguoi_moi", "sets": 3, "reps": 15, "rest_seconds": 60},
    {"name": "Bodyweight Squats", "category": "strength", "muscle_group": "Full Body", "difficulty": "nguoi_moi", "sets": 3, "reps": 20, "rest_seconds": 60},
    {"name": "Jumping Jacks", "category": "cardio", "muscle_group": "Cardio", "difficulty": "nguoi_moi", "sets": 3, "reps": 30, "rest_seconds": 45},
    {"name": "Lunges", "category": "strength", "muscle_group": "Full Body", "difficulty": "nguoi_moi", "sets": 3, "reps": 12, "rest_seconds": 60},
    {"name": "Plank", "category": "strength", "muscle_group": "Core", "difficulty": "nguoi_moi", "sets": 3, "reps": 30, "rest_seconds": 45},
    {"name": "Burpees", "category": "cardio", "muscle_group": "Cardio", "difficulty": "trung_binh", "sets": 3, "reps": 10, "rest_seconds": 60},
    {"name": "Dips", "category": "strength", "muscle_group": "Upper Body", "difficulty": "trung_binh", "sets": 3, "reps": 12, "rest_seconds": 60},
    {"name": "Glute Bridges", "category": "strength", "muscle_group": "Lower Body", "difficulty": "nguoi_moi", "sets": 3, "reps": 15, "rest_seconds": 60},
    {"name": "Mountain Climbers", "category": "cardio", "muscle_group": "Cardio", "difficulty": "trung_binh", "sets": 3, "reps": 20, "rest_seconds": 45},
    {"name": "Bicycle Crunches", "category": "strength", "muscle_group": "Core", "difficulty": "nguoi_moi", "sets": 3, "reps": 20, "rest_seconds": 45},
    {"name": "Pike Push-ups", "category": "strength", "muscle_group": "Upper Body", "difficulty": "trung_binh", "sets": 3, "reps": 10, "rest_seconds": 60},
    {"name": "Step-ups", "category": "strength", "muscle_group": "Lower Body", "difficulty": "nguoi_moi", "sets": 3, "reps": 12, "rest_seconds": 60},
    {"name": "High Knees", "category": "cardio", "muscle_group": "Cardio", "difficulty": "nguoi_moi", "sets": 3, "reps": 30, "rest_seconds": 45},
    {"name": "Superman Hold", "category": "strength", "muscle_group": "Back", "difficulty": "nguoi_moi", "sets": 3, "reps": 12, "rest_seconds": 45},
    {"name": "Jump Squats", "category": "cardio", "muscle_group": "Cardio", "difficulty": "trung_binh", "sets": 3, "reps": 15, "rest_seconds": 60},
    {"name": "Leg Raises", "category": "strength", "muscle_group": "Core", "difficulty": "nguoi_moi", "sets": 3, "reps": 15, "rest_seconds": 45},

    # ── Muscle Gain (tang_co) ──────────────────────────────────────────────────
    {"name": "Push-ups", "category": "strength", "muscle_group": "Chest", "difficulty": "trung_binh", "sets": 4, "reps": 10, "rest_seconds": 90},
    {"name": "Superman Hold", "category": "strength", "muscle_group": "Back", "difficulty": "nguoi_moi", "sets": 4, "reps": 10, "rest_seconds": 60},
    {"name": "Diamond Push-ups", "category": "strength", "muscle_group": "Triceps", "difficulty": "trung_binh", "sets": 3, "reps": 8, "rest_seconds": 90},
    {"name": "Bodyweight Squats", "category": "strength", "muscle_group": "Legs", "difficulty": "trung_binh", "sets": 4, "reps": 12, "rest_seconds": 90},
    {"name": "Lunges", "category": "strength", "muscle_group": "Legs", "difficulty": "trung_binh", "sets": 3, "reps": 10, "rest_seconds": 90},
    {"name": "Glute Bridges", "category": "strength", "muscle_group": "Glutes", "difficulty": "nguoi_moi", "sets": 4, "reps": 12, "rest_seconds": 60},
    {"name": "Pike Push-ups", "category": "strength", "muscle_group": "Shoulders", "difficulty": "trung_binh", "sets": 4, "reps": 8, "rest_seconds": 90},
    {"name": "Reverse Snow Angels", "category": "strength", "muscle_group": "Back", "difficulty": "nguoi_moi", "sets": 3, "reps": 12, "rest_seconds": 60},
    {"name": "Plank", "category": "strength", "muscle_group": "Core", "difficulty": "nguoi_moi", "sets": 3, "reps": 45, "rest_seconds": 60},
    {"name": "Wide Push-ups", "category": "strength", "muscle_group": "Chest", "difficulty": "trung_binh", "sets": 4, "reps": 10, "rest_seconds": 90},
    {"name": "Doorway Curls", "category": "strength", "muscle_group": "Biceps", "difficulty": "nguoi_moi", "sets": 3, "reps": 12, "rest_seconds": 60},
    {"name": "Jump Squats", "category": "cardio", "muscle_group": "Legs", "difficulty": "trung_binh", "sets": 3, "reps": 10, "rest_seconds": 90},
    {"name": "Burpees", "category": "cardio", "muscle_group": "Full Body", "difficulty": "nang_cao", "sets": 4, "reps": 8, "rest_seconds": 90},
    {"name": "Bicycle Crunches", "category": "strength", "muscle_group": "Core", "difficulty": "nguoi_moi", "sets": 3, "reps": 20, "rest_seconds": 60},

    # ── Maintenance (giu_can) ───────────────────────────────────────────────────
    {"name": "Push-ups", "category": "strength", "muscle_group": "Full Body", "difficulty": "trung_binh", "sets": 3, "reps": 12, "rest_seconds": 75},
    {"name": "Bodyweight Squats", "category": "strength", "muscle_group": "Legs", "difficulty": "trung_binh", "sets": 3, "reps": 15, "rest_seconds": 75},
    {"name": "Plank", "category": "strength", "muscle_group": "Core", "difficulty": "trung_binh", "sets": 3, "reps": 30, "rest_seconds": 60},
    {"name": "Lunges", "category": "strength", "muscle_group": "Full Body", "difficulty": "trung_binh", "sets": 3, "reps": 12, "rest_seconds": 75},
    {"name": "Dips", "category": "strength", "muscle_group": "Upper Body", "difficulty": "trung_binh", "sets": 3, "reps": 10, "rest_seconds": 75},
    {"name": "Jumping Jacks", "category": "cardio", "muscle_group": "Cardio", "difficulty": "nguoi_moi", "sets": 3, "reps": 30, "rest_seconds": 45},
    {"name": "Glute Bridges", "category": "strength", "muscle_group": "Full Body", "difficulty": "nguoi_moi", "sets": 3, "reps": 15, "rest_seconds": 60},
    {"name": "Bicycle Crunches", "category": "strength", "muscle_group": "Core", "difficulty": "nguoi_moi", "sets": 3, "reps": 15, "rest_seconds": 60},
    {"name": "Superman Hold", "category": "strength", "muscle_group": "Back", "difficulty": "nguoi_moi", "sets": 3, "reps": 10, "rest_seconds": 60},
    {"name": "Step-ups", "category": "strength", "muscle_group": "Legs", "difficulty": "nguoi_moi", "sets": 3, "reps": 12, "rest_seconds": 75},
    {"name": "Mountain Climbers", "category": "cardio", "muscle_group": "Cardio", "difficulty": "trung_binh", "sets": 3, "reps": 20, "rest_seconds": 60},
    {"name": "Burpees", "category": "cardio", "muscle_group": "Full Body", "difficulty": "trung_binh", "sets": 3, "reps": 8, "rest_seconds": 75},
    {"name": "Leg Raises", "category": "strength", "muscle_group": "Core", "difficulty": "trung_binh", "sets": 3, "reps": 12, "rest_seconds": 60},
    {"name": "Pike Push-ups", "category": "strength", "muscle_group": "Upper Body", "difficulty": "trung_binh", "sets": 3, "reps": 8, "rest_seconds": 75},
]


async def seed_exercises(session: AsyncSession) -> int:
    from app.models.exercise import Exercise

    added = 0
    for ex_data in EXERCISES_DATA:
        exercise = Exercise(
            id=uuid4(),
            name=ex_data["name"],
            category=ex_data["category"],
            muscle_group=ex_data["muscle_group"],
            difficulty=ex_data["difficulty"],
            default_sets=_infer_sets(ex_data),
            default_reps=_infer_reps(ex_data),
            default_rest_seconds=_infer_rest(ex_data),
            equipment_needed=False,
            is_active=True,
        )
        session.add(exercise)
        added += 1

    await session.commit()
    return added


async def main() -> None:
    logger.info("Seeding exercises into database...")
    async with AsyncSessionLocal() as session:
        added = await seed_exercises(session)
        logger.info("Seeded %d exercises", added)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
