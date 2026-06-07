"""
Injury Safety Matrix — Cross-agent safety layer for FitnessCoachAgent.

Applies mandatory exercise restrictions when injury/medical data is detected
from HealthMonitorAgent (Phase 1). Acts as a rule-based gate BEFORE the LLM
formulates any workout recommendation, ensuring no dangerous exercise
slips through even if the AI model is permissive.

Usage:
    from app.agents.safety_matrix import SafetyMatrix, apply_safety_overrides

    matrix = SafetyMatrix()
    overrides = matrix.evaluate(
        active_issues=context.agent_results["health"].content.get("active_issues", []),
        sore_areas=body_sore_areas,
        injury_areas=body_injury_areas,
        fitness_clearance=context.agent_results["health"].content.get("fitness_clearance", {}),
    )
"""

from dataclasses import dataclass, field
from typing import Any


# ─── The matrix: injury region → blocked exercises + safe alternatives ───────────


@dataclass
class ExerciseBlock:
    """Describes a blocked exercise and its safe replacement."""
    blocked_name: str
    blocked_name_vi: str
    reason: str
    alternatives: list[str]


_BACK_MATRIX: list[ExerciseBlock] = [
    ExerciseBlock(
        blocked_name="Barbell Squat",
        blocked_name_vi="Squat tạ",
        reason="Tạo áp lực trục thẳng đứng lên cột sống",
        alternatives=["Leg Press (tựa lưng thẳng)", "Leg Extension ngồi", "Lying Leg Curl"],
    ),
    ExerciseBlock(
        blocked_name="Deadlift",
        blocked_name_vi="Deadlift",
        reason="Gây áp lực cực lớn lên đĩa đệm và cột sống thắt lưng",
        alternatives=["Romanian Deadlift nhẹ", "Good Morning không tạ", "Hyperextension"],
    ),
    ExerciseBlock(
        blocked_name="Overhead Press",
        blocked_name_vi="Overhead Press",
        reason="Gây áp lực nén lên cột sống cổ và thắt lưng",
        alternatives=["Seated Dumbbell Press (lưng tựa ghế)", "Lateral Raise đứng nhẹ"],
    ),
    ExerciseBlock(
        blocked_name="Bent Over Row",
        blocked_name_vi="Bent Over Row",
        reason="Gây áp lực lên đĩa đệm thắt lưng khi gập người",
        alternatives=["Chest Supported Row", "Seated Cable Row (lưng thẳng)"],
    ),
    ExerciseBlock(
        blocked_name="Jump Squat",
        blocked_name_vi="Jump Squat",
        reason="Tải trọng rơi tác động mạnh lên cột sống",
        alternatives=["Goblet Squat chậm", "Bodyweight Squat không nhảy"],
    ),
]

_SHOULDER_MATRIX: list[ExerciseBlock] = [
    ExerciseBlock(
        blocked_name="Bench Press",
        blocked_name_vi="Bench Press",
        reason="Tạo áp lực lên khớp vai khi hạ tạ",
        alternatives=["Incline Dumbbell Press (góc nhẹ)", "Push-up chống gối", "Cable Fly nhẹ"],
    ),
    ExerciseBlock(
        blocked_name="Plank",
        blocked_name_vi="Plank",
        reason="Gây áp lực nén lên cột sống cổ và vai khi giữ tư thế",
        alternatives=["Dead Bug", "Glute Bridge", "Bird Dog"],
    ),
    ExerciseBlock(
        blocked_name="Push-up",
        blocked_name_vi="Push-up thông thường",
        reason="Tạo áp lực lên khớp vai và khuỷu tay ở vị trí hạ người",
        alternatives=["Knee Push-up", "Incline Push-up (tay đặt cao)", "Wall Push-up"],
    ),
    ExerciseBlock(
        blocked_name="Shoulder Press",
        blocked_name_vi="Shoulder Press ngồi",
        reason="Nén khớp vai ở vị trí ab-90 độ",
        alternatives=["Front Raise", "Upright Row nhẹ", "Face Pull"],
    ),
    ExerciseBlock(
        blocked_name="Burpee",
        blocked_name_vi="Burpee",
        reason="Nhảy + plank gây áp lực kép lên vai và cột sống",
        alternatives=["Step-up", "Mountain Climber chậm", "Đi bộ nhanh"],
    ),
]

_KNEE_MATRIX: list[ExerciseBlock] = [
    ExerciseBlock(
        blocked_name="Jump Squat",
        blocked_name_vi="Jump Squat",
        reason="Lực rơi tác động mạnh lên dây chằng và sụn chêm",
        alternatives=["Goblet Squat chậm", "Leg Press nhẹ", "Leg Extension"],
    ),
    ExerciseBlock(
        blocked_name="Burpee",
        blocked_name_vi="Burpee",
        reason="Bước nhảy gây lực va đập trực tiếp lên khớp gối",
        alternatives=["Step-tap", "Marching in place", "Seated leg raise"],
    ),
    ExerciseBlock(
        blocked_name="Lunge",
        blocked_name_vi="Lunge (tiến/lùi)",
        reason="Góc gối sâu gây áp lực lên dây chằng chéo trước",
        alternatives=["Split Squat (tĩnh)", "Side Lying Leg Raise", "Đạp xe ngược"],
    ),
    ExerciseBlock(
        blocked_name="Box Jump",
        blocked_name_vi="Box Jump",
        reason="Lực tiếp đất tác động mạnh vào khớp gối",
        alternatives=["Step-up lên thang", "Romanian Deadlift", "Hip Thrust"],
    ),
    ExerciseBlock(
        blocked_name="Running",
        blocked_name_vi="Chạy bộ",
        reason="Lực va đập liên tục khi chân chạm đất",
        alternatives=["Đạp xe", "Bơi lội", "Elliptical (máy elip)"],
    ),
]

_WRIST_MATRIX: list[ExerciseBlock] = [
    ExerciseBlock(
        blocked_name="Push-up",
        blocked_name_vi="Push-up",
        reason="Trọng lượng cơ thể dồn xuống cổ tay khi hạ người",
        alternatives=["Knee Push-up", "Wall Push-up", "Incline Push-up"],
    ),
    ExerciseBlock(
        blocked_name="Plank",
        blocked_name_vi="Plank",
        reason="Cổ tay chống trọng lượng toàn bộ cơ thể",
        alternatives=["RKC Plank (khuỷu tay)", "Side Plank", "Glute Bridge"],
    ),
    ExerciseBlock(
        blocked_name="Bench Press",
        blocked_name_vi="Bench Press",
        reason="Cổ tay gập khi giữ thanh tạ dọc",
        alternatives=["Dumbbell Press ngang ngực", "Machine Chest Press", "Cable Fly"],
    ),
]

_HIP_MATRIX: list[ExerciseBlock] = [
    ExerciseBlock(
        blocked_name="Deadlift",
        blocked_name_vi="Deadlift",
        reason="Gập hông sâu với tải trọng nén lên khớp háng và dây chằng",
        alternatives=["Romanian Deadlift nhẹ", "Hip Thrust", "Glute Bridge"],
    ),
    ExerciseBlock(
        blocked_name="Lunge",
        blocked_name_vi="Lunge",
        reason="Bước dài gây áp lực lên khớp háng",
        alternatives=["Goblet Squat", "Leg Press", "Standing Hip Abduction"],
    ),
    ExerciseBlock(
        blocked_name="Hip Thrust nặng",
        blocked_name_vi="Hip Thrust với tạ nặng",
        reason="Tải trọng trực tiếp lên xương chậu có thể gây đau khớp háng",
        alternatives=["Glute Bridge bodyweight", "Clamshell", "Fire Hydrant"],
    ),
]

_CARDIO_LIMITED: list[ExerciseBlock] = [
    ExerciseBlock(
        blocked_name="Running",
        blocked_name_vi="Chạy bộ",
        reason="Cơ thể đang trong trạng thái bệnh lý — cardio cường độ cao không phù hợp",
        alternatives=["Đi bộ nhẹ nhàng", "Đạp xe tốc độ chậm", "Yoga stretch nhẹ"],
    ),
    ExerciseBlock(
        blocked_name="HIIT",
        blocked_name_vi="HIIT",
        reason="Nhịp tim cao khi đang bệnh có thể gây biến chứng",
        alternatives=["Đi bộ", "Stretching nhẹ", "Thở diaphragmatic"],
    ),
    ExerciseBlock(
        blocked_name="Burpee",
        blocked_name_vi="Burpee",
        reason="Nhảy + gập người kích hoạt cơ hoành khi đang bệnh",
        alternatives=["Step-tap", "Arm circles nhẹ", "Nằm thở sâu"],
    ),
]

# ─── Region-to-matrix lookup ────────────────────────────────────────────────────

_REGION_MATRICES: dict[str, list[ExerciseBlock]] = {
    "back":         _BACK_MATRIX,
    "lower_back":   _BACK_MATRIX,
    "spine":        _BACK_MATRIX,
    "shoulder":     _SHOULDER_MATRIX,
    "shoulders":    _SHOULDER_MATRIX,
    "knee":         _KNEE_MATRIX,
    "knees":        _KNEE_MATRIX,
    "ligament":     _KNEE_MATRIX,
    "wrist":        _WRIST_MATRIX,
    "wrists":       _WRIST_MATRIX,
    "hand":         _WRIST_MATRIX,
    "hands":        _WRIST_MATRIX,
    "hip":          _HIP_MATRIX,
    "hips":         _HIP_MATRIX,
    # Expanded body region coverage
    "ankle":        _KNEE_MATRIX,
    "foot":         _KNEE_MATRIX,
    "chest":        _SHOULDER_MATRIX,
    "abdomen":      _BACK_MATRIX,
    "cardio_limited": _CARDIO_LIMITED,
    "illness":      _CARDIO_LIMITED,
}


# ─── Cross-reference with HealthMonitor fitness_clearance codes ────────────────

_CLEARANCE_TO_REGION: dict[str, str] = {
    "heavy_lifting":   "back",
    "core_exercises":  "back",
    "high_intensity":  "cardio_limited",
    "running":         "knee",
    "jumping":         "knee",
    "upper_body":      "shoulder",
    "push_exercises":  "shoulder",
}


@dataclass
class SafetyOverride:
    """Result of evaluating the safety matrix for one injury region."""
    region: str
    blocked: list[str] = field(default_factory=list)
    blocked_vi: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)


@dataclass
class SafetyResult:
    """Aggregated safety overrides for a complete recommendation."""
    applied: bool = False
    overrides: list[SafetyOverride] = field(default_factory=list)
    all_blocked: list[str] = field(default_factory=list)
    all_blocked_vi: list[str] = field(default_factory=list)
    all_alternatives: list[str] = field(default_factory=list)
    forced_workout_type: str | None = None  # "rest" | "light_activity" | None


class SafetyMatrix:
    """
    Rule-based injury safety gate.
    Reads health data from Phase 1 (HealthMonitorAgent) and produces
    mandatory exercise overrides that FitnessCoachAgent MUST respect.
    """

    def evaluate(
        self,
        active_issues: list[dict[str, Any]],
        sore_areas: list[str],
        injury_areas: list[str],
        fitness_clearance: dict[str, Any],
    ) -> SafetyResult:
        """
        Evaluate the safety matrix against detected injuries/conditions.

        Returns a SafetyResult with:
          - all_blocked: list of blocked exercise names
          - all_alternatives: list of safe replacements
          - forced_workout_type: "rest" | "light_activity" | None
        """
        result = SafetyResult()

        # ── 1. Resolve regions from active_issues ────────────────────────────────
        regions = self._regions_from_issues(active_issues)

        # ── 2. Merge in explicit injury/sore areas from body snapshot ─────────
        for area in injury_areas:
            region = self._normalize_area(area)
            if region and region not in regions:
                regions.append(region)

        for area in sore_areas:
            region = self._normalize_area(area)
            if region and region not in regions:
                regions.append(region)

        # ── 3. Merge in fitness_clearance codes from HealthMonitor ─────────────
        avoid_codes = fitness_clearance.get("avoid", []) or []
        for code in avoid_codes:
            if code in _CLEARANCE_TO_REGION:
                region = _CLEARANCE_TO_REGION[code]
                if region not in regions:
                    regions.append(region)

        # ── 4. Apply no_exercise clearance ─────────────────────────────────────
        cleared_for = fitness_clearance.get("cleared_for", []) or []
        if "no_exercise" in cleared_for or "all_exercise" in avoid_codes:
            result.forced_workout_type = "rest"
            result.applied = True
            return result

        # ── 5. Collect blocks from all regions ─────────────────────────────────
        seen_exercises: set[str] = set()
        for region in regions:
            matrix = _REGION_MATRICES.get(region, [])
            override = SafetyOverride(region=region)
            for block in matrix:
                if block.blocked_name not in seen_exercises:
                    seen_exercises.add(block.blocked_name)
                    override.blocked.append(block.blocked_name)
                    override.blocked_vi.append(block.blocked_name_vi)
                    override.alternatives.extend(block.alternatives)
            if override.blocked:
                result.overrides.append(override)
                result.all_blocked.extend(override.blocked)
                result.all_blocked_vi.extend(override.blocked_vi)
                result.all_alternatives.extend(override.alternatives)

        # ── 6. Force workout type based on severity ─────────────────────────────
        has_severe = self._has_severe_issue(active_issues)
        if has_severe:
            result.forced_workout_type = "rest"
        elif result.applied and not result.forced_workout_type:
            result.forced_workout_type = "light_activity"

        result.applied = result.applied or len(result.overrides) > 0
        return result

    def _regions_from_issues(self, issues: list[dict[str, Any]]) -> list[str]:
        """Infer affected body regions from active_issues."""
        regions: list[str] = []
        area_keywords: dict[str, list[str]] = {
            "back":         ["lưng", "cột sống", "spine", "lower back", "thắt lưng", "đau lưng", "thoát vị", "disc"],
            "shoulder":     ["vai", "shoulder", "rotator", "đau vai", "cổ", "neck"],
            "knee":         ["gối", "knee", "dây chằng", "ligament", "sụn chêm", "đầu gối", "bắp chân", "cẳng chân"],
            "wrist":        ["cổ tay", "wrist", "tay", "carpal", "ngón tay"],
            "hip":          ["hông", "hip", "xương chậu", "SI joint"],
            "ankle":        ["mắt cá chân", "cổ chân", "bàn chân", "chân"],
            "chest":        ["ngực"],
            "abdomen":      ["bụng", "bụng dưới"],
            "illness":      ["cảm", "sốt", "ho", "nhiễm", "bệnh", "symptom", "viêm khớp", "viêm cơ tim", "viêm phổi"],
        }
        for issue in issues:
            combined = (
                str(issue.get("issue", "")) + " " +
                str(issue.get("description", "")) + " " +
                str(issue.get("recommendation", ""))
            ).lower()
            for region, keywords in area_keywords.items():
                if any(kw in combined for kw in keywords):
                    if region not in regions:
                        regions.append(region)
            # Check explicit fitness_restriction codes
            fit_restrict = issue.get("fitness_restriction") or []
            for code in fit_restrict:
                mapped = _CLEARANCE_TO_REGION.get(code)
                if mapped and mapped not in regions:
                    regions.append(mapped)
        return regions

    def _normalize_area(self, area: str) -> str | None:
        """Map ORM area names to matrix region keys."""
        mapping = {
            "lower_back":  "back",
            "upper_back":  "back",
            "spine":       "back",
            "back":        "back",
            "neck":        "shoulder",
            "cổ":          "shoulder",
            "shoulder":    "shoulder",
            "right_shoulder": "shoulder",
            "left_shoulder":  "shoulder",
            "knee":        "knee",
            "right_knee":  "knee",
            "left_knee":   "knee",
            # Expanded mapping for Vietnamese body region names
            "bắp chân":    "knee",
            "cẳng chân":   "knee",
            "mắt cá chân": "ankle",
            "cổ chân":     "ankle",
            "bàn chân":    "foot",
            "ngực":        "chest",
            "bụng":        "abdomen",
            "wrist":       "wrist",
            "right_wrist": "wrist",
            "left_wrist":  "wrist",
            "right_arm":   "wrist",
            "left_arm":    "wrist",
            "hip":         "hip",
            "right_hip":   "hip",
            "left_hip":    "hip",
        }
        mapped = mapping.get(area.lower())
        return mapped if mapped else None

    def _has_severe_issue(self, issues: list[dict[str, Any]]) -> bool:
        """
        Return True if any issue has severe musculoskeletal impact.

        Before flagging as severe, we check for MITIGATING QUALIFIER keywords
        that reduce severity. If a mitigating qualifier appears in the same
        issue text, the issue is treated as MILD (region restriction only,
        not full forced rest).

        Mitigating qualifiers: nhẹ (mild), hơi (a bit), sơ sơ (slight),
        vừa (moderate), mild, light, slight, minor.
        """
        MITIGATING_QUALIFIERS = {
            "nhẹ", "hơi", "sơ sơ", "vừa", "mild", "light", "slight", "minor",
            "đỡ", "bớt", "hồi phục", "recovery",
        }
        # Clinically specific severe-issue phrases (replaced generic "viêm")
        SEVERE_KEYWORDS = [
            "chấn thương", "injury", "gãy", "trật", "thoát vị",
            "viêm khớp", "viêm cơ tim", "viêm phổi", "nhiễm trùng nặng",
        ]

        for issue in issues:
            severity = issue.get("severity", "").lower()
            if severity == "severe":
                # Check for mitigating qualifiers in the text before flagging as severe
                combined = (
                    str(issue.get("issue", "")) + " " +
                    str(issue.get("description", ""))
                ).lower()

                has_mitigating = any(q in combined for q in MITIGATING_QUALIFIERS)
                has_severe_keyword = any(kw in combined for kw in SEVERE_KEYWORDS)

                if has_mitigating and has_severe_keyword:
                    # Mitigated: treat as mild → region restriction only, not forced rest
                    continue
                if has_severe_keyword:
                    return True
                if severity == "severe" and not has_severe_keyword:
                    # Explicit "severe" label without any severe keyword → still severe
                    return True
            elif severity in ("moderate", "mild"):
                # Even moderate/mild issues with severe keywords are checked
                combined = (
                    str(issue.get("issue", "")) + " " +
                    str(issue.get("description", ""))
                ).lower()
                if any(kw in combined for kw in SEVERE_KEYWORDS):
                    # Severe keyword present → check for mitigating qualifiers
                    has_mitigating = any(q in combined for q in MITIGATING_QUALIFIERS)
                    if not has_mitigating:
                        return True
        return False


# ─── Convenience function ───────────────────────────────────────────────────────


def apply_safety_overrides(
    active_issues: list[dict[str, Any]],
    sore_areas: list[str],
    injury_areas: list[str],
    fitness_clearance: dict[str, Any],
) -> SafetyResult:
    """
    One-shot evaluation of the safety matrix.
    Call this at the top of FitnessCoachAgent.execute() BEFORE building the prompt.
    """
    matrix = SafetyMatrix()
    return matrix.evaluate(
        active_issues=active_issues,
        sore_areas=sore_areas,
        injury_areas=injury_areas,
        fitness_clearance=fitness_clearance,
    )
