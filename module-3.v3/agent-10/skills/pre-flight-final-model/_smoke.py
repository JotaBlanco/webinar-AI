"""Smoke test for pre-flight-final-model (m3.v3).

Builds bundles in a tmp dir and checks the new m3.v3 gates fire as expected:
- Scenario A: valid bundle with alternatives header + MODELS.md -> passes.
- Scenario B: predict.py removed -> fails on predict_py_present.
- Scenario C: EXPERIMENTS.md lacks the "Alternatives considered" header -> fails.
- Scenario D: EXPERIMENTS.md missing -> fails.
- Scenario E: MODELS.md has <3 candidates -> fails.
- Scenario F: shipped predict identical to V1 -> warn (still passes).

Run standalone: ``python3 _smoke.py`` (from this directory).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preflight import preflight  # noqa: E402


PREDICT_PY_STRUCTURAL = '''\
"""Stub structurally-different model: V0 passthrough with a constant offset.
Differs from V1 by more than the diff tolerance — enough to clear the warn."""
import pandas as pd

def predict(sim_df, platform):
    yr = sim_df["yaw_rate_pred_rads"].to_numpy() + 0.01
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
'''

PREDICT_PY_V1_PASSTHROUGH = '''\
"""V1 passthrough — should trigger the differs-from-V1 warn."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))
from v1_baseline import predict_v1

def predict(sim_df, platform):
    return predict_v1(sim_df, platform)
'''

MANIFEST = {
    "platform_support": ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"],
    "predict_callable": "predict.py:predict",
}

REPORT_BODY = (
    "# Placeholder report\n\n"
    "Stub REPORT.md used by the pre-flight smoke test. Exists to clear the "
    ">= 100 byte size check; real reports should explain method, validation, "
    "and known limitations.\n"
)

EXPERIMENTS_WITH_ALTERNATIVES = """\
# EXPERIMENTS.md

## Alternatives considered

- (structure) Linear dynamic single-track with slip angles — attack transient regime
- (structure) Regime-switched model: V1 on straight, dynamic on transient
- (structure) Residual learner on V1 residual with d(delta)/dt feature
- Polynomial steering scale refinement of V1 — coefficient-only refit
- (orthogonal) Multi-seed fold averaging on V1

## E00 — V1 baseline
- Result (dev): yaw 0.00587; CTE 56.81.

## E01 — Rung-1 dynamic single-track attempt
- Hypothesis: transient regime carries the largest residual.
- Result (dev): yaw 0.0108 (-25%); CTE 122 (-16%).
- Verdict: lost to V1 (under-parameterised).
"""

EXPERIMENTS_NO_ALTERNATIVES_HEADER = """\
# EXPERIMENTS.md

## E00 — V1 baseline
- Result (dev): yaw 0.00587; CTE 56.81.

## E01 — refit
- Result (dev): yaw 0.0083; CTE 99.
"""

MODELS_MD = """\
# MODELS.md

Registry of candidate models attempted this run.

## dynamic-single-track-v1
- dir: models/dynamic-single-track-v1/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.0108
- pooled-cte-rmse-dev: 122.0
- verdict: lost to V1 (under-parameterised at openpilot priors)

## v1-polynomial-g
- dir: models/v1-polynomial-g/
- structure: refines-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.00580
- pooled-cte-rmse-dev: 56.4
- verdict: marginal; within run-to-run noise

## v1-plus-residual-learner
- dir: models/v1-plus-residual-learner/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.00420
- pooled-cte-rmse-dev: 47.2
- verdict: SHIPPED — V1 + small per-segment correction beat V1 on dev
"""

MODELS_MD_ONE_ENTRY = """\
# MODELS.md

## only-candidate
- structure: differs-from-v1
- verdict: nope
"""


def _build_valid_bundle(d: Path, *, predict_py: str = PREDICT_PY_STRUCTURAL,
                        experiments: str = EXPERIMENTS_WITH_ALTERNATIVES,
                        models: str = MODELS_MD) -> None:
    (d / "predict.py").write_text(predict_py)
    (d / "manifest.json").write_text(json.dumps(MANIFEST, indent=2))
    (d / "REPORT.md").write_text(REPORT_BODY)
    (d.parent / "EXPERIMENTS.md").write_text(experiments)
    (d.parent / "MODELS.md").write_text(models)


def _print_checks(label: str, result: dict) -> None:
    print(f"\n[smoke] === {label} ===")
    print(f"[smoke] passes = {result['passes']}")
    for c in result["checks"]:
        print(f"  - {c['status']:4s}  {c['name']:42s}  {c['detail']}")
    if result["errors"]:
        print("[smoke] errors:")
        for e in result["errors"]:
            print(f"    * {e}")


def main() -> int:
    repo_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/")
    os.chdir(repo_root)

    # --- Scenario A: valid -----------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle)
        result = preflight(bundle)
        _print_checks("A (valid)", result)
        assert result["passes"] is True, f"A should pass; errors={result['errors']}"

    # --- Scenario B: broken (no predict.py) ------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle)
        (bundle / "predict.py").unlink()
        result = preflight(bundle)
        _print_checks("B (no predict.py)", result)
        failing = {c["name"] for c in result["checks"] if c["status"] == "fail"}
        assert result["passes"] is False
        assert "predict_py_present" in failing, failing

    # --- Scenario C: EXPERIMENTS.md missing alternatives header ----------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle, experiments=EXPERIMENTS_NO_ALTERNATIVES_HEADER)
        result = preflight(bundle)
        _print_checks("C (no alternatives header)", result)
        failing = {c["name"] for c in result["checks"] if c["status"] == "fail"}
        assert result["passes"] is False
        assert "experiments_md_has_alternatives_header" in failing, failing

    # --- Scenario D: EXPERIMENTS.md missing -----------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle)
        (bundle.parent / "EXPERIMENTS.md").unlink()
        result = preflight(bundle)
        _print_checks("D (no EXPERIMENTS.md)", result)
        failing = {c["name"] for c in result["checks"] if c["status"] == "fail"}
        assert result["passes"] is False
        assert "experiments_md_has_alternatives_header" in failing, failing

    # --- Scenario E: MODELS.md has fewer than 3 entries ------------------------
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle, models=MODELS_MD_ONE_ENTRY)
        result = preflight(bundle)
        _print_checks("E (MODELS.md one entry)", result)
        failing = {c["name"] for c in result["checks"] if c["status"] == "fail"}
        assert result["passes"] is False
        assert "models_md_has_three_candidates" in failing, failing

    # --- Scenario F: shipped predict identical to V1 -> warn (still passes) ---
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "final-model"
        bundle.mkdir()
        _build_valid_bundle(bundle, predict_py=PREDICT_PY_V1_PASSTHROUGH)
        result = preflight(bundle)
        _print_checks("F (V1 passthrough -> warn)", result)
        statuses = {c["name"]: c["status"] for c in result["checks"]}
        assert statuses["predict_differs_structurally_from_v1"] == "warn", (
            f"F should warn on structural-novelty; got {statuses['predict_differs_structurally_from_v1']}"
        )
        assert result["passes"] is True, f"F warn should still pass; errors={result['errors']}"

    print("\n[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
