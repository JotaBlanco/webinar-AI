"""V1 + per-platform yaw-bias + steering-derivative correction.

Formulation
-----------
    yr_hat = predict_v1(sim_df, platform) + b_platform + k_dd_platform * d(delta_road)/dt

The k_dd term targets transient-regime error: when steering is rapidly changing,
real vehicle dynamics differ from V1's single-pole lag approximation. The
gradient of delta_road is a model-free proxy for the steering rate that lag is
trying to approximate.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
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

KDD_BY_PLATFORM = {
    "FORD_F_150_LIGHTNING_MK1": -0.010,
    "FORD_MUSTANG_MACH_E_MK1": -0.010,
    "HYUNDAI_IONIQ_5": 0.0,
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = predict_v1(sim_df, platform).copy()
    yr = out["yaw_rate_pred_rads"].to_numpy(dtype=float).copy()
    b = YAW_BIAS_BY_PLATFORM.get(platform, 0.0)
    k = KDD_BY_PLATFORM.get(platform, 0.0)
    yr = yr + b
    if k != 0.0 and "delta_road_rad" in sim_df.columns:
        t = sim_df["t_s"].to_numpy(dtype=float)
        d = sim_df["delta_road_rad"].to_numpy(dtype=float)
        if len(t) >= 2:
            dd = np.gradient(d, t)
            yr = yr + k * dd
    out["yaw_rate_pred_rads"] = yr
    return out
