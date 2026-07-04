"""Inspect dataset expected_routing for Tier A."""
import json
from pathlib import Path

d = json.loads(Path("tests/sma_eval/dataset.json").read_text(encoding="utf-8"))
tests = d.get("tier_a_hard_constraints", [])
print(f"Tier A test count: {len(tests)}")
for t in tests:
    print(
        f"{t['test_id']:<22} routing={t.get('expected_routing')!r:<30} "
        f"input={t.get('input_message', '')[:70]!r}"
    )