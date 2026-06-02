"""Lead-compensator variant of V1: yaw_ss is fed a (delta + K_d * d_delta/dt) input.

predict(sim_df, platform) -> DataFrame aligned with sim_df.index.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS = json.loads((_HERE / "coeffs.json").read_text())


def _per_segment_delta0(df, fallback, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in _COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)
    c = _COEFFS[platform]
    if c["use_per_segment_delta0"]:
        d0 = _per_segment_delta0(sim_df, c["delta0_fallback"])
    else:
        d0 = c["delta0_fallback"]
    t = sim_df["t_s"].to_numpy()
    delta_raw = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    d_delta = np.gradient(delta_raw, t) if len(t) > 1 else np.zeros_like(delta_raw)
    delta_eff = ((delta_raw - d0) + c["K_d"] * d_delta) * c["g"]
    yr_ss = v * delta_eff / (c["L_eff"] + c["K_us"] * v * v)
    dt = np.diff(t, prepend=t[0])
    tau = c["tau"]
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
