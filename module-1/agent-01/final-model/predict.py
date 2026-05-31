"""V1 lateral model — understeer-corrected bicycle with steering lag.

Yaw-rate model (per platform):

    psi_dot_hat(t) = v(t) * (a * delta_lagged(t) + b) / (L_eff + K * v(t)^2)

where:
  - delta_lagged is `delta_road_rad` shifted by `lag` samples (forward),
    representing actuator/tyre lag relative to the steering input.
  - L_eff, K, a, b, lag are fit per platform on data/sim/segments/ truth
    (yaw_rate_meas_rads) using Nelder-Mead least squares, masking v < 1 m/s.

Trajectory:
  - Integrate heading psi from yaw_rate via cumulative trapezoid (dt from t_s).
  - x, y = cumulative trapezoid of v*cos(psi), v*sin(psi). Origin at first sample.

Tesla: no truth in sim/, so coeffs use openpilot-canonical L and a=1, b=0, lag=0,
       with K = mean of the three fitted platforms (best-available prior).

Contract: reads only the 8 sim-only columns. Does NOT read yaw_rate_meas_rads.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

_COEFS_PATH = Path(__file__).resolve().parent / "coefs.json"
with open(_COEFS_PATH) as _f:
    _COEFS = json.load(_f)

# Fallback for any unknown platform: use Ioniq-like defaults (mid-size BEV).
_DEFAULT = {
    "lag": 3,
    "params": [2.9, 0.0033, 0.95, 0.0],
}


def _apply_lag(arr: np.ndarray, n: int) -> np.ndarray:
    if n <= 0:
        return arr
    out = np.empty_like(arr)
    out[:n] = arr[0]
    out[n:] = arr[:-n]
    return out


def _cumtrapz(y: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Cumulative trapezoid, output length == input length, starting at 0."""
    out = np.zeros_like(y)
    if len(y) < 2:
        return out
    dt = np.diff(t)
    out[1:] = np.cumsum(0.5 * (y[1:] + y[:-1]) * dt)
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw-rate and trajectory from input-only sim_df.

    sim_df columns expected (sim-only contract):
      t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
      accel_pedal_pct, brake_pressed, yaw_rate_pred_rads  (V0 baseline; ignored)

    Returns a DataFrame aligned to sim_df.index with columns:
      yaw_rate_pred_rads, x_m, y_m
    """
    cfg = _COEFS.get(platform, _DEFAULT)
    lag = int(cfg["lag"])
    L, K, a, b = [float(v) for v in cfg["params"]]

    t = sim_df["t_s"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    delta_lag = _apply_lag(delta, lag)

    denom = L + K * v * v
    # Avoid pathological denom (always positive for K>=0, L>0, v>=0; safe).
    yaw_rate = v * (a * delta_lag + b) / denom

    # Integrate trajectory in world frame, origin (0,0,0).
    psi = _cumtrapz(yaw_rate, t)
    vx = v * np.cos(psi)
    vy = v * np.sin(psi)
    x = _cumtrapz(vx, t)
    y = _cumtrapz(vy, t)

    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yaw_rate,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    return out
