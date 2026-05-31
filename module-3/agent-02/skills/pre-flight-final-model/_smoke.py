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


def _build_valid_bundle(d: Path) -> None:
    (d / "predict.py").write_text(PREDICT_PY)
    (d / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    (d / "REPORT.md").write_text(REPORT_BODY)


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

    print("\n[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
