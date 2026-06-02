"""V3 predict: V2 + per-platform additive residual correction.

Form: yr_v3 = yr_v2 + a_ay * (v * yr_v2) + b
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

_THIS = Path(__file__).resolve()
COEFFS = json.loads((_THIS.parent / "v2_coeffs.json").read_text())
CORR   = json.loads((_THIS.parent / "v3_correction.json").read_text())


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in COEFFS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = COEFFS[platform]
    if p["use_per_segment_delta0"]:
        d0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        d0 = p["delta0"]
    delta = (sim_df["delta_road_rad"].to_numpy() - d0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    # Apply V3 correction
    c = CORR.get(platform)
    if c is not None:
        yr = yr + c["a_ay"] * (v * yr) + c["b"]
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
