"""V2 predict — refit coefficients of V1 shape + a small per-platform yaw-bias correction.

Same shape as V1: steady-state understeer + first-order lag + (optionally
per-segment) delta0 calibration. The Mustang/Hyundai CTE warnings in V1 come
from a small but systematic yaw-rate bias; correcting that bias directly is
exactly the right move for CTE, which is a double-integral of yaw error.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "v2_coeffs.json"
with open(_COEFFS_PATH) as _f:
    _BASE = json.load(_f)

# These yaw-bias corrections are fit to drive yaw_residual_mean to zero per
# platform. Sign convention: subtract from prediction.
YAW_BIAS_CORRECTION = {
    "FORD_F_150_LIGHTNING_MK1": -0.00021,
    "FORD_MUSTANG_MACH_E_MK1": -0.00144,
    "HYUNDAI_IONIQ_5": -0.00074,
}


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in _BASE:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = _BASE[platform]
    delta0 = (
        _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        if p["use_per_segment_delta0"]
        else p["delta0"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    yr = yr - YAW_BIAS_CORRECTION.get(platform, 0.0)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
