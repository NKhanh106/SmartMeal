"""Show exactly which tests still fail and what fixable root cause."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent.parent

short = {
    "AllergenViolationMetric": "Allergen",
    "NutritionalConstraintViolationMetric": "NCV",
    "NutritionalEstimationErrorMetric": "NEE",
    "InterAgentConsistencyMetric": "IAC",
    "RecipeFeasibilityMetric": "RFS",
    "AgentRoleAdherenceMetric": "ARA",
    "TaskDecompositionQualityMetric": "TDQ",
}


def show(path, label):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    fails = [r for r in data["results"] if r["status"] != "passed"]
    if not fails:
        print(f"\n=== {label}: ALL PASS ===")
        return
    print(f"\n=== {label}: {len(fails)}/{len(data['results'])} FAIL ===")
    for r in fails:
        print(f"\n  {r['test_id']} (overall={r['overall_score']:.4f})")
        # Show only metrics scoring < 0.5
        weak = []
        for md in (r.get("metric_details") or []):
            n = md.get("name", "")
            if n == "UNKNOWN" or n not in short:
                continue
            s = md.get("score", 0)
            if s < 0.5:
                reason = md.get("reason") or md.get("error") or ""
                if md.get("violations"):
                    reason = "; ".join(
                        v.get("type", "") if isinstance(v, dict) else str(v)
                        for v in md.get("violations", [])[:2]
                    )
                weak.append(f"{short[n]}={s:.2f} [{reason[:80]}]")
        if weak:
            for w in weak:
                print(f"    • {w}")


show(here / "full_tier_a.json", "FULL")
show(here / "partial_tier_a.json", "PARTIAL")
show(here / "baseline_tier_a.json", "BASELINE")