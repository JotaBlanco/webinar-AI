"""V1 + per-platform constant yaw-rate bias correction.

Formulation
-----------
    yr_hat = predict_v1(sim_df, platform) + b_platform

where b_platform is a single scalar per platform, fit on the local dev set to
jointly improve pooled yaw_rate_rmse and pooled cte_rmse against V1.

Structurally this is a degenerate residual learner with one feature: the
constant function. It attacks the per-platform signed CTE drift that V1
leaves on the table (Mach-E -22 m, IONIQ-5 -12 m). A small persistent yaw
bias integrates linearly with distance into a large signed CTE; removing
that bias is the highest-leverage move on this metric.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_CODE = Path(__file__).resolve().parents[2] / "code"
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from v1_baseline import predict_v1  # noqa: E402


YAW_BIAS_BY_PLATFORM = {
    "FORD_F_150_LIGHTNING_MK1": -0.00012,
    "FORD_MUSTANG_MACH_E_MK1": +0.00213,
    "HYUNDAI_IONIQ_5": +0.00112,
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = predict_v1(sim_df, platform).copy()
    b = YAW_BIAS_BY_PLATFORM.get(platform, 0.0)
    if b != 0.0:
        out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"].to_numpy() + b
    return out
