"""
Migration script: Convert old-format profile fields to schema-compliant format.

Old format (seed_data):
- taste_preferences: dict with string values ("thích", "trung bình")
- cuisine_preferences: list[dict] with id/name/preference
- disliked_foods / favorite_foods: list[dict] with id/food/reason
- eating_speed: string in Vietnamese ("nhanh", "bình thường")
- health_conditions: list[dict] with id/name/severity/status
- allergies: list[dict] with id/allergen/severity/category

New format (Pydantic schema):
- taste_preferences: dict with int 1-5 values
- cuisine_preferences: list[str] of cuisine IDs
- disliked_foods / favorite_foods: list[str] of food names
- eating_speed: enum "slow"|"normal"|"fast"
- health_conditions: list[dict] with condition/severity/note
- allergies: list[dict] with allergen/severity

Run: python -m scripts.fix_profile_format
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_delete, make_cache_key
from app.core.constants import HEALTH_CONDITIONS
from app.db.session import AsyncSessionLocal
from app.models.user_profile import UserProfile


# ─── Mapping tables ───────────────────────────────────────────────────────────

TASTE_MAP = {
    "không thích": 1,
    "không": 1,
    "ít thích": 2,
    "trung bình": 3,
    "bình thường": 3,
    "thích": 4,
    "rất thích": 5,
}

EATING_SPEED_MAP = {
    "rất chậm": "slow",
    "chậm": "slow",
    "slow": "slow",
    "bình thường": "normal",
    "trung bình": "normal",
    "normal": "normal",
    "nhanh": "fast",
    "rất nhanh": "fast",
    "fast": "fast",
}

CUISINE_NAME_TO_ID = {
    "Việt Nam": "vietnamese",
    "Hàn Quốc": "korean",
    "Nhật Bản": "japanese",
    "Trung Quốc": "chinese",
    "Thái Lan": "thai",
    "Địa Trung Hải": "mediterranean",
    "Phương Tây": "western",
    "Ý": "western",
    "Ấn Độ": "indian",
    "Trung Đông": "middle_eastern",
    "Fast food": "fusion",
    "Nhanh (fast food)": "fusion",
    "Nhanh (quick meals)": "fusion",
    "Healthy/clean eating": "fusion",
    "Keto-friendly": "fusion",
    "Fusion": "fusion",
}

ALLERGEN_MAP = {
    "hải sản": "shellfish",
    "gluten": "wheat",
}

SEVERITY_MAP = {
    "nhẹ": "mild",
    "vừa": "moderate",
    "nặng": "severe",
    "controlled": "managed",
    "managed": "managed",
    "monitored": "managed",
    "present": "managed",
    "recovered": "resolved",
    "resolved": "resolved",
    "unmanaged": "unmanaged",
}

VALID_CONDITION_IDS = {c["id"] for c in HEALTH_CONDITIONS}

CONDITION_NAME_TO_ID = {
    "prehypertension": "hypertension",
    "hypertension": "hypertension",
    "type2_diabetes": "type2_diabetes",
    "type1_diabetes": "type1_diabetes",
    "diabetes": "type2_diabetes",
    "obesity": "obesity",
    "sedentary_lifestyle": "obesity",
}


def _convert_taste(value):
    """Convert a single taste preference value to int 1-5."""
    if isinstance(value, int):
        return max(1, min(5, value))
    if isinstance(value, str):
        key = value.strip().lower()
        for src, score in TASTE_MAP.items():
            if src.lower() == key:
                return score
    return None


def _convert_eating_speed(value):
    """Convert eating_speed to 'slow'|'normal'|'fast'."""
    if not value:
        return None
    if isinstance(value, str) and value in {"slow", "normal", "fast"}:
        return value
    return EATING_SPEED_MAP.get(value)


def _convert_cuisine(value):
    """Convert cuisine_preferences to list[str] of IDs."""
    if not value:
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            if item in {"vietnamese", "japanese", "korean", "chinese", "thai",
                        "mediterranean", "western", "indian", "middle_eastern", "fusion"}:
                result.append(item)
        elif isinstance(item, dict):
            name = item.get("name")
            if name:
                mapped = CUISINE_NAME_TO_ID.get(name, "fusion")
                if mapped not in result:
                    result.append(mapped)
    return result


def _convert_food_list(value):
    """Convert disliked_foods / favorite_foods to list[str]."""
    if not value:
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            food = item.get("food")
            if food and food not in result:
                result.append(food)
    return result


def _convert_allergies(value):
    """Convert allergies list to schema format."""
    if not value:
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            allergen_raw = item.get("allergen", "")
            allergen = ALLERGEN_MAP.get(allergen_raw, allergen_raw)
            if allergen in {"peanuts", "tree_nuts", "milk", "eggs", "wheat",
                            "soy", "fish", "shellfish", "sesame", "sulfites"}:
                severity_raw = item.get("severity", "moderate")
                severity = SEVERITY_MAP.get(severity_raw, "moderate")
                result.append({"allergen": allergen, "severity": severity})
    return result


def _convert_dietary_restrictions(value):
    """Convert dietary_restrictions to list[str] of restriction IDs."""
    if not value:
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            restriction = item.get("restriction")
            if restriction and restriction not in result:
                result.append(restriction)
    return result


def _convert_medications(value):
    """Convert medications list to schema format."""
    if not value:
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            name = item.get("name")
            if name:
                entry = {"name": name}
                if item.get("dosage"):
                    entry["note"] = f"{item['dosage']}"
                if item.get("frequency"):
                    entry["frequency"] = item["frequency"]
                result.append(entry)
    return result


def _convert_health_conditions(value):
    """Convert health_conditions to schema format. Drops conditions without valid ID mapping."""
    if not value:
        return []
    result = []
    for item in value:
        if not isinstance(item, dict):
            continue
        cond_id_raw = item.get("condition") or item.get("name") or ""
        cond_id = CONDITION_NAME_TO_ID.get(cond_id_raw, cond_id_raw)
        if cond_id not in VALID_CONDITION_IDS:
            continue
        severity_raw = item.get("severity", "managed")
        severity = SEVERITY_MAP.get(severity_raw, "managed")
        result.append({"condition": cond_id, "severity": severity})
    return result


def fix_profile(profile: UserProfile) -> bool:
    """Convert a single profile to schema format. Returns True if changed."""
    changed = False

    if isinstance(profile.taste_preferences, dict):
        new_taste = {}
        for key in ("spicy", "sweet", "salty", "sour", "bitter"):
            val = profile.taste_preferences.get(key)
            if val is not None:
                converted = _convert_taste(val)
                if converted is not None:
                    new_taste[key] = converted
        if new_taste != profile.taste_preferences:
            profile.taste_preferences = new_taste
            changed = True

    new_cuisine = _convert_cuisine(profile.cuisine_preferences)
    if new_cuisine != profile.cuisine_preferences:
        profile.cuisine_preferences = new_cuisine
        changed = True

    new_disliked = _convert_food_list(profile.disliked_foods)
    if new_disliked != profile.disliked_foods:
        profile.disliked_foods = new_disliked
        changed = True

    new_favorite = _convert_food_list(profile.favorite_foods)
    if new_favorite != profile.favorite_foods:
        profile.favorite_foods = new_favorite
        changed = True

    new_speed = _convert_eating_speed(profile.eating_speed)
    if new_speed != profile.eating_speed:
        profile.eating_speed = new_speed
        changed = True

    new_allergies = _convert_allergies(profile.allergies)
    if new_allergies != profile.allergies:
        profile.allergies = new_allergies
        changed = True

    new_diet = _convert_dietary_restrictions(profile.dietary_restrictions)
    if new_diet != profile.dietary_restrictions:
        profile.dietary_restrictions = new_diet
        changed = True

    new_meds = _convert_medications(profile.medications)
    if new_meds != profile.medications:
        profile.medications = new_meds
        changed = True

    new_cond = _convert_health_conditions(profile.health_conditions)
    if new_cond != profile.health_conditions:
        profile.health_conditions = new_cond
        changed = True

    return changed


async def fix_profile_format():
    """Migrate all user_profiles to schema format and invalidate cache."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UserProfile))
        profiles = result.scalars().all()

        fixed_count = 0
        for profile in profiles:
            if fix_profile(profile):
                fixed_count += 1
                try:
                    await cache_delete(make_cache_key("user_profile", str(profile.user_id)))
                except Exception:
                    pass

        if fixed_count > 0:
            await db.commit()

        print(f"[OK] Converted {fixed_count}/{len(profiles)} profile(s) to new format.")


if __name__ == "__main__":
    asyncio.run(fix_profile_format())