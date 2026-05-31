"""V2 predictor for evaluation (sits in work/, not shipped yet)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).resolve().parents[1] / "final-model" / "coeffs_v2.json"
with _COEFFS_PATH.open("r") as _fh:
    _COEFFS = json.load(_fh)


def _predict_yaw(t, v, delta, c):
    g0 = float(c["g0"]); g1 = float(c["g1"])
    d0 = float(c["delta_offset"]); K_us = float(c["K_us"])
    tau = float(c["tau"]); L = float(c["L"])
    g_eff = g0 + g1 * np.abs(delta)
    delta_eff = g_eff * delta + d0
    yr_ss = v * delta_eff / (L + K_us * v * v)
    n = len(t)
    if n == 0:
        return np.zeros(0)
    if n == 1 or tau <= 1e-6:
        return yr_ss.copy()
    dt = np.diff(t)
    alpha = np.where(dt > 0, dt / (tau + dt), 1.0)
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    for k in range(1, n):
        yr[k] = (1.0 - alpha[k - 1]) * yr[k - 1] + alpha[k - 1] * yr_ss[k]
    return yr


def predict(sim_df, platform):
    idx = sim_df.index
    if platform not in _COEFFS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)},
            index=idx,
        )
    c = _COEFFS[platform]
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    if np.isnan(v).any():
        v = pd.Series(v).ffill().bfill().fillna(0.0).to_numpy()
    if np.isnan(delta).any():
        delta = pd.Series(delta).ffill().bfill().fillna(0.0).to_numpy()
    yr = _predict_yaw(t, v, delta, c)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=idx)
