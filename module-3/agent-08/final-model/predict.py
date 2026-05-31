"""Lateral-fidelity predict — refined kinematic single-track with
per-platform g / delta0 / K_us / tau / L_eff, plus first-order yaw lag.

Tesla: V0 passthrough (no ground-truth channel to fit against).

Coefficients fitted offline against pooled yaw-rate sum-of-squares
on `data/sim/segments/<platform>/**/sim.csv` using scipy.optimize
Nelder-Mead (see ../out/fit.py).

Operating contract: reads only columns present in sim-only/ schema
(t_s, delta_road_rad, v_mps, yaw_rate_pred_rads).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with open(_COEFFS_PATH) as _fh:
    COEFFS = json.load(_fh)


def _apply_lag(yr_ss: np.ndarray, dt: np.ndarray, tau: float) -> np.ndarray:
    """First-order lag y[i] = y[i-1] + alpha[i] * (yr_ss[i] - y[i-1])."""
    n = len(yr_ss)
    if n == 0:
        return yr_ss
    if tau <= 0:
        return yr_ss.copy()
    alpha = dt / (tau + dt)
    y = np.empty(n, dtype=float)
    y[0] = yr_ss[0]
    for i in range(1, n):
        y[i] = y[i-1] + alpha[i] * (yr_ss[i] - y[i-1])
    return y


def _predict_physics(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v     = sim_df["v_mps"].to_numpy(dtype=float)
    t     = sim_df["t_s"].to_numpy(dtype=float)

    delta_eff = (delta - p["delta0"]) * p["g"]
    yr_ss = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)

    if len(t) >= 2:
        dt = np.diff(t, prepend=t[0])
        # guard zero/negative dt
        dt = np.where(dt <= 0, np.median(np.diff(t)) if len(t) > 1 else 0.02, dt)
    else:
        dt = np.array([0.02])
    return _apply_lag(yr_ss, dt, p["tau"])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw_rate_pred_rads for the given segment.

    For Tesla (no truth channel), returns V0 passthrough so we don't
    drift from the baseline KS output on a platform where score-model
    treats baseline AS truth.
    """
    if platform not in COEFFS:
        return sim_df[["yaw_rate_pred_rads"]].copy()
    yr = _predict_physics(sim_df, COEFFS[platform])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
