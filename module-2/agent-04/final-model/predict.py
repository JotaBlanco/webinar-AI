"""Lateral-fidelity predictor — per-platform steady-state bicycle with a small
first-order yaw-rate lag.

Predicted yaw rate at each sample:

    delta_eff = delta_road_rad - delta_offset
    yr_ss     = v * delta_eff / (L_eff + K_us * v^2)
    yr[i+1]   = yr[i] + min(1, dt[i]/tau) * (yr_ss[i] - yr[i])         (tau>0)

Coefficients (L_eff, K_us, delta_offset, tau) are fit per platform from a 70%
train split of the Ford segments under data/sim/segments/. See REPORT.md.

If a platform is unknown, the function falls back to the V0 prediction
already present in the input sim_df.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFF_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFF_PATH.open("r", encoding="utf-8") as _fh:
    _COEFFS = json.load(_fh)


def _predict_yaw_rate(t: np.ndarray, v: np.ndarray, delta: np.ndarray, coef: dict) -> np.ndarray:
    """Steady-state bicycle yaw rate + first-order lag."""
    L = float(coef["L_eff_m"])
    K = float(coef["K_us"])
    d0 = float(coef.get("delta_offset_rad", 0.0))
    tau = float(coef.get("tau_s", 0.0))

    denom = L + K * (v * v)
    # numerical floor for denom to avoid blow-ups (denom always positive here)
    denom = np.where(denom > 1e-3, denom, 1e-3)
    yr_ss = v * (delta - d0) / denom

    if tau <= 1e-6 or len(yr_ss) < 2:
        return yr_ss

    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    for i in range(len(yr_ss) - 1):
        a = dt[i] / tau
        if a > 1.0:
            a = 1.0
        elif a < 0.0:
            a = 0.0
        y[i + 1] = y[i] + a * (yr_ss[i] - y[i])
    return y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for one segment.

    Parameters
    ----------
    sim_df : pd.DataFrame
        One segment's sim.csv. Must contain ``t_s``, ``v_mps``, ``delta_road_rad``.
        For unknown platforms the V0 column ``yaw_rate_pred_rads`` is passed through.
    platform : str
        One of ``FORD_F_150_LIGHTNING_MK1`` or ``FORD_MUSTANG_MACH_E_MK1`` for tuned
        prediction; any other value triggers V0 passthrough.

    Returns
    -------
    pd.DataFrame
        Indexed identically to ``sim_df``, with column ``yaw_rate_pred_rads``.
    """
    out = pd.DataFrame(index=sim_df.index)
    coef = _COEFFS.get(platform)
    if coef is None:
        if "yaw_rate_pred_rads" in sim_df.columns:
            out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
        else:
            # Last-ditch fallback: kinematic Ackermann with nominal L=3.0
            v = sim_df["v_mps"].to_numpy(float)
            d = sim_df["delta_road_rad"].to_numpy(float)
            out["yaw_rate_pred_rads"] = v * np.tan(d) / 3.0
        return out

    t = sim_df["t_s"].to_numpy(float)
    v = sim_df["v_mps"].to_numpy(float)
    delta = sim_df["delta_road_rad"].to_numpy(float)
    out["yaw_rate_pred_rads"] = _predict_yaw_rate(t, v, delta, coef)
    return out
