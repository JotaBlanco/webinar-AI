"""Smoke test for assess-candidate-model.

Builds a stub candidate (V0 passthrough with small offset) in a tmp dir,
runs assess() against a tiny segment-paths subset, asserts assessment.md
was written and contains the expected sections.

Run from repo root: `python3 module-3.v3/agent-01/skills/assess-candidate-model/_smoke.py`.
"""

from __future__ import annotations

import os
import sys
import tempfile
from glob import glob
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

REPO_ROOT = HERE.parents[3]
os.chdir(REPO_ROOT)

from assess import assess  # noqa: E402


STUB_PREDICT = '''\
"""Stub: V0 passthrough + 0.001 rad/s offset (structurally trivial, loses to V1)."""
import pandas as pd

def predict(sim_df, platform):
    yr = sim_df["yaw_rate_pred_rads"].to_numpy() + 0.001
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
'''


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        model_dir = Path(tmp) / "stub-candidate"
        model_dir.mkdir()
        (model_dir / "predict.py").write_text(STUB_PREDICT)

        # Restrict to a handful of segments to keep smoke fast.
        sample_paths = sorted(
            glob("data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv", recursive=True)
        )[:5]
        if not sample_paths:
            print("[smoke] SKIP — no sample segments under data/sim/")
            return 0

        result = assess(model_dir, segment_paths=sample_paths)
        ass_path = Path(result["assessment_path"])

        assert ass_path.exists(), "assessment.md should exist"
        body = ass_path.read_text(encoding="utf-8")
        for expected in (
            "Headline (pooled, candidate vs V1)",
            "Per-platform vs V1",
            "Top CTE improvements",
            "Top CTE regressions",
            "Residual-structure verdict",
            "Verdict",
            "Model-class-specific diagnostics",
        ):
            assert expected in body, f"assessment.md missing section: {expected}"

        # Stub loses to V1 — sanity check that the assessment captured that.
        delta_yaw = result["vs_v1"]["delta_yaw_pct"]
        delta_cte = result["vs_v1"]["delta_cte_pct"]
        print(f"[smoke] candidate vs V1: Δyaw={delta_yaw:+.2f}% Δcte={delta_cte:+.2f}%")
        print(f"[smoke] assessment.md head:\n{body[:300]}")
        print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
