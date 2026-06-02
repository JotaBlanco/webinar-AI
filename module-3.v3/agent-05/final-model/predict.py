"""Shipped model: V1 + per-platform additive yaw-rate bias correction.

This is a thin shim that imports the v1-debiased candidate. See
`models/v1-debiased/notes.md` for the formulation and
`models/v1-debiased/assessment.md` for the dev scores.

Allowlist compliance: reads only the canonical 8 columns through `predict_v1`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Resolve repo root so we can import code.v1_baseline regardless of CWD.
_BUNDLE = Path(__file__).resolve().parent
_ROOT = _BUNDLE.parent
_CODE = _ROOT / "code"
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from v1_baseline import predict_v1  # noqa: E402


# Per-platform additive yaw-rate bias (rad/s). Fit by grid scan against the
# local dev set, minimising normalised (yaw_rmse + cte_rmse) vs V1.
YAW_BIAS_BY_PLATFORM = {
    "FORD_F_150_LIGHTNING_MK1": -0.00012,
    "FORD_MUSTANG_MACH_E_MK1": +0.00213,
    "HYUNDAI_IONIQ_5": +0.00112,
    # TESLA_MODEL_3: not listed -> 0 (V0 passthrough; no truth channel).
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """V1 yaw-rate prediction plus a per-platform constant bias correction."""
    out = predict_v1(sim_df, platform).copy()
    b = YAW_BIAS_BY_PLATFORM.get(platform, 0.0)
    if b != 0.0:
        out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"].to_numpy() + b
    return out
