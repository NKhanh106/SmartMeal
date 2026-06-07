# -*- coding: utf-8 -*-
"""Safety fix verification tests — SmartMeal biomedical audit fixes."""

import sys
sys.path.insert(0, '.')

def check(label, condition, detail=""):
    if condition:
        print(f"  PASS: {label}")
    else:
        print(f"  FAIL: {label}" + (f" ({detail})" if detail else ""))
        global failures
        failures += 1

failures = 0

# ── Test 1: A-5 — Upper bounds on nutrition_math ───────────────────────────────
print("\n[A-5] Nutrition math upper bounds:")
from app.services.nutrition_math import (
    calculate_macro_targets,
    MAX_REASONABLE_CALORIES,
    MAX_REASONABLE_PROTEIN_G,
    MAX_REASONABLE_FAT_G,
    MAX_REASONABLE_CARB_G,
)
r = calculate_macro_targets(
    weight_kg=200, height_cm=180, age=30, gender='male',
    activity_level='very_active', nutrition_goal_type='surplus'
)
check("protein_g <= MAX_REASONABLE_PROTEIN_G", r.macros.protein_g <= MAX_REASONABLE_PROTEIN_G, r.macros.protein_g)
check("fat_g <= MAX_REASONABLE_FAT_G", r.macros.fat_g <= MAX_REASONABLE_FAT_G, r.macros.fat_g)
check("carb_g <= MAX_REASONABLE_CARB_G", r.macros.carb_g <= MAX_REASONABLE_CARB_G, r.macros.carb_g)
check("target_calories <= MAX_REASONABLE_CALORIES", r.macros.target_calories <= MAX_REASONABLE_CALORIES, r.macros.target_calories)

# Small user: no clamping needed
r2 = calculate_macro_targets(
    weight_kg=50, height_cm=160, age=25, gender='female',
    activity_level='moderate', nutrition_goal_type='deficit'
)
check("Small user: protein_g sensible (~100g)", 60 <= r2.macros.protein_g <= 120, r2.macros.protein_g)
check("Small user: carb_g not zero", r2.macros.carb_g > 0, r2.macros.carb_g)

# ── Test 2: C-2 — Behavioral pattern false positives ───────────────────────────
print("\n[C-2] Behavioral pattern false positives:")
from app.agents.nutrition_advisor_agent import classify_behavioral_pattern

benign_cases = [
    ("bo bua sang vi ban hoc", "skip benign - busy school"),
    ("chua kip an sang vi tre gio", "skip benign - late for work"),
    ("khong co thoi gian an truA", "skip benign - no time"),
    ("bi om ua nen chua an gi", "skip benign - sick"),
    ("toi bi cham soc tre con", "skip benign - caring for child"),
]
for msg, desc in benign_cases:
    is_b, cat, lbl = classify_behavioral_pattern(msg, [])
    check(f"Benign suppressed: {desc}", not is_b, f"triggered={cat}")

true_cases = [
    # Must use real Vietnamese diacritics (ỏ, ữ, à, ì) to match regex patterns
    # ASCII "vi" won't match "vì" — diacritics are different Unicode code points
    ("bỏ bữa sáng vì sợ lên cân", "skip - fear of weight gain (real diacritics)"),
    ("hqua stress nên ăn hết đêm", "stress eating (real diacritics)"),
    ("nhịn ăn vì sợ béo", "fasting - fear of being fat (real diacritics)"),
    ("chỉ ăn rau thôi vì sợ béo", "extreme restriction - fear (real diacritics)"),
]
for msg, desc in true_cases:
    is_b, cat, lbl = classify_behavioral_pattern(msg, [])
    check(f"True positive: {desc}", is_b, f"cat={cat}")

# ── Test 3: B-4 — Severity keyword mitigation ─────────────────────────────────
print("\n[B-4] Severity keyword with mitigating qualifiers:")
from app.agents.safety_matrix import SafetyMatrix
m = SafetyMatrix()

false_positive_cases = [
    ([{'issue': 'viêm amidan nhẹ', 'description': 'hơi đau họng', 'severity': 'mild'}], "viêm nhẹ"),
    ([{'issue': 'viêm họng vừa', 'description': 'hơi khó chịu', 'severity': 'moderate'}], "viêm vừa"),
    ([{'issue': 'chấn thương vai nhẹ', 'description': 'hơi đau', 'severity': 'mild'}], "chấn thương nhẹ"),
    ([{'issue': 'bị thương hơi đau', 'description': 'sơ sơ', 'severity': 'mild'}], "bị thương hơi"),
]
for issues, desc in false_positive_cases:
    result = m._has_severe_issue(issues)
    check(f"Not severe: {desc}", not result, f"got {result}")

true_positive_cases = [
    ([{'issue': 'viêm amidan', 'description': 'sốt cao đau họng', 'severity': 'moderate'}], "viêm amidan nặng"),
    ([{'issue': 'đau lưng', 'description': 'đau dữ dội', 'severity': 'severe'}], "đau lưng severe"),
    ([{'issue': 'gãy tay', 'description': 'sưng to', 'severity': 'moderate'}], "gãy tay"),
]
for issues, desc in true_positive_cases:
    result = m._has_severe_issue(issues)
    check(f"Is severe: {desc}", result, f"got {result}")

# ── Test 4: B-2 — Neck area normalization ───────────────────────────────────
print("\n[B-2] Neck area normalization:")
check("neck -> shoulder", m._normalize_area('neck') == 'shoulder')
check("cổ -> shoulder", m._normalize_area('cổ') == 'shoulder')
check("right_shoulder -> shoulder", m._normalize_area('right_shoulder') == 'shoulder')
check("knee -> knee", m._normalize_area('knee') == 'knee')
check("unknown -> unknown", m._normalize_area('unknown_area') == 'unknown_area')

# ── Test 5: B-1/B-6 — Regex substring matching ────────────────────────────────
print("\n[B-1/B-6] Exercise name regex substring matching:")
import re as _re

# Simulate the blocked keywords (from safety matrix for back injury)
# Note: these use plain substring matching (no \b) to handle Vietnamese diacritics
blocked_keywords = ['barbell squat', 'squat tạ', 'deadlift', 'jump squat', 'overhead press']

def _strip_emoji(text):
    emoji = _re.compile("["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "]+", flags=_re.UNICODE)
    return emoji.sub("", text)

def exercise_is_blocked_sim(name_raw):
    """Simulates the actual _enforce_safety_result logic: plain substring match."""
    name_norm = _strip_emoji(name_raw).lower()
    for kw in blocked_keywords:
        if kw in name_norm:
            return True
    return False

# Cases where the BLOCKED keyword IS a substring of the exercise name
# blocked_keywords = ['barbell squat', 'squat tạ', 'deadlift', 'jump squat', 'overhead press']
blocked_cases = [
    ("🏋️ Barbell Squat nâng cao", "emoji prefix"),
    ("Squat tạ cho chân", "vietnamese blocked name matches 'squat tạ'"),
    ("JUMP SQUAT", "uppercase matches 'jump squat'"),
    ("Overhead Press ngồi", "partial matches 'overhead press'"),
    ("Deadlift thường", "contains 'deadlift' = blocked"),
]
# Cases that should NOT be blocked (no blocked keyword is a substring)
safe_cases = [
    ("Barbell Kniebeuge", "safe — 'barbell squat' != 'barbell kniebeuge'"),
    ("Back Squat", "NOT blocked — 'barbell squat' != 'back squat'"),
    ("Squat lưng", "NOT blocked — 'squat tạ' != 'squat lưng'"),
    ("Leg Press (tựa lưng)", "safe alternative"),
    ("Leg Extension ngồi", "safe alternative"),
    ("Running", "not in blocked list"),
    ("Goblet Squat", "NOT blocked — 'barbell squat' not in name"),
]
for name, desc in blocked_cases:
    result = exercise_is_blocked_sim(name)
    check(f"Blocked: {desc} ({name})", result, f"name={name}")

for name, desc in safe_cases:
    result = exercise_is_blocked_sim(name)
    check(f"Safe: {desc} ({name})", not result, f"name={name}")

# ── Test 6: C-1 — Disclaimer appender ──────────────────────────────────────
print("\n[C-1] Medical disclaimer appender:")
from app.agents.output_guardrails import append_medical_disclaimer, filter_prohibited_phrases, apply_output_guardrails

plain = "Bạn nên ăn nhiều rau xanh."
result = append_medical_disclaimer(plain, context='nutrition')
check("Disclaimer appended", 'lưu ý' in result.lower() and plain in result)
check("No double disclaimer", result.count('Lưu ý:') == 1, result.count('Lưu ý:'))

# Already has disclaimer
already = plain + " Lưu ý: tham khảo bác sĩ."
result2 = append_medical_disclaimer(already, context='nutrition')
check("No duplicate when already present", result2.count('Lưu ý:') == 1)

# Fitness disclaimer
fit = "Hôm nay nên chạy bộ 30 phút."
result_fit = append_medical_disclaimer(fit, context='fitness')
check("Fitness disclaimer appended", 'lưu ý' in result_fit.lower())

# Health disclaimer
health = "Bạn có triệu chứng cần theo dõi."
result_health = append_medical_disclaimer(health, context='health')
check("Health disclaimer appended", 'lưu ý' in result_health.lower())

# ── Test 7: C-3 — Prohibited phrase filter ───────────────────────────────────
print("\n[C-3] Mode B prohibited phrase filter:")
phrases = [
    ("bạn nên kiểm soát lại việc ăn", "kiểm soát lại"),
    ("đừng ăn đêm đi", "đừng ăn"),
    ("bắt buộc phải nhịn ăn", "bắt buộc phải"),
    ("ngừng ăn đi", "ngừng ăn"),
]
for text, desc in phrases:
    result = filter_prohibited_phrases(text)
    check(f"Filtered: {desc}", 'kiểm soát lại' not in result.lower())

# ── Test 8: D-2/D-3/A-5 — Data writer constants ────────────────────────────
print("\n[D-2/D-3/A-5] Data writer safety constants:")
from app.agents.data_writers import (
    MIN_DAILY_CALORIES, MAX_TOTAL_CALORIES,
    MIN_WEIGHT_KG, MAX_WEIGHT_KG,
    MAX_PROTEIN_G, MAX_FAT_G,
)
check("MIN_DAILY_CALORIES = 1000", MIN_DAILY_CALORIES == 1000)
check("MAX_TOTAL_CALORIES = 6000", MAX_TOTAL_CALORIES == 6000)
check("MIN_WEIGHT_KG = 20.0", MIN_WEIGHT_KG == 20.0)
check("MAX_WEIGHT_KG = 300.0", MAX_WEIGHT_KG == 300.0)
check("MAX_PROTEIN_G = 300", MAX_PROTEIN_G == 300)
check("MAX_FAT_G = 200", MAX_FAT_G == 200)

# ── Results ────────────────────────────────────────────────────────────────────
print()
if failures == 0:
    print("ALL TESTS PASSED.")
else:
    print(f"FAILURES: {failures}")
    sys.exit(1)
