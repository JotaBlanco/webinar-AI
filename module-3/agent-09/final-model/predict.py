"""Lateral-fidelity predict — calibrated kinematic single-track + first-order yaw lag.

Per-platform coefficients in `coeffs.json`. Tesla falls back to identity
(echo V0 baseline) because the sim's truth channel for Tesla IS V0.

Model:
    delta_eff[i] = (delta_road_rad[i] - delta0) * g
    yr_ss[i]     = v[i] * delta_eff[i] / (L_eff + K_us * v[i]^2)
    yr[i+1]      = yr[i] + alpha[i] * (yr_ss[i] - yr[i])
    alpha[i]     = dt[i] / (tau + dt[i])
    yr[0]        = yr_ss[0]
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with _COEFFS_PATH.open() as _f:
    _COEFFS = json.load(_f)


def _model_yaw_rate(t, v, delta, L_eff, g, delta0, K_us, tau):
    delta_eff = (delta - delta0) * g
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)
    if len(t) < 2:
        return yr_ss.copy()
    dt = np.diff(t)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    if tau <= 0:
        yr[:] = yr_ss
        return yr
    # Vectorised first-order IIR — recursive, so loop:
    for i in range(len(dt)):
        a = dt[i] / (tau + dt[i])
        yr[i + 1] = yr[i] + a * (yr_ss[i] - yr[i])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)

    c = _COEFFS.get(platform)
    if c is None:
        # Unknown platform (incl. Tesla) — echo V0 baseline.
        if "yaw_rate_pred_rads" in sim_df.columns:
            out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
        else:
            out["yaw_rate_pred_rads"] = np.zeros(len(sim_df))
        return out

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    yr = _model_yaw_rate(
        t, v, delta,
        L_eff=c["L_eff"], g=c["g"], delta0=c["delta0"],
        K_us=c["K_us"], tau=c["tau"],
    )
    # Replace any NaNs (e.g. v==0 segments) with V0 fallback.
    if np.any(np.isnan(yr)):
        v0 = sim_df.get("yaw_rate_pred_rads")
        if v0 is not None:
            yr = np.where(np.isnan(yr), v0.to_numpy(dtype=float), yr)
        else:
            yr = np.nan_to_num(yr, nan=0.0)
    out["yaw_rate_pred_rads"] = yr
    return out
