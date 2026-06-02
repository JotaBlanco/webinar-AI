"""Final predict() — understeer-corrected bicycle with calibrated steering offset
and first-order yaw lag.

Operating contract (per task statement):
- Reads only allow-listed columns from the sim-only schema:
    t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
    accel_pedal_pct, brake_pressed, yaw_rate_pred_rads.
- Returns DataFrame indexed to sim_df.index with columns:
    yaw_rate_pred_rads  (required)
    x_m, y_m            (integrated from yaw rate + measured v)

Model:
    delta_eff[k] = (delta_road_rad[k] + delta_offset) * scale
    yr_ss[k]     = v[k] * delta_eff[k] / (L + K_us * v[k]^2)        (steady-state)
    yr[k+1]      = yr[k] + dt[k] * (yr_ss[k] - yr[k]) / tau         (first-order lag)

For TESLA_MODEL_3 the training data is effectively V0-clean (psi_dot_rads in the
training file is the KS state, not a real measurement), so the model degrades to
V0 pass-through (K_us = scale - 1 = delta_offset = tau = 0).

Coefficients are per-platform; see coeffs.json beside this file.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS = json.loads((_HERE / "coeffs.json").read_text())

# Fallback wheelbase if a platform shows up that we did not calibrate against.
_FALLBACK_L = 3.0


def _params(platform: str) -> dict:
    if platform in _COEFFS:
        return _COEFFS[platform]
    return {
        "K_us": 0.0, "scale": 1.0, "delta_offset_rad": 0.0,
        "tau_s": 0.0, "L": _FALLBACK_L,
    }


def _predict_yaw_rate(t: np.ndarray, v: np.ndarray, d: np.ndarray,
                      K_us: float, scale: float, do: float, tau: float,
                      L: float) -> np.ndarray:
    d_eff = (d + do) * scale
    # Avoid division by zero at v ≈ 0; the contribution is negligible anyway.
    denom = L + K_us * v * v
    yr_ss = np.where(denom > 1e-6, v * d_eff / denom, 0.0)
    if tau <= 1e-4 or len(t) < 2:
        return yr_ss
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    dt = np.diff(t)
    # Clamp pathological dt's.
    dt = np.clip(dt, 1e-4, 1.0)
    for i in range(len(t) - 1):
        yr[i + 1] = yr[i] + dt[i] * (yr_ss[i] - yr[i]) / tau
    return yr


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Euler integration matching the canonical metric integrator:
        psi[i+1] = psi[i] + yr[i] * dt[i]
        x[i+1]   = x[i] + v[i] * cos(psi[i]) * dt[i]
        y[i+1]   = y[i] + v[i] * sin(psi[i]) * dt[i]
    All trajectories start at (0, 0, 0).
    """
    n = len(t)
    x = np.zeros(n)
    y = np.zeros(n)
    if n < 2:
        return x, y
    dt = np.diff(t)
    dt = np.clip(dt, 1e-4, 1.0)
    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame with the same index as sim_df.

    Required output columns:
        yaw_rate_pred_rads  — yaw rate per row [rad/s]
        x_m, y_m            — trajectory integrated from the prediction
    """
    p = _params(platform)
    K_us = p["K_us"]; scale = p["scale"]; do = p["delta_offset_rad"]
    tau = p["tau_s"]; L = p["L"]

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)

    yr = _predict_yaw_rate(t, v, d, K_us, scale, do, tau, L)
    x, y = _integrate_xy(t, v, yr)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=sim_df.index,
    )


__all__ = ["predict"]
