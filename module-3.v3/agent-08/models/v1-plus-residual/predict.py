"""V1 + linear residual correction.

`predict(sim_df, platform) -> DataFrame[yaw_rate_pred_rads]`

The residual is a per-platform linear regression on a small set of
allowlist-only features designed to capture transient (`ddelta`), platform
bias (intercept), and high-`|a_lat|` curvature terms that V1 misses.

Reads coeffs.json next to this file. Falls through to V1 for unknown platforms.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402

with open(_HERE / "coeffs.json") as fh:
    _COEFFS = json.load(fh)

FEATURE_NAMES = [
    "bias","delta_road","v","v_delta","ddelta","v_ddelta",
    "v0_yaw","abs_v0_yaw","a_long","v_sq_delta",
]

def _features(sim_df: pd.DataFrame) -> np.ndarray:
    t = sim_df["t_s"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    a_long = sim_df["a_long_mps2"].to_numpy(dtype=float) if "a_long_mps2" in sim_df.columns else np.zeros_like(t)
    v0_yaw = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    if len(t) > 1:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)
    return np.column_stack([
        np.ones_like(t), delta, v, v * delta, ddelta, v * ddelta,
        v0_yaw, np.abs(v0_yaw), a_long, v * v * delta,
    ])

def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
    if platform not in _COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": v1}, index=sim_df.index)
    beta = np.asarray(_COEFFS[platform]["beta"], dtype=float)
    X = _features(sim_df)
    correction = X @ beta
    return pd.DataFrame({"yaw_rate_pred_rads": v1 + correction}, index=sim_df.index)
