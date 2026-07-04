"""Diagnose why so few tests pass."""
import json
from pathlib import Path
from collections import Counter, defaultdict

here = Path(__file__).resolve().parent.parent

print("=" * 78)
print("DIAGNOSIS: why pass rate is low (1/8 to 2/8 of Tier A)")
print("=" * 78)

for cfg in ["baseline", "partial", "full"]:
    p = here / f"{cfg}_tier_a.json"
    with open(p, encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n{'='*78}")
    print(f"CONFIG = {cfg.upper()}")
    print(f"{'='*78}")

    # 1. status distribution
    statuses = Counter(r["status"] for r in data["results"])
    print(f"\n[1] Status distribution: {dict(statuses)}")

    # 2. What % of tests scored >= 0.8 (passing threshold)
    above_80 = sum(1 for r in data["results"] if r["overall_score"] >= 0.8)
    print(f"[2] Tests scoring >= 0.8: {above_80}/{len(data['results'])}")

    # 3. Score bucket distribution
    buckets = Counter()
    for r in data["results"]:
        s = r["overall_score"]
        if s >= 0.8:
            buckets["0.8-1.0 (pass)"] += 1
        elif s >= 0.6:
            buckets["0.6-0.8 (near)"] += 1
        elif s >= 0.4:
            buckets["0.4-0.6 (fail)"] += 1
        else:
            buckets["< 0.4 (deep fail)"] += 1
    print(f"[3] Score buckets: {dict(buckets)}")

    # 4. Per-metric failure root cause
    print(f"\n[4] Per-metric failure analysis (which metric kills the score)")
    print(f"{'Test':<20} {'Overall':>8} {'Nutr.S':>7} {'Doman.Q':>7} {'Multi':>7}  Failed metric(s)")
    for r in data["results"]:
        ts = r.get("tier_scores") or {}
        ns = ts.get("NUTRITION_SAFETY", 0)
        dq = ts.get("DOMAIN_QUALITY", 0)
        ma = ts.get("MULTI_AGENT_PERFORMANCE", 0)
        # weights
        contrib_ns = ns * 0.40
        contrib_dq = dq * 0.35
        contrib_ma = ma * 0.25
        failing = []
        if contrib_ns < 0.30: failing.append("NS")
        if contrib_dq < 0.30: failing.append("DQ")
        if contrib_ma < 0.20: failing.append("MA")
        print(
            f"{r['test_id']:<20} {r['overall_score']:>8.4f} "
            f"{ns:>7.3f} {dq:>7.3f} {ma:>7.3f}  {' '.join(failing) or '—'}"
        )

    # 5. Look at which individual metrics scored 0 or low
    print(f"\n[5] Individual metrics that scored < 0.5 (root cause of failure)")
    low_metrics = Counter()
    for r in data["results"]:
        for md in (r.get("metric_details") or []):
            name = md.get("name", "")
            if name == "UNKNOWN":
                continue
            score = md.get("score")
            if score is None:
                continue
            if score < 0.5:
                low_metrics[name] += 1
    if low_metrics:
        for name, count in low_metrics.most_common():
            print(f"   - {name}: {count}/{len(data['results'])} tests scored < 0.5")
    else:
        print("   (none)")