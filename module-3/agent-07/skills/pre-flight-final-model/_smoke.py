"""Smoke test for pre-flight-final-model.

Scenario A: build a minimal valid bundle in a tmp dir and assert ``passes=True``.
Scenario B: break the bundle (remove predict.py) and assert ``passes=False``.

Run standalone: ``python3 _smoke.py`` (from this directory).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from pprint import pprint

# Make preflight.py importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight import preflight  # noqa: E402


PREDICT_PY = '''\
import pandas as pd

def predict(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()
'''

MANIFEST = {
    "platform_support": ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"],
    "predict_callable": "predict.py:predict",
}

REPORT_BODY = (
    "# Placeholder report\n\n"
    "This is a stub REPORT.md used by the pre-flight smoke test.\n"
    "It exists only to clear the >= 100 byte size check; real reports "
    "should explain method, validation, and known limitations.\n"
)

EXPERIMENTS_WITH_CLIMB = """\
# EXPERIMENTS.md

## E00 — V0 baseline
- Rung: 0
- Hypothesis: floor to beat.
- Result (dev): yaw 0.01456; CTE 147.44.

## E01 — Rung-1 dynamic single-track attempt
- Rung: 1
- Hypothesis: transient regime carries the largest residual.
- What I changed vs E00: added vy/yr state-integration with C_af fitted per platform.
- Result (dev): yaw 0.01080 (-25.8%); CTE 122.9 (-16.6%).
- Verdict: revert — beaten by E02 rung-0 refinements.
- Things this rules out: pure linear-tyre dynamic ST doesn't beat a well-fit rung 0 on this data.
"""

EXPERIMENTS_RUNG_0_ONLY = """\
# EXPERIMENTS.md

## E00 — V0 baseline
- Rung: 0
- Result (dev): yaw 0.01456; CTE 147.44.

## E01 — refit understeer per platform
- Rung: 0
- Result (dev): yaw 0.0083; CTE 99.
"""


def _build_valid_bundle(d: Path, *, experiments_at: Path | None = None) -> None:
    (d / "predict.py").write_text(PREDICT_PY)
    (d / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    (d / "REPORT.md").write_text(REPORT_BODY)
    # By convention EXPERIMENTS.md lives one level up (working-dir root, sibling
    # of final-model/). The smoke helper places it there unless explicitly
    # overridden.
    target = experiments_at if experiments_at is not None else d.parent / "EXPERIMENTS.md"
    target.write_text(EXPERIMENTS_WITH_CLIMB)


def _print_checks(label: str, result: dict) -> None:
    print(f"\n[smoke] === {label} ===")
    print(f"[smoke] passes = {result['passes']}")
    for c in result["checks"]:
        print(f"  - {c['status']:4s}  {c['name']:35s}  {c['detail']}")
    if result["errors"]:
        print("[smoke] errors:")
        for e in result["errors"]:
            print(f"    * {e}")


def main() -> int:
    # Set cwd so the sample-segment glob resolves.
    repo_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/")
    os.chdir(repo_root)

    # --- Scenario A: valid bundle ----------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle)

        result_a = preflight(bundle)
        _print_checks("Scenario A (valid)", result_a)

        assert result_a["passes"] is True, (
            f"Scenario A should pass; errors={result_a['errors']}"
        )
        assert all(c["status"] == "pass" for c in result_a["checks"]), (
            "Scenario A: expected every check to be 'pass'"
        )

    # --- Scenario B: broken bundle (no predict.py) -----------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle)
        (bundle / "predict.py").unlink()  # break it

        result_b = preflight(bundle)
        _print_checks("Scenario B (broken: predict.py removed)", result_b)

        assert result_b["passes"] is False, "Scenario B should NOT pass"
        assert len(result_b["errors"]) >= 1, "Scenario B should report at least one error"
        # predict_py_present must be the failing check.
        names_failing = {c["name"] for c in result_b["checks"] if c["status"] == "fail"}
        assert "predict_py_present" in names_failing, (
            f"Scenario B: predict_py_present should fail; got failing={names_failing}"
        )

    # --- Scenario C: rung-0-only EXPERIMENTS.md should fail the new check ------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle)
        # Overwrite the parent's EXPERIMENTS.md with a rung-0-only log
        (bundle.parent / "EXPERIMENTS.md").write_text(EXPERIMENTS_RUNG_0_ONLY)

        result_c = preflight(bundle)
        _print_checks("Scenario C (no climb attempt logged)", result_c)

        assert result_c["passes"] is False, "Scenario C should NOT pass"
        names_failing = {c["name"] for c in result_c["checks"] if c["status"] == "fail"}
        assert "experiments_md_has_rung_climb_attempt" in names_failing, (
            "Scenario C: rung-climb check should fail when EXPERIMENTS has only Rung: 0 entries; "
            f"got failing={names_failing}"
        )

    # --- Scenario D: missing EXPERIMENTS.md altogether -------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        # Build the bundle but DELETE the EXPERIMENTS.md the helper auto-created
        _build_valid_bundle(bundle)
        (bundle.parent / "EXPERIMENTS.md").unlink()

        result_d = preflight(bundle)
        _print_checks("Scenario D (no EXPERIMENTS.md)", result_d)

        assert result_d["passes"] is False, "Scenario D should NOT pass"
        names_failing = {c["name"] for c in result_d["checks"] if c["status"] == "fail"}
        assert "experiments_md_has_rung_climb_attempt" in names_failing, (
            "Scenario D: rung-climb check should fail when EXPERIMENTS.md is missing; "
            f"got failing={names_failing}"
        )

    print("\n[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
