"""Eval for skills/hello-world/. Delete with the hello-world skill once a real eval is in place.

Contract: see evals/README.md.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any


REQUIRED_KEYS = {"mean", "median", "stdev", "outliers"}
EXPECTED = {
    # Computed from data/example.csv at template time. Recompute if you edit the file.
    "mean": 7.39,
    "median": 3.65,
    "stdev": 12.21,
    "outlier_count": 1,  # the value 42.0 in row 9
}
TOL = 0.05  # 5% tolerance on mean/median/stdev


def evaluate(skill_output: dict[str, Any], fixture_path: str | Path | None = None) -> dict[str, Any]:
    """Check the hello-world skill's output against the known stats for data/example.csv."""
    missing = REQUIRED_KEYS - set(skill_output)
    if missing:
        return {
            "passed": False,
            "failure_mode": "missing-keys",
            "evidence": {"missing": sorted(missing)},
        }

    for key in ("mean", "median", "stdev"):
        actual = float(skill_output[key])
        expected = EXPECTED[key]
        if math.isclose(actual, expected, rel_tol=TOL, abs_tol=TOL):
            continue
        return {
            "passed": False,
            "failure_mode": f"value-mismatch:{key}",
            "evidence": {"actual": actual, "expected": expected, "tolerance": TOL},
        }

    outliers = skill_output.get("outliers") or []
    if len(outliers) != EXPECTED["outlier_count"]:
        return {
            "passed": False,
            "failure_mode": "outlier-count-mismatch",
            "evidence": {"actual": len(outliers), "expected": EXPECTED["outlier_count"]},
        }

    return {
        "passed": True,
        "failure_mode": None,
        "evidence": {"checked_keys": sorted(REQUIRED_KEYS)},
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: hello_world_eval.py <skill_output.json>")
        sys.exit(2)
    out = json.loads(Path(sys.argv[1]).read_text())
    result = evaluate(out)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
