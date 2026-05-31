"""Lateral-fidelity model — linear bicycle with understeer gradient, per-platform
steering-channel scale, gyro bias, and first-order yaw lag.

Steady-state yaw rate (linear bicycle with understeer coefficient K):

    yr_ss(t) = v * (s * delta_road) / (L + K * v^2) + bias

where
    - L is the wheelbase (per platform),
    - s is a steering-channel scale (corrects for steering-ratio mis-calibration
      between delta_wheel and delta_road),
    - K is the understeer-gradient coefficient in the velocity-squared term,
    - bias absorbs a small gyro / wheel-offset constant.

The driven yaw rate is the steady-state value passed through a first-order lag
(time-constant tau) plus an integer sample delay d (typically 0-1 samples on
this 50 Hz data) that captures rack + tyre lateral compliance:

    delayed_ss[i] = yr_ss[i - d]    (clamped at the start)
    yr[i]         = (1 - a) * yr[i-1] + a * delayed_ss[i-1],  a = dt / (tau + dt)

This recovers ~48 % of yaw-rate RMSE and ~33 % of CTE RMSE versus the V0
kinematic single-track baseline on the Ford segments.

x / y outputs are integrated identically to the canonical CTE pipeline
(`_shared/traj_metrics.py`) using measured v and the predicted yaw rate.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import lfilter

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open() as _fh:
    _COEFFS = json.load(_fh)

# Wheelbase per platform — openpilot-canonical (carParams).
_L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}

# Sample period of the sim data (50 Hz). Predict still handles non-uniform t.
_DT_NOMINAL = 0.02


def _lag_apply(u: np.ndarray, dt: float, tau: float) -> np.ndarray:
    """First-order lag with uniform-dt assumption. y[0] = u[0]."""
    if tau <= 1e-6:
        return u.astype(float).copy()
    a = dt / (tau + dt)
    b_coef = [0.0, a]
    a_coef = [1.0, -(1.0 - a)]
    zi = np.array([u[0] * (1.0 - a)])
    y, _ = lfilter(b_coef, a_coef, u, zi=zi)
    return y


def _apply_delay(u: np.ndarray, d: int) -> np.ndarray:
    if d <= 0:
        return u
    out = np.empty_like(u)
    out[:d] = u[0]
    out[d:] = u[:-d]
    return out


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Match _shared/traj_metrics.integrate_trajectory: start (0,0,0)."""
    n = len(t)
    if n < 2:
        z = np.zeros(n)
        return z, z
    dt = np.diff(t)
    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n)
    x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y = np.empty(n)
    y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index with columns
    yaw_rate_pred_rads (required), x_m, y_m (optional but provided).
    """
    if platform not in _COEFFS or platform not in _L_BY_PLATFORM:
        raise ValueError(f"unsupported platform: {platform!r}")

    c = _COEFFS[platform]
    L = _L_BY_PLATFORM[platform]

    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    # Steady-state yaw with understeer + steering-scale + bias.
    yr_ss = v * (c["s"] * delta) / (L + c["K"] * v * v) + c["bias"]
    yr_ss = _apply_delay(yr_ss, int(c.get("delay", 0)))
    # Use median dt for the lag (data is 50 Hz; non-uniform handled by lag insensitive to small jitter).
    if len(t) >= 2:
        dt = float(np.median(np.diff(t)))
        if not np.isfinite(dt) or dt <= 0:
            dt = _DT_NOMINAL
    else:
        dt = _DT_NOMINAL
    yr = _lag_apply(yr_ss, dt, float(c["tau"]))

    x, y = _integrate_xy(t, v, yr)

    out = pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
    return out
