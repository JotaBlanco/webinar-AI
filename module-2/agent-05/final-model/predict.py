"""Final lateral-fidelity model — agent-05 (V2).

Speed-known understeer-corrected bicycle with per-platform calibration AND a
first-order steering/tire lag, fitted on a 75/25 train/dev split.

Model:
    yr_raw[k] = g * v[k] * (delta[k] - delta0) / (L + K_us * v[k]^2)
    yr[k]     = lpf_tau(yr_raw)[k]              # first-order, dt-aware

Where per-platform (g, K_us, delta0, tau) are jointly fitted to minimise
sample-pooled yaw-rate MSE (v_mps > 2). g absorbs steering-ratio scale that
the carParams steerRatio misses; K_us captures speed-dependent understeer
that the pure KS model ignores; delta0 absorbs static toe/alignment bias;
tau lumps actuator + tire compliance lag.

Returns a DataFrame with `yaw_rate_pred_rads` (required) and `x_m`, `y_m`
(integrated trajectory) aligned with sim_df.index.

Robustness:
- Falls back to pure KS (g=1, K_us=0, delta0=0, tau=0) on unknown platforms.
- Handles short segments (n < 2) and non-monotone time stamps gracefully.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open() as _fh:
    _COEFFS = json.load(_fh)

_DEFAULT = {"L": 2.9, "g": 1.0, "K_us": 0.0, "delta0": 0.0, "tau": 0.0}


def _params(platform: str) -> dict:
    return _COEFFS.get(platform, _DEFAULT)


def _lpf_first_order(x: np.ndarray, dt: np.ndarray | float, tau: float) -> np.ndarray:
    """First-order LPF with per-step dt. y[k] = a*x[k] + (1-a)*y[k-1], a = dt/(tau+dt)."""
    if tau <= 0.0:
        return x.copy()
    n = len(x)
    y = np.empty(n)
    y[0] = x[0]
    if np.isscalar(dt):
        a = dt / (tau + dt)
        for k in range(1, n):
            y[k] = a * x[k] + (1.0 - a) * y[k - 1]
    else:
        # dt is length n-1
        for k in range(1, n):
            a = dt[k - 1] / (tau + dt[k - 1])
            y[k] = a * x[k] + (1.0 - a) * y[k - 1]
    return y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    p = _params(platform)
    L = float(p["L"])
    g = float(p["g"])
    K_us = float(p["K_us"])
    delta0 = float(p["delta0"])
    tau = float(p.get("tau", 0.0))

    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    n = len(v)
    denom = L + K_us * v * v
    yr_raw = g * v * (delta - delta0) / denom

    if n >= 2:
        dt_arr = np.diff(t)
        # If timestamps are bad, fall back to no filtering.
        if np.all(dt_arr > 0):
            yr = _lpf_first_order(yr_raw, dt_arr, tau)
        else:
            yr = yr_raw.copy()
    else:
        yr = yr_raw.copy()

    # Integrate trajectory (matches grader's integration convention).
    x = np.zeros(n)
    y = np.zeros(n)
    psi = np.zeros(n)
    if n >= 2:
        dt_arr = np.diff(t)
        if np.all(dt_arr > 0):
            psi[1:] = np.cumsum(yr[:-1] * dt_arr)
            x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt_arr)
            y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt_arr)

    return pd.DataFrame(
        {
            "yaw_rate_pred_rads": yr,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
