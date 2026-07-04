"""Find exact root cause for each failing test in FULL config."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent.parent
data = json.loads((here / "full_tier_a.json").read_text(encoding="utf-8"))

# 7 metric short names matching the brief
short = {
    "AllergenViolationMetric": "Allergen",
    "NutritionalConstraintViolationMetric": "NCV",
    "NutritionalEstimationErrorMetric": "NEE",
    "InterAgentConsistencyMetric": "IAC",
    "RecipeFeasibilityMetric": "RFS",
    "AgentRoleAdherenceMetric": "ARA",
    "TaskDecompositionQualityMetric": "TDQ",
}

print(f"\n{'TEST':<22} {'STATUS':<10} {'OVERALL':>8}")
for r in data["results"]:
    print(f"{r['test_id']:<22} {r['status']:<10} {r['overall_score']:>8.4f}")
    if r["status"] == "passed":
        continue
    print(f"  ─ Fail breakdown ─")
    for md in (r.get("metric_details") or []):
        name = md.get("name", "")
        if name == "UNKNOWN":
            print(f"  • UNKNOWN metric (exception)  score={md.get('score')}")
            continue
        if name not in short:
            continue
        s = md.get("score", 0)
        passed = md.get("passed", False)
        flag = "PASS" if passed else "FAIL"
        reason = md.get("reason", "")
        violations = md.get("violations", [])
        warnings = md.get("warnings", [])
        bmr = md.get("bmr_floor", "")
        maxc = md.get("max_calories_mentioned", "")
        print(f"  • {short[name]:<7} score={s:.3f} [{flag}]")
        if reason:
            print(f"           reason: {reason}")
        if violations:
            for v in violations[:3]:
                print(f"           violation: {v}")
        if warnings:
            for w in warnings[:3]:
                print(f"           warning: {w}")
        if bmr or maxc is not None:
            print(f"           bmr_floor={bmr} max_calories_mentioned={maxc}")
    print()