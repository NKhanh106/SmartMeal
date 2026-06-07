# SmartMeal Biomedical Logic Safety Audit Report

**Auditor:** Claude (Code Agent)
**Date:** 2026-06-06
**Scope:** Nutrition calculations, safety matrix bypasses, medical disclaimer enforcement, data writer integrity
**Files Audited:** `nutrition_math.py`, `health_monitor_agent.py`, `safety_matrix.py`, `fitness_coach_agent.py`, `nutrition_advisor_agent.py`, `extractor_agent.py`, `data_writers.py`, `context_loader.py`, `nutrition_goal.py`, `web_researcher_agent.py`, `ai_chatbot.py`, `meal_logs.py`

---

## SECTION A: Nutrition Calculation Edge Cases

---

### A-1: BMI-Based Safety Override for Underweight Users (Deficit Prevention)

**Finding:** ✅ **NO ISSUE — SATISFACTORILY PROTECTED**

The `MINIMUM_CALORIE_FLOOR_FACTOR = 1.0` in `nutrition_math.py` line 75 ensures that for a deficit goal, `target_calories = max(tdee - 500, bmr * 1.0)`. An underweight user (BMI < 18.5) with BMR = 1350 kcal who wants a deficit would get target = max(1350 - 500 = 850, 1350) = **1350 kcal** — exactly their BMR, not below.

This floor prevents recommending a caloric deficit to underweight users. However, the system still does NOT explicitly flag underweight users (BMI < 18.5) as a special population. It silently floors to BMR.

**Severity:** Low
**Intent:** Non-adversarial. Accidental misuse possible if a very underweight user sets a deficit goal. The floor prevents harm but does not provide a warning.
**Verdict:** Acceptable with caveat. Consider adding a clinical warning when BMI < 18.5.

---

### A-2: Protein Overload for Small Body Weight

**Finding:** ⚠️ **MEDIUM — Over-recommendation possible for small-framed users**

`calculate_macros()` at line 192 computes `protein_g = weight_kg * 2.0`.

| Weight | Protein Recommended | 2.2g/kg upper bound | Excess |
|---------|-------------------|---------------------|--------|
| 40 kg   | 80g               | 88g                | Safe  |
| 45 kg   | 90g               | 99g                | Safe  |
| 50 kg   | 100g              | 110g               | Safe  |
| 40 kg, athlete | 80g       | 88g                | Safe  |

At 2.0 g/kg, this is actually **below** the 2.2 g/kg athletic ceiling. The concern is not protein overload but protein at the upper end of normal range for a small person. For a 40 kg user, 80g/day ≈ 320 kcal from protein. If target calories are 1350 (deficit), protein alone is 24% of total calories. This is nutritionally acceptable but may feel like a lot of food for a small-framed person.

The real concern: if a 40 kg user with a **maintenance** goal of ~2100 kcal enters `deficit` and gets floored to 1350 kcal, their protein (80g = 320 kcal = **24%** of actual intake) is very high relative to the real deficit. The macro ratio becomes skewed.

**Triggering input:** `weight_kg=40, height_cm=155, age=25, gender="female", activity="moderate", goal="deficit"`

**Severity:** Medium
**Intent:** Non-adversarial. Affects small-framed users (common in Southeast Asian populations).
**Fix:**

```python
# Before (nutrition_math.py:192):
protein_g = round(weight_kg * PROTEIN_G_PER_KG, 1)

# After — cap protein at 2.2 g/kg for athletes, 1.8 g/kg for general population
athlete_cap = 2.2
general_cap = 2.0
protein_cap = athlete_cap if activity_level in ("very_active", "active") else general_cap
protein_g = round(min(weight_kg * PROTEIN_G_PER_KG, weight_kg * protein_cap), 1)
```

---

### A-3: Activity Level Fallback to "moderate" (1.55x)

**Finding:** ✅ **LOW RISK — Graceful degradation**

`calculate_tdee()` at line 152-155 uses `ActivityLevel(activity_level.lower())`. If the enum doesn't contain the string value, it raises `ValueError`, which is caught by the outer try/except in `calculate_macro_targets()`. The `ActivityLevel` enum is defined in the same file with 5 values. If an unrecognized value like `"athlete"` is passed, `ValueError` is raised → function returns `None` and Mode A is skipped in `nutrition_advisor_agent.py:230-236`.

The fallback to `1.550×` only occurs if `ActivityLevel(value)` does NOT raise `ValueError` but the multiplier is looked up with a default. However, since `ActivityLevel(value)` raises on bad input, the fallback is not reachable through the normal path. The only way to hit the fallback is to pass a valid enum member name that happens to not be in `ACTIVITY_MULTIPLIERS` — which is impossible since all 5 enum members are mapped.

**Verdict:** No active issue. The invalid input silently causes Mode A to be skipped (the nutrition advisor falls back to LLM-only macro estimation).

---

### A-4: Gender String Edge Cases

**Finding:** ✅ **NO ISSUE — Both code paths validated**

Two gender checks exist:
1. `calculate_bmr()` line 143: `s = MALE_S if gender.lower() in ("male", "nam", "m") else FEMALE_S` — hardcoded fallback to female.
2. `calculate_macro_targets()` line 239-243: explicit validation against `("male", "female", "nam", "nu")`.

The validation in `calculate_macro_targets()` (line 239) runs BEFORE `calculate_bmr()` (line 246). So if `"MALE"` is passed, `gender_clean = "male"` passes validation. Then `calculate_bmr("male")` matches `"male"` in the tuple. If `"Nam"` is passed, it matches `"nam"`.

Unicode variants like `"MÂLE"` (French) would fail validation and raise `ValueError`. Vietnamese `"nam"` and `"nữ"` are accepted.

**Verdict:** No active issue.

---

### A-5: TDEE Overflow for Very Large Users

**Finding:** ⚠️ **MEDIUM — No upper bound on computed values**

For a 200 kg, 180 cm, 30-year-old male with `very_active`:
- BMR = 10×200 + 6.25×180 - 5×30 + 5 = 2000 + 1125 - 150 + 5 = **2980 kcal**
- TDEE = 2980 × 1.9 = **5662 kcal**
- Protein = 400g (800 kcal)
- Fat = 25% × 5662 / 9 = **157g fat**
- Carb = (5662 - 800 - 1414) / 4 = **862g carbs**

157g fat/day is not dangerous. The issue is that these values are mathematically produced with no sanity ceiling. A 500 kg user would produce BMR ≈ 7000, TDEE ≈ 13,300, and protein = 1000g. The database stores `Numeric(8,2)` so values up to 99,999.99 are fine, but the absurdity of 1000g protein/day is not prevented.

**Severity:** Medium
**Intent:** Non-adversarial. Edge case affecting very heavy users.
**Fix:**

```python
# Add to calculate_macro_targets() after line 237:
MAX_REASONABLE_CALORIES = 6000  # kcal
MAX_REASONABLE_PROTEIN_G = 300  # g
MAX_REASONABLE_FAT_G = 200       # g
MAX_REASONABLE_CARB_G = 900      # g

# After macro calculation:
protein_g = min(protein_g, MAX_REASONABLE_PROTEIN_G)
fat_g = min(fat_g, MAX_REASONABLE_FAT_G)
carb_g = min(carb_g, MAX_REASONABLE_CARB_G)
target_calories = min(target_calories, MAX_REASONABLE_CALORIES)
```

---

### A-6: Zero/Missing Weight Propagation

**Finding:** ✅ **PROTECTED — Explicit guard at line 233**

```python
if weight_kg <= 0 or height_cm <= 0 or age <= 0:
    raise ValueError(...)
```

`weight_kg=0` raises `ValueError` before any calculation. `weight_kg=None` would fail `weight_kg <= 0` with a `TypeError` (caught by the outer `except Exception`), which also prevents calculation.

**Verdict:** No active issue.

---

### A-7: Zero Carb Clamp Validity

**Finding:** ⚠️ **LOW — Mathematically possible, nutritionally questionable**

`calculate_macros()` line 199: `carb_g = round(max(calories_from_carb, 0) / KCAL_PER_G_CARB, 1)`. Zero carbs is possible when `protein_g × 4 + fat_g × 9 ≥ target_calories`.

Example: 40 kg user, deficit goal (BMR-floored to ~1350 kcal):
- Protein = 80g × 4 = 320 kcal
- Fat = 25% × 1350 / 9 = 37.5g → 337.5 kcal
- Remaining = 1350 - 320 - 337.5 = **692.5 kcal → 173g carbs**

Not zero. But with an aggressive deficit (e.g., if floor were removed), carbs could hit zero. With the 1.0 floor, zero carbs cannot occur for most users.

However: the `max(calories_from_carb, 0)` clamp silently reduces total calories below `target_calories`. If carbs become 0, the actual intake is protein_cal + fat_cal, which is less than the intended target. This is a silent calorie target erosion bug.

**Severity:** Low (floor prevents it in practice)
**Intent:** Non-adversarial.

---

## SECTION B: Safety Matrix Bypass Vectors

---

### B-1: Exercise Name Evasion (Synonyms, Vietnamese, Emoji, Foreign)

**Finding:** ⚠️ **MEDIUM — Partial coverage, exploitable by sophisticated users**

The `_EXERCISE_NAME_TO_REGION` mapping is defined in `_regions_from_issues()` (lines 334-361) and uses keyword matching on `issue + description + recommendation` text. The actual block lists use **exact string matching** on `ExerciseBlock.blocked_name` and `blocked_name_vi`.

Analysis by region:

| Exercise Name | Blocked | Bypass Variant | Blocked? |
|--------------|---------|----------------|----------|
| Barbell Squat | ✅ | "Squat lưng" | ❌ (not in `_BACK_MATRIX`) |
| Barbell Squat | ✅ | "Back Squat" | ❌ (English not in `blocked_name`) |
| Barbell Squat | ✅ | "Barbell Kniebeuge" (German) | ❌ |
| Barbell Squat | ✅ | "🏋️ Squat" | ❌ |
| Deadlift | ✅ | "Gánh tạ" | ❌ |
| Burpee | ✅ | "Burpee biến thể" | ❌ |
| Push-up | ✅ | "Push-up nâng cao" | ❌ |
| Push-up | ✅ | "Plank chống đẩy" | ❌ |

The post-LLM filter in `fitness_coach_agent.py:409-420` checks exact string matching:

```python
safe_names_lower = {e.lower() for e in safety_result.all_blocked}
safe_names_lower.update(e.lower() for e in safety_result.all_blocked_vi)
filtered = [
    ex for ex in exercises
    if ex.get("name", "").lower() not in safe_names_lower
]
```

"Barbell Squat" (English) would be blocked. "Squat tạ" (Vietnamese) would NOT be blocked because `_BACK_MATRIX` only contains `"Squat tạ"` as `blocked_name_vi` (used only for display, not filtering). The filter only checks `blocked_name` (English) and `blocked_name_vi` (Vietnamese) against exercise `name` field.

**Severity:** Medium
**Intent:** Requires adversarial intent or linguistic knowledge.
**Fix:** Add Vietnamese exercise name variants to both the block lists AND the post-filter matching, or use fuzzy/partial matching:

```python
# In fitness_coach_agent._enforce_safety_result(), line 415:
def _name_matches_block(ex_name: str, blocked_names: list[str], blocked_vi: list[str]) -> bool:
    ex_lower = ex_name.lower()
    # Exact match
    if ex_lower in {n.lower() for n in blocked_names + blocked_vi}:
        return True
    # Partial match: any blocked name is a substring of exercise name
    for blocked in blocked_names + blocked_vi:
        if blocked.lower() in ex_lower or ex_lower in blocked.lower():
            return True
    return False

filtered = [
    ex for ex in exercises
    if not _name_matches_block(ex.get("name", ""), safety_result.all_blocked, safety_result.all_blocked_vi)
]
```

---

### B-2: Region Name Injection via body_snapshot

**Finding:** ⚠️ **MEDIUM — `body_snapshot` populated by LLM, not validated**

`sore_areas` and `injury_areas` in `body_snapshot` come from `_build_memory_updates()` in `health_monitor_agent.py:400-431`. This method reads `active_issues` from the AI's LLM output and maps them via `AREA_KEYWORDS`. The mapping is one-directional (Vietnamese keywords → English keys).

```python
AREA_KEYWORDS = {
    "tay phải": "right_arm",
    "lưng": "lower_back",
    ...
}
```

If `AREA_KEYWORDS` maps `"cổ"` (neck) → `"neck"`, then `safety_matrix._normalize_area("neck")` → `"shoulder"`? Wait, let me re-check. In `_normalize_area()`:
```python
mapping = {
    "lower_back":  "back",
    "upper_back":  "back",
    ...
    "shoulder":    "shoulder",
    "cổ":         ???  # NOT in mapping
}
```

`normalize_area` uses `area.lower()` as the key, so if `area = "NECK"`, it returns `"neck"` which is NOT in the mapping, so it returns `"neck"` as-is. Then `_REGION_MATRICES.get("neck")` → `None`. So a `neck` injury would NOT trigger any exercise blocks!

Similarly, `"ankle"` → `"ankle"` → no matrix found.

The AREA_KEYWORDS in HealthMonitor map `"cổ"` → `"neck"`, which means a Vietnamese user saying "đau cổ" would create a `neck` injury area that the safety matrix does NOT recognize.

**Severity:** Medium
**Intent:** Could occur accidentally (non-adversarial) if user mentions neck pain.
**Fix:**

```python
# In safety_matrix._normalize_area(), add:
mapping = {
    ...
    "neck":    "shoulder",  # Neck pain → avoid overhead press and similar
    "ankle":   "knee",      # Ankle → avoid running, jumping
    "foot":    "knee",
    "toes":    "knee",
}
```

---

### B-3: Severity Word Evasion in Vietnamese

**Finding:** ✅ **NO ACTIVE ISSUE — Severity is AI-inferred, bypass is not actionable**

Severity words in `extractor_agent.py` line 165 are Vietnamese and used for `confidence` mapping, not for safety decisions. The severity for safety decisions (forced rest, workout type) comes from `safety_matrix._has_severe_issue()` at line 387-397:

```python
def _has_severe_issue(self, issues: list[dict[str, Any]]) -> bool:
    severe_keywords = ["chấn thương", "injury", "gãy", "trật", "thoát vị", "viêm"]
    for issue in issues:
        severity = issue.get("severity", "").lower()
        if severity == "severe":
            return True
        combined = (str(issue.get("issue", "")) + " " + str(issue.get("description", ""))).lower()
        if any(kw in combined for kw in severe_keywords):
            return True
    return False
```

The severity keyword check is in Vietnamese (no English "critical" bypass possible). The `severity == "severe"` string check is case-sensitive but the `.lower()` is applied first.

**Verdict:** No active issue.

---

### B-4: Forced "rest" Override Misuse (False-Positive Severe Keyword)

**Finding:** ⚠️ **HIGH — False-positive severe keywords can trigger forced rest**

`_has_severe_issue()` at line 389 checks for `"viêm"` (inflammation) as a severe keyword. A user saying "tôi bị viêm amidan đang hồi phục" (I have tonsillitis recovering) would trigger `severity == "severe"` → `forced_workout_type = "rest"`.

More critically: if `active_issues` from HealthMonitor contains an issue with `severity = "severe"` (set by the LLM in `health_monitor_agent.py`), the safety matrix forces rest even if the issue is a mild complaint the LLM over-classified.

The user could intentionally say "tôi bị chấn thương vai nhẹ" (I have mild shoulder injury) — the keyword "chấn thương" triggers `_has_severe_issue() = True` regardless of the actual severity qualifier "nhẹ" (mild).

**Severity:** High (but the harm is in the *opposite* direction — over-restriction, not under-restriction)
**Verdict:** The false positive causes forced rest (safer than the alternative), so this is a "denial of service" to the fitness agent rather than a safety bypass. However, a user who *wants* to exercise could be frustrated by false rest mandates.

---

### B-5: Biomechanical vs. Name-Based Exercise Blocking

**Finding:** ⚠️ **MEDIUM — Name-only matching misses biomechanically related exercises**

The safety matrix blocks exercises by name pattern matching. For a "Back" injury:
- ✅ Blocked: "Barbell Squat" (explicit entry)
- ✅ Blocked: "Deadlift" (explicit entry)
- ❌ NOT blocked: "Cycling" — low back stress during forward lean
- ❌ NOT blocked: "Swimming breaststroke" — hip extension stress
- ❌ NOT blocked: "Elliptical" — slight spinal loading

For a "Knee" injury:
- ✅ Blocked: "Running" (explicit entry)
- ❌ NOT blocked: "Stair climbing" — high patellofemoral load
- ❌ NOT blocked: "Cycling" (if cadence is high)

The system is explicit about the exercises it blocks. This is a known limitation of name-based filtering.

**Severity:** Medium
**Intent:** Non-adversarial. Could affect users who receive seemingly-safe exercise recommendations that actually stress an injured area.

---

### B-6: `applies_to_exercise` Logic Correctness

**Finding:** ✅ **CORRECT — Post-filter hard-blocks by exact name match**

The `_enforce_safety_result()` method at lines 409-420 in `fitness_coach_agent.py` does post-filtering. The logic:

```python
safe_names_lower = {e.lower() for e in safety_result.all_blocked}
safe_names_lower.update(e.lower() for e in safety_result.all_blocked_vi)
filtered = [
    ex for ex in exercises
    if ex.get("name", "").lower() not in safe_names_lower
]
```

This is correct for exact matching. The `blocked_name_vi` strings are included in the filter. However, partial matching (e.g., "Barbell" substring in "Barbell Front Squat") is NOT handled.

**Verdict:** Logic is correct but incomplete. Partial name matches are not blocked.

---

## SECTION C: Medical Disclaimer Bypass

---

### C-1: Disclaimer Only in System Prompt

**Finding:** ⚠️ **MEDIUM — No out-of-band disclaimer enforcement in user-facing output**

The disclaimer in `health_monitor_agent.py:26-29`:
```
"You are NOT a doctor and must always recommend consulting a real doctor
for serious conditions."
```

This is in the `SYSTEM_PROMPT`. If the LLM ignores system prompts, the user-facing response in `text_for_orchestrator` would not contain any disclaimer.

The `user_facing_note` at line 161-164 contains a Vietnamese message encouraging doctor consultation for serious symptoms. But this is only emitted when urgent keywords are detected. For non-urgent health assessments, there is **no automatic disclaimer** in the user-facing text.

**Severity:** Medium
**Intent:** Adversarial (LLM jailbreak) or non-adversarial (model degradation).
**Fix:**

```python
# In the orchestrator or health_monitor_agent, add to user_facing output:
def _append_medical_disclaimer(text: str) -> str:
    disclaimer = (
        "\n\nLưu ý: Mình không phải bác sĩ. "
        "Thông tin trên chỉ mang tính tham khảo. "
        "Nếu bạn có triệu chứng nghiêm trọng, hãy gặp bác sĩ."
    )
    return text + disclaimer

# Apply in health_monitor_agent.py line 239 (text_for_orchestrator building):
if text_for_orch:
    text_for_orch = _append_medical_disclaimer(text_for_orch)
```

---

### C-2: Behavioral Pattern False Positives (Eating Disorders)

**Finding:** ⚠️ **HIGH — "Bỏ bữa" regex fires on legitimate skipping**

`classify_behavioral_pattern()` at `nutrition_advisor_agent.py:106`:

```python
(r"(?:bỏ|bỏ qua|không.*ă[n]?)\s*(?:bữa|bữa sáng|bữa trưa|bữa tối)", "skipping_meals", "Bỏ bữa"),
```

Pattern: `"bỏ" + whitespace + "bữa"` matches "bỏ bữa sáng vì bận học" (I skip breakfast because I'm busy studying). This triggers Mode B eating disorder response for a legitimate, non-disordered statement.

The second pattern:
```python
(r"(?:sáng|nay)\s*(?:không\s*ă[n]?|chưa\s*ă[n]?)(?:\s|$)", "skipping_meals", "Bỏ bữa sáng"),
```
Matches "sáng không ăn" (morning didn't eat) — which is a neutral description, not necessarily disordered.

**False positive rate:** HIGH for Vietnamese speakers who casually mention skipping meals.

**Severity:** High
**Intent:** Non-adversarial. Users without eating disorders will frequently trigger Mode B responses.
**Fix:** Add negation/context check to reduce false positives:

```python
# In classify_behavioral_pattern(), add context filter:
def classify_behavioral_pattern(message: str, conversation_history: list[dict]) -> tuple[bool, str, str]:
    msg_lower = message.strip().lower()
    
    # Skip if negated or explained
    NEGATION_CONTEXT = ["vì", "do", "nên", "thường", "lúc", "lúc nào", "thỉnh thoảng"]
    for pattern, category, label in BEHAVIORAL_EATING_PATTERNS:
        if re.search(pattern, msg_lower):
            # Check for benign context: "vì bận", "do công việc", "thỉnh thoảng"
            if any(ctx in msg_lower for ctx in NEGATION_CONTEXT):
                # Likely a legitimate explanation, not a disorder
                return False, "", ""
            return True, category, label
    return False, "", ""
```

---

### C-3: Mode B Language Enforcement (LLM Ignores System Prompt)

**Finding:** ⚠️ **MEDIUM — System prompt rules not out-of-band enforced**

`nutrition_advisor_agent.py:433-441` lists HARD RULES in the Mode B system prompt:
```
NEVER say: "bạn nên kiểm soát", "đừng ăn", "không tốt"
ALWAYS say: "có thể bạn đang...", "một số người nhận thấy rằng..."
```

If the LLM ignores these rules, it could produce judgmental responses. There is no post-processing step that scans the Mode B output for prohibited phrases.

**Severity:** Medium
**Intent:** Adversarial (prompt injection) or non-adversarial (model behavior).
**Fix:**

```python
# After Mode B result, add output filter:
PROHIBITED_MODE_B_PHRASES = [
    "nên kiểm soát", "đừng ăn", "không tốt cho bạn", 
    "bạn sai", "kiêng ăn", "ngừng ăn",
]

def _filter_mode_b_output(text: str) -> str:
    for phrase in PROHIBITED_MODE_B_PHRASES:
        if phrase in text.lower():
            # Replace with empathetic alternative
            text = text.replace(phrase, "[phản ứng cảm xúc là bình thường]")
    return text
```

---

### C-4: Web Researcher Tavily vs. AI Synthesis Disclaimer

**Finding:** ⚠️ **LOW — Disclaimer only on fallback, not on real Tavily results**

`web_researcher_agent.py:534-541`: When Tavily is unavailable, `_ai_synthesis_fallback()` adds:
```python
f["ai_synthesis_disclaimer"] = (
    "Thông tin này được tổng hợp từ kiến thức AI, "
    "không phải từ web search thực. Vui lòng verify "
    "trực tiếp từ nguồn trước khi áp dụng."
)
```

When Tavily IS available and returns real web results, the findings are returned WITHOUT this disclaimer. The `_summarize_real_results()` method (lines 461-504) passes content from real web sources to an AI summarizer, which could hallucinate claims even from real snippets. There is **no disclaimer** added to real Tavily results.

**Severity:** Low
**Intent:** Non-adversarial.
**Fix:** Add a standard medical disclaimer to ALL web research output:

```python
# In _build_text_for_orchestrator(), append disclaimer to all findings:
DISCLAIMER = (
    "\n\n⚠️ Thông tin trên chỉ mang tính tham khảo. "
    "Không thay thế được tư vấn y khoa chuyên môn. "
    "Nguồn: SmartMeal Web Research."
)
```

---

### C-5: Allergen Filter — Meal Name Not Checked

**Finding:** ⚠️ **MEDIUM — Food name allergens not explicitly checked**

`_verify_no_allergens()` at `nutrition_advisor_agent.py:908-913`:

```python
suggestion_text = (
    s.get("suggestion", "") + " " +
    s.get("preparation", "") + " " +
    " ".join(s.get("alternatives", []))
).lower()
if not any(a.lower() in suggestion_text for a in hard_avoid):
    clean_suggestions.append(s)
```

The `suggestion` field (e.g., `"Bánh mì pate"`) is included in the check. The allergen `"pate"` IS a substring of `"bánh mì pate"`, so it WOULD be filtered.

BUT: if the allergen is stored as `"peanut"` and the food is `"Bơ đậu phộng"` (Vietnamese), the string match fails. The hard_avoid list from `profile.allergies` contains raw allergen strings — not normalized to Vietnamese equivalents.

**Example:** Allergen = `"peanut"` → hard_avoid = `["peanut"]`. Food = `"đậu phộng"` (peanuts). `"peanut"` not in `"đậu phộng"`. **NOT filtered.**

**Severity:** Medium
**Intent:** Non-adversarial. Common for users with peanut/tree nut allergies using the system in Vietnamese.
**Fix:**

```python
# Add allergen synonym mapping:
ALLERGEN_SYNONYMS = {
    "peanut": ["đậu phộng", "lạc", "bơ đậu phộng", "peanut", "groundnut"],
    "milk": ["sữa", "cheese", "phô mai", "dairy", "milk"],
    "shellfish": ["tôm", "cua", "ghẹ", "nghêu", "sò", "hàu", "shellfish"],
    "egg": ["trứng", "egg"],
    "soy": ["đậu nành", "đậu", "soy", "tofu"],
    "wheat": ["lúa mì", "bột mì", "wheat", "gluten"],
    "fish": ["cá", "fish"],
}

def _allergen_matches(allergen: str, text: str) -> bool:
    text_lower = text.lower()
    if allergen.lower() in text_lower:
        return True
    synonyms = ALLERGEN_SYNONYMS.get(allergen.lower(), [])
    return any(syn in text_lower for syn in synonyms)
```

---

## SECTION D: Data Writer Safety Gaps

---

### D-1: Proposal Confirmation Security

**Finding:** ✅ **GOOD — All authorization checks in place**

`ai_chatbot.py:329-371` confirms:

1. ✅ **Atomic GETDEL** (line 345): `await redis.getdel(proposal_key)` — prevents double-execution from concurrent requests.
2. ✅ **TTL enforcement** (implicit in Redis): Proposals stored in Redis expire (TTL check not visible but Redis keyspace expiration handles this).
3. ✅ **Session ID match** (line 361): `if str(proposal.session_id) != str(session_id)` — prevents cross-session confirmation.
4. ✅ **User ID embedded in key** (line 342): `f"proposal:{current_user.id}:{proposal_id}"` — prevents cross-user confirmation.
5. ❌ **NO explicit TTL value check**: The proposal schema (`update_proposal.py`) does NOT include a `created_at` or `expires_at` field. TTL is enforced by Redis key expiration, but the proposal payload itself has no timestamp.

**Verdict:** Well-secured. The missing TTL in payload is acceptable since Redis enforces expiration at the key level.

---

### D-2: NutritionGoal Range Validation

**Finding:** ⚠️ **MEDIUM — No application-layer minimum calorie check**

`nutrition_goal.py` line 49: `daily_calorie_target: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)` — no CHECK constraint.

A malicious admin or bug could set `daily_calorie_target = 100`. The `_write_nutrition_goal()` function at `data_writers.py:396-427` accepts this value without validation:

```python
for raw_field, db_field in field_mapping.items():
    if raw_field in data:
        updates[db_field] = data[raw_field]  # No range check
```

**Severity:** Medium
**Intent:** Requires admin-level access or a bug in the proposal generation code.
**Fix:**

```python
# In data_writers.py, _write_nutrition_goal():
MIN_DAILY_CALORIES = 1000  # kcal — absolute clinical minimum

for raw_field, db_field in field_mapping.items():
    if raw_field in data:
        value = data[raw_field]
        if db_field == "daily_calorie_target":
            if not (MIN_DAILY_CALORIES <= value <= 10000):
                return DataWriteResult(
                    success=False, target=UpdateTarget.NUTRITION_GOAL,
                    message="Giá trị calories không hợp lệ",
                    error=f"daily_calorie_target must be {MIN_DAILY_CALORIES}-10000, got {value}",
                )
        updates[db_field] = value
```

---

### D-3: Body Weight Range Validation

**Finding:** ⚠️ **MEDIUM — No range check on weight writes**

`_write_body_weight()` at `data_writers.py:164-197`:

```python
weight = data.get("weight_kg")
if not weight:
    return DataWriteResult(...)
await db.execute(
    update(UserProfile)
    .where(UserProfile.user_id == user_uuid)
    .values(current_weight_kg=weight)
)
```

Values of 5 kg or 500 kg would be accepted. The ProgressLog also has no CHECK constraint on `weight_kg` (defined as `Numeric(6, 2)`).

**Triggering input:** `{"weight_kg": 5, "measured_at": "2026-06-06"}` → writes 5 kg to user profile.

**Severity:** Medium
**Intent:** Non-adversarial (accidental data entry error) or adversarial (malicious proposal generation).
**Fix:**

```python
MIN_WEIGHT_KG = 20.0   # ~44 lbs
MAX_WEIGHT_KG = 300.0  # ~660 lbs

weight = data.get("weight_kg")
if not weight:
    return DataWriteResult(...)
if not (MIN_WEIGHT_KG <= float(weight) <= MAX_WEIGHT_KG):
    return DataWriteResult(
        success=False, target=UpdateTarget.BODY_WEIGHT,
        message=f"Can nang phai trong khoang {MIN_WEIGHT_KG}-{MAX_WEIGHT_KG} kg",
        error=f"weight_kg={weight} outside valid range",
    )
```

---

### D-4: ProgressLog Date Uniqueness (Same-Day Submissions)

**Finding:** ✅ **CORRECTLY HANDLED — Unique constraint enforces one entry per day**

`ProgressLog.__table_args__` at `progress_log.py:45-47`:
```python
UniqueConstraint("user_id", "log_date", name="uq_progress_user_date"),
```

When `_write_body_weight()` inserts a `ProgressLog` on the same date as an existing entry:
1. First write: INSERT succeeds
2. Second write: `IntegrityError` from unique constraint violation → caught by `data_writers.py:70-78` → rollback → returns error message "Luu du lieu that bai"

**Verdict:** Correctly handles duplicate submissions. The second attempt fails gracefully.

---

### D-5: Meal Log Recalculation with Negative Calories

**Finding:** ⚠️ **MEDIUM — Negative calories stored without constraint**

`meal_service.py:147-150`:
```python
meal_log.total_calories = float(round_decimal(
    sum(Decimal(str(item.calories)) for item in items)))
```

If a MealItem has `calories < 0`, the sum is negative. The `MealItem.calories` column has no CHECK constraint (`Numeric(10,2)`). A malicious user who can edit a meal item (via an API endpoint) could set calories to -5000, and the recalculation would store a negative total.

The `MealLog.total_calories` column also has no CHECK constraint. The `POST /meal-logs/{id}/recalculate` endpoint (line 157-175) recalculates and returns the updated log without validating the result.

**Severity:** Medium
**Intent:** Requires ability to edit MealItem calories (likely via a PATCH endpoint that may or may not exist publicly).
**Fix:**

```python
# In meal_service.py, recalculate_meal_totals():
async def recalculate_meal_totals(db: AsyncSession, meal_log_id):
    ...
    total_cal = float(round_decimal(sum(Decimal(str(item.calories)) for item in items)))
    if total_cal < 0:
        total_cal = 0
    meal_log.total_calories = total_cal
    # Same for protein, carb, fat
```

---

## Summary Table

| ID | Category | Finding | Severity | Type |
|----|----------|---------|----------|------|
| A-1 | Nutrition | BMI floor protects underweight users | Low | Non-adversarial |
| A-2 | Nutrition | Protein may over-recommend for small users | Medium | Non-adversarial |
| A-3 | Nutrition | Unrecognized activity → Mode A skipped | Low | Non-adversarial |
| A-4 | Nutrition | Gender validation covers edge cases | None | — |
| A-5 | Nutrition | No upper bound on TDEE/macros | Medium | Non-adversarial |
| A-6 | Nutrition | Zero weight guarded | None | — |
| A-7 | Nutrition | Zero carbs possible with aggressive deficit | Low | Non-adversarial |
| B-1 | Safety | Exercise name bypass (synonyms, Vietnamese, emoji) | Medium | Adversarial |
| B-2 | Safety | Neck/ankle injury not mapped to region | Medium | Non-adversarial |
| B-3 | Safety | Severity word evasion | None | — |
| B-4 | Safety | False-positive severe keywords → forced rest | High | Non-adversarial |
| B-5 | Safety | Biomechanical stress not blocked by name | Medium | Non-adversarial |
| B-6 | Safety | Post-filter logic correct but partial | Low | — |
| C-1 | Disclaimer | No out-of-band disclaimer in user-facing output | Medium | Adversarial |
| C-2 | Disclaimer | "Bỏ bữa" regex false positives | High | Non-adversarial |
| C-3 | Disclaimer | Mode B language rules not enforced | Medium | Adversarial |
| C-4 | Disclaimer | No disclaimer on real Tavily results | Low | Non-adversarial |
| C-5 | Disclaimer | Allergen synonyms not normalized | Medium | Non-adversarial |
| D-1 | Data | Proposal confirm well-secured | None | — |
| D-2 | Data | No calorie range validation on NutritionGoal | Medium | Adversarial |
| D-3 | Data | No weight range validation on writes | Medium | Non-adversarial |
| D-4 | Data | Same-day ProgressLog correctly rejected | None | — |
| D-5 | Data | Negative calories possible on recalculation | Medium | Adversarial |

### Critical (Priority Fix):
*(none — no confirmed data corruption or patient harm vectors)*

### High Priority:
- **C-2**: Behavioral pattern false positives (eating disorder misclassification)
- **B-4**: False-positive severe keywords causing forced rest

### Medium Priority:
- **A-2**: Protein cap for small users
- **A-5**: No TDEE/macro upper bound
- **B-1**: Exercise name bypass vectors
- **B-2**: Neck/ankle injury mapping gap
- **B-5**: Biomechanical blocking gaps
- **C-1**: Out-of-band medical disclaimer
- **C-3**: Mode B language enforcement
- **C-5**: Allergen synonym normalization
- **D-2**: Calorie range validation
- **D-3**: Weight range validation
- **D-5**: Negative calorie guard

### Low Priority:
- A-1, A-3, A-7, B-6, C-4
