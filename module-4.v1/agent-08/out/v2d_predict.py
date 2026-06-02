"""V2d: V2c + conservative per-segment yaw bias correction.

When a segment has many low-yaw / low-steer samples, we can refine the constant offset.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

_GB_PATH = ROOT / "out" / "gain_bias.json"
with open(_GB_PATH) as f:
    GAIN_BIAS = json.load(f)


def _segment_extra_offset(yr_v1_after_gb: np.ndarray, v: np.ndarray, dr: np.ndarray,
                          v_thresh: float = 8.0, yr_thresh: float = 0.005,
                          dr_thresh: float = 0.005, min_n: int = 200,
                          shrink: float = 0.5, clamp: float = 0.002) -> float:
    """Estimate an additional per-segment offset from yr_v1 in 'straight' windows.
    Conservative: shrink and clamp so it can only help."""
    mask = (np.abs(yr_v1_after_gb) < yr_thresh) & (v > v_thresh) & (np.abs(dr) < dr_thresh)
    if int(mask.sum()) < min_n:
        return 0.0
    m = float(np.median(yr_v1_after_gb[mask]))
    m *= shrink
    if m > clamp: m = clamp
    if m < -clamp: m = -clamp
    return m


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy(float)
    gb = GAIN_BIAS.get(platform, {"gain": 1.0, "offset": 0.0})
    yr = gb["gain"] * yr_v1 + gb["offset"]
    if platform == "TESLA_MODEL_3":
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    v = sim_df["v_mps"].to_numpy(float)
    dr = sim_df["delta_road_rad"].to_numpy(float)
    extra = _segment_extra_offset(yr, v, dr)
    yr = yr - extra
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
