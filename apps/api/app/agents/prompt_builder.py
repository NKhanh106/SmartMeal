"""
Converts FullUserContext → optimized prompt strings per agent.
Each builder returns ONLY what that agent needs — no noise.

These functions are the ONLY place context strings are assembled.
All agents should call these instead of building strings inline.
"""

from app.agents.context_loader import FullUserContext


# ─── Shared utilities ──────────────────────────────────────────────────────────


def _str_list(items: list, max_items: int = 5) -> str:
    return ", ".join(str(i) for i in items[:max_items])


def _goal_label(goal: str | None) -> str:
    if not goal:
        return "unknown"
    return {
        "muscle_gain": "Tăng cơ",
        "weight_loss": "Giảm cân",
        "weight_gain": "Tăng cân",
        "maintain_shape": "Giữ dáng",
        "medical_treatment": "Điều trị bệnh lý",
        "balanced_lifestyle": "Sinh hoạt điều độ",
        "sports_performance": "Thể thao",
        "tang_co": "Tăng cơ",
        "giam_can": "Giảm cân",
        "giu_can": "Giữ dáng",
    }.get(goal, goal)


def _adherence_label(adherence: str) -> str:
    return {
        "significantly_under": "⚠️ Ăn thiếu nhiều so với mục tiêu",
        "slightly_under":      "Ăn hơi thiếu",
        "on_track":             "✅ Đang đạt mục tiêu",
        "slightly_over":        "Ăn hơi vượt",
        "significantly_over":   "⚠️ Ăn vượt nhiều",
    }.get(adherence, adherence)


# ─── HEALTH MONITOR ───────────────────────────────────────────────────────────


def build_health_monitor_context(ctx: FullUserContext) -> str:
    """
    Health monitor needs: conditions, medications, symptoms, body state,
    lifestyle factors (sleep, stress).
    """
    lines = []

    # Demographics
    if ctx.age or ctx.gender:
        demo = []
        if ctx.age:             demo.append(f"{ctx.age} tuổi")
        if ctx.gender:          demo.append(str(ctx.gender))
        if ctx.body.weight_kg:  demo.append(f"{ctx.body.weight_kg}kg")
        lines.append(f"Demographics: {', '.join(demo)}")

    # Active health conditions
    if ctx.health_conditions:
        active = [c for c in ctx.health_conditions if c.get("severity") != "resolved"]
        if active:
            parts = []
            for c in active:
                sev = c.get("severity", "managed")
                note = f" ({c['note']})" if c.get("note") else ""
                parts.append(f"{c['condition']} [{sev}]{note}")
            lines.append(f"Health conditions: {'; '.join(parts)}")

    # Medications
    if ctx.medications:
        meds = [m.get("name", "") for m in ctx.medications if m.get("name")]
        if meds:
            lines.append(f"Medications: {', '.join(meds)}")

    # Body state
    body_parts = []
    if ctx.body.energy_level and ctx.body.energy_level != "normal":
        body_parts.append(f"energy: {ctx.body.energy_level}")
    if ctx.body.digestion_status and ctx.body.digestion_status != "normal":
        body_parts.append(f"digestion: {ctx.body.digestion_status}")
    if ctx.body.hydration_status and ctx.body.hydration_status != "normal":
        body_parts.append(f"hydration: {ctx.body.hydration_status}")
    if body_parts:
        lines.append(f"Current state: {', '.join(body_parts)}")

    if ctx.body.sore_areas:
        lines.append(f"Sore areas: {', '.join(ctx.body.sore_areas)}")
    if ctx.body.injury_areas:
        lines.append(f"Injury areas: {', '.join(ctx.body.injury_areas)}")

    # Active symptoms (last 7 days)
    if ctx.body.active_symptoms:
        for s in ctx.body.active_symptoms[:3]:
            lines.append(
                f"{s.get('date', '')}: {s.get('description', '')} [{s.get('severity', 'mild')}]"
            )

    # Sleep
    sleep_parts = []
    if ctx.sleep_duration_hours:
        sleep_parts.append(f"{ctx.sleep_duration_hours}h/night")
    if ctx.sleep_quality:
        sleep_parts.append(f"quality {ctx.sleep_quality}")
    if ctx.body.sleep_last_night_hours:
        sleep_parts.append(f"last night {ctx.body.sleep_last_night_hours}h")
    if sleep_parts:
        lines.append(f"Sleep: {', '.join(sleep_parts)}")

    # Stress
    if ctx.stress_level and isinstance(ctx.stress_level, (int, float)) and ctx.stress_level >= 7:
        label = "high"
    elif ctx.stress_level and isinstance(ctx.stress_level, (int, float)) and ctx.stress_level >= 4:
        label = "medium"
    else:
        label = "low"
        lines.append(f"Stress: {ctx.stress_level}/10 ({label})")

    # Health risk flags
    if ctx.health_risk_flags:
        lines.append(f"Risk flags: {', '.join(ctx.health_risk_flags[:5])}")

    # Key facts (health-related)
    health_facts = [
        f for f in ctx.key_facts
        if any(kw in f.lower() for kw in ["bệnh", "thuốc", "dị ứng", "kiêng", "không ăn", "không uống"])
    ]
    if health_facts:
        lines.append(f"Key facts: {'; '.join(health_facts[:3])}")

    return "\n".join(lines) if lines else "No detailed health data available."


# ─── NUTRITION ADVISOR ───────────────────────────────────────────────────────


def build_nutrition_advisor_context(ctx: FullUserContext) -> str:
    """
    Nutrition advisor needs: goals, current intake, preferences,
    restrictions, deficiencies, meal patterns.
    """
    lines = []

    # Goal
    if ctx.usage_goal:
        note = f" — {ctx.usage_goal_note}" if ctx.usage_goal_note else ""
        lines.append(f"Goal: {_goal_label(ctx.usage_goal)}{note}")

    # Physical stats
    if ctx.weight_kg and ctx.age and ctx.gender:
        bmi = None
        if ctx.height_cm:
            bmi = round(ctx.weight_kg / ((ctx.height_cm / 100) ** 2), 1)
        stats = f"{ctx.weight_kg}kg"
        if ctx.height_cm:  stats += f", {ctx.height_cm}cm"
        if bmi:            stats += f", BMI {bmi}"
        lines.append(f"Physical: {stats}")

    # Nutrition targets
    if ctx.nutrition.kcal_target:
        parts = [f"{ctx.nutrition.kcal_target:.0f} kcal"]
        if ctx.nutrition.protein_target_g:
            parts.append(f"P:{ctx.nutrition.protein_target_g:.0f}g")
        if ctx.nutrition.carb_target_g:
            parts.append(f"C:{ctx.nutrition.carb_target_g:.0f}g")
        if ctx.nutrition.fat_target_g:
            parts.append(f"F:{ctx.nutrition.fat_target_g:.0f}g")
        lines.append(f"Daily target: {', '.join(parts)}")

    # Today's intake vs goal
    if ctx.nutrition.today_kcal:
        gap = ctx.nutrition.kcal_gap_today
        if gap is not None:
            if gap > 0:
                gap_str = f"(still need {gap:.0f} kcal)"
            elif gap < 0:
                gap_str = f"(over by {-gap:.0f} kcal)"
            else:
                gap_str = "(goal reached)"
        else:
            gap_str = ""
        lines.append(f"Today: {ctx.nutrition.today_kcal:.0f} kcal {gap_str}")

        if ctx.nutrition.today_meals:
            meal_items = []
            for m in ctx.nutrition.today_meals[:3]:
                items = m.get("items", []) if isinstance(m, dict) else []
                meal_items.append(f"{m.get('meal_type', '?')}: {', '.join(items[:3])}")
            if meal_items:
                lines.append(f"  Meals: {'; '.join(meal_items)}")

    # 7-day adherence
    if ctx.nutrition.avg_kcal_7d:
        adherence = ctx.nutrition.kcal_adherence_7d
        lines.append(
            f"7-day avg: {ctx.nutrition.avg_kcal_7d:.0f} kcal/day — {_adherence_label(adherence)}"
        )

    # Hard restrictions
    hard_avoid = []
    if ctx.allergies:
        hard_avoid.extend(a.get("allergen", "") for a in ctx.allergies)
    if ctx.dietary_restrictions:
        hard_avoid.extend(ctx.dietary_restrictions)
    if hard_avoid:
        lines.append(f"NEVER suggest: {', '.join(hard_avoid)}")

    # Health-driven restrictions
    if ctx.health_risk_flags:
        descriptions = {
            "limit_simple_carbs":     "Limit simple carbs",
            "limit_sugar":           "Limit sugar",
            "limit_sodium_2g_day":  "Salt <2g/day",
            "limit_purine":          "Limit purine (seafood, organ meats)",
            "limit_potassium":      "Limit potassium",
            "limit_phosphorus":      "Limit phosphorus",
            "avoid_alcohol":         "No alcohol",
            "limit_saturated_fat":  "Limit saturated fat",
            "increase_protein":      "Increase protein",
            "increase_calcium":      "Increase calcium",
            "increase_iron":         "Increase iron",
        }
        readable = [descriptions.get(f, f) for f in ctx.health_risk_flags[:6]]
        lines.append(f"Medical rules: {', '.join(readable)}")

    # Foods to avoid (confirmed bad reactions)
    if ctx.foods_to_avoid:
        avoid_strs = [
            f"{f.get('food', '')} ({f.get('reason', '')})"
            for f in ctx.foods_to_avoid[:4]
        ]
        lines.append(f"Bad reactions: {', '.join(avoid_strs)}")

    # Taste preferences
    if ctx.taste_preferences:
        taste_map = {"spicy": "cay", "sweet": "ngọt", "salty": "mặn", "sour": "chua", "bitter": "đắng"}
        likes  = [taste_map.get(t, t) for t, v in ctx.taste_preferences.items() if isinstance(v, (int, float)) and v >= 4]
        dislikes = [taste_map.get(t, t) for t, v in ctx.taste_preferences.items() if isinstance(v, (int, float)) and v <= 2]
        if likes:     lines.append(f"Likes: {', '.join(likes)}")
        if dislikes:  lines.append(f"Dislikes taste: {', '.join(dislikes)}")

    if ctx.favorite_foods:
        lines.append(f"Favorite foods: {_str_list(ctx.favorite_foods, 5)}")
    if ctx.disliked_foods:
        lines.append(f"Disliked foods: {_str_list(ctx.disliked_foods, 5)}")
    if ctx.cuisine_preferences:
        lines.append(f"Cuisines: {_str_list(ctx.cuisine_preferences, 3)}")

    # Meal pattern
    if ctx.meal_frequency:
        freq_map = {
            "two_meals":         "2 meals/day",
            "three_meals":       "3 meals/day",
            "four_meals":        "4 meals/day",
            "five_plus":         "5+ small meals",
            "intermittent_fasting": "Intermittent fasting",
        }
        lines.append(f"Meal frequency: {freq_map.get(ctx.meal_frequency, ctx.meal_frequency)}")
    if ctx.cooking_preference:
        cook_map = {
            "home_cooked":  "home-cooked",
            "eat_out":      "eats out",
            "mixed":        "mixed",
            "meal_prep":    "meal prep",
        }
        lines.append(f"Cooking: {cook_map.get(ctx.cooking_preference, '')}")
    if ctx.work_schedule:
        lines.append(f"Work schedule: {ctx.work_schedule}")
    if ctx.nutrition.hydration_target_ml:
        lines.append(f"Hydration target: {ctx.nutrition.hydration_target_ml}ml/day")

    # Key facts
    food_facts = [
        f for f in ctx.key_facts
        if any(kw in f.lower() for kw in ["ăn", "uống", "thích", "không", "kiêng", "bữa"])
    ]
    if food_facts:
        lines.append(f"Known facts: {'; '.join(food_facts[:3])}")

    return "\n".join(lines) if lines else "No detailed nutrition data available."


# ─── FITNESS COACH ───────────────────────────────────────────────────────────


def build_fitness_coach_context(ctx: FullUserContext) -> str:
    """
    Fitness coach needs: fitness level, restrictions, schedule, goals,
    body state, recent workouts.
    """
    lines = []

    # Goal
    if ctx.usage_goal:
        lines.append(f"Goal: {_goal_label(ctx.usage_goal)}")

    # Physical stats
    if ctx.weight_kg:
        stats = f"{ctx.weight_kg}kg"
        if ctx.height_cm:  stats += f", {ctx.height_cm}cm"
        if ctx.age:        stats += f", {ctx.age} years"
        lines.append(f"Physical: {stats}")

    # Fitness level
    level_map = {
        "beginner":     "Beginner — light exercises, basic technique",
        "intermediate": "Intermediate — increase intensity gradually",
        "advanced":     "Advanced — can handle heavy training",
        "athlete":      "Athlete",
    }
    lines.append(f"Fitness level: {level_map.get(ctx.fitness.fitness_level, ctx.fitness.fitness_level)}")

    # Recent workout history
    if ctx.fitness.last_workout_date:
        lines.append(f"Last workout: {ctx.fitness.last_workout_date}")
    if ctx.fitness.workout_frequency_7d:
        lines.append(f"Frequency (7 days): {ctx.fitness.workout_frequency_7d} sessions")

    if ctx.fitness.preferred_types:
        lines.append(f"Preferred: {', '.join(ctx.fitness.preferred_types)}")

    # Physical restrictions (CRITICAL for safety — also drives Safety Matrix evaluation)
    injury_areas = ctx.body.injury_areas
    sore_areas = ctx.body.sore_areas

    if injury_areas:
        lines.append(f"INJURED (do not train these areas): {', '.join(injury_areas)}")
        # Inject safety override hints for known injured regions
        injury_rules = _build_injury_safety_rules(injury_areas)
        if injury_rules:
            lines.append(f"SAFETY RULES: {injury_rules}")

    if sore_areas:
        lines.append(f"SORE (work around these areas): {', '.join(sore_areas)}")
        sore_rules = _build_sore_safety_rules(sore_areas)
        if sore_rules:
            lines.append(f"SAFETY RULES: {sore_rules}")

    if ctx.fitness.current_restrictions:
        for r in ctx.fitness.current_restrictions[:3]:
            lines.append(f"Restriction: {r.get('area', '')} — {r.get('reason', '')}")

    # Active symptoms affecting fitness
    if ctx.body.active_symptoms:
        for s in ctx.body.active_symptoms[:2]:
            lines.append(f"Symptom: {s.get('description', '')} — avoid high intensity")

    # Energy today
    if ctx.body.energy_level:
        advice = {
            "low":      "Low energy — prioritize light exercise or rest",
            "normal":   "Normal energy",
            "high":     "High energy — can handle intense training",
        }
        lines.append(f"Energy: {advice.get(ctx.body.energy_level, ctx.body.energy_level)}")

    # Sleep
    if ctx.body.sleep_last_night_hours:
        h = ctx.body.sleep_last_night_hours
        if h < 6:
            note = "⚠️ Low sleep — do light exercise, prioritize recovery"
        elif h >= 7:
            note = "Good sleep — can train normally"
        else:
            note = "Acceptable sleep"
        lines.append(f"Last night: {h}h — {note}")

    # Schedule
    schedule_parts = []
    if ctx.work_schedule:   schedule_parts.append(ctx.work_schedule)
    if ctx.sleep_schedule:  schedule_parts.append(f"sleep {ctx.sleep_schedule}")
    if schedule_parts:
        lines.append(f"Schedule: {', '.join(schedule_parts)}")

    # Health conditions affecting exercise
    exercise_notes = {
        "hypertension":       "High BP — avoid isometric, monitor HR",
        "type2_diabetes":     "Diabetes — train 1-2h after eating, carry sugar",
        "heart_disease":      "Heart disease — do not exceed 70% max HR",
        "osteoporosis":       "Osteoporosis — avoid high-impact exercises",
        "knee_pain":          "Knee pain — avoid deep squats, long runs",
        "lower_back_pain":    "Lower back pain — avoid Deadlift, Barbell Squat",
        "shoulder_injury":    "Shoulder injury — avoid Bench Press, Overhead Press",
    }
    for cond in ctx.health_conditions:
        cid = cond.get("condition", "")
        if cid in exercise_notes:
            lines.append(f"Health note: {exercise_notes[cid]}")

    # Key fitness facts
    fitness_facts = [
        f for f in ctx.key_facts
        if any(kw in f.lower() for kw in ["tập", "gym", "chạy", "bơi", "yoga", "thể thao", "vận động"])
    ]
    if fitness_facts:
        lines.append(f"Known facts: {'; '.join(fitness_facts[:2])}")

    return "\n".join(lines) if lines else "No detailed fitness data available."


def _build_injury_safety_rules(injury_areas: list[str]) -> str:
    """Return human-readable safety rule summary for injured areas."""
    rules_by_area = {
        "lower_back": "BLOCK: Barbell Squat, Deadlift, Overhead Press → REPLACE: Leg Press, Leg Extension",
        "back":       "BLOCK: Barbell Squat, Deadlift, Overhead Press → REPLACE: Leg Press, Leg Extension",
        "spine":      "BLOCK: Deadlift, Jump Squat, Burpee → REPLACE: Leg Press, Swimming",
        "shoulder":    "BLOCK: Bench Press, Plank, Push-up → REPLACE: Incline Press, Lateral Raise",
        "shoulders":   "BLOCK: Bench Press, Plank, Push-up → REPLACE: Incline Press, Lateral Raise",
        "knee":       "BLOCK: Jump Squat, Lunge, Running → REPLACE: Leg Press, Cycling, Swimming",
        "knees":      "BLOCK: Jump Squat, Lunge, Running → REPLACE: Leg Press, Cycling, Swimming",
        "wrist":      "BLOCK: Push-up, Plank, Bench Press → REPLACE: Dumbbell Press, Wall Push-up",
        "wrists":     "BLOCK: Push-up, Plank, Bench Press → REPLACE: Dumbbell Press, Wall Push-up",
        "hip":        "BLOCK: Deadlift, Lunge → REPLACE: Hip Thrust bodyweight, Glute Bridge",
        "hips":       "BLOCK: Deadlift, Lunge → REPLACE: Hip Thrust bodyweight, Glute Bridge",
    }
    parts = []
    for area in injury_areas:
        if area in rules_by_area:
            parts.append(rules_by_area[area])
    return " | ".join(parts)


def _build_sore_safety_rules(sore_areas: list[str]) -> str:
    """Return lighter safety rules for sore (non-injured) areas."""
    return "Do NOT load the sore area. Suggest antagonist muscles and light blood-flow movement only."


# ─── ORCHESTRATOR SUMMARY ────────────────────────────────────────────────────


def build_orchestrator_summary(ctx: FullUserContext) -> str:
    """
    Compact summary for the final synthesis AI call.
    Only includes immediately relevant facts — no noise.
    """
    lines = []

    # Identity
    identity = []
    if ctx.name:   identity.append(ctx.name)
    if ctx.age:    identity.append(f"{ctx.age} years old")
    if ctx.gender: identity.append(str(ctx.gender))
    if identity:
        lines.append(f"User: {', '.join(identity)}")

    # Goal
    if ctx.usage_goal:
        lines.append(f"Goal: {_goal_label(ctx.usage_goal)}")

    # Active health issues
    active_conditions = [
        c for c in ctx.health_conditions
        if c.get("severity") != "resolved"
    ]
    if active_conditions:
        lines.append(f"Conditions: {', '.join(c['condition'] for c in active_conditions[:3])}")

    # Body state
    if ctx.body.sore_areas:
        lines.append(f"Sore: {', '.join(ctx.body.sore_areas)}")
    if ctx.body.active_symptoms:
        lines.append(f"Symptom: {ctx.body.active_symptoms[0].get('description', '')}")

    # Nutrition gap
    if ctx.nutrition.kcal_gap_today is not None:
        gap = ctx.nutrition.kcal_gap_today
        if abs(gap) > 200:
            if gap > 0:
                lines.append(f"Today: still need {gap:.0f} kcal")
            else:
                lines.append(f"Today: over by {-gap:.0f} kcal")

    # Hard restrictions
    hard_avoid = [a.get("allergen", "") for a in ctx.allergies if a.get("allergen")]
    if hard_avoid:
        lines.append(f"Allergies: {', '.join(hard_avoid)}")

    if ctx.profile_completeness < 0.5:
        lines.append("⚠️ Profile incomplete — base recommendations on available data")

    return "\n".join(lines) if lines else ""
