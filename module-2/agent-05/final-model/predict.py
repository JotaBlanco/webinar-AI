"""Final model — per-platform kinematic-bicycle + understeer + steering-rate lead.

For each non-Tesla platform we predict:

    delta_eff = delta_road_rad + tau * d(delta_road_rad)/dt
    yaw_rate  = v_mps * tan(delta_eff) / (L_eff + K_us * v_mps**2) + bias

Tesla is a V0 passthrough — its sim.csv has no independent truth channel
(psi_dot_rads IS the V0 KS output), so any deviation increases RMSE.

Coefficients live in coeffs.json next to this file.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
_COEFFS: dict | None = None


def _load_coeffs() -> dict:
    global _COEFFS
    if _COEFFS is None:
        _COEFFS = json.loads(_COEFFS_PATH.read_text())
    return _COEFFS


def _predict_yaw(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
    coeffs = _load_coeffs().get(platform)

    v0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    if coeffs is None or platform == "TESLA_MODEL_3":
        # Unknown platform → passthrough V0.
        return v0

    L_eff = float(coeffs.get("L_eff", 3.0))
    K_us  = float(coeffs.get("K_us",  0.0))
    tau   = float(coeffs.get("tau",   0.0))
    bias  = float(coeffs.get("bias",  0.0))

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)

    if len(t) >= 2:
        d_dot = np.gradient(d, t)
    else:
        d_dot = np.zeros_like(d)

    d_eff = d + tau * d_dot
    num   = v * np.tan(d_eff)
    den   = L_eff + K_us * v * v
    return num / den + bias


def _integrate_trajectory(t: np.ndarray, v: np.ndarray, yaw_rate: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Integrate (v, yaw_rate) into (x, y) by trapezoidal rule with cumulative heading."""
    n = len(t)
    if n == 0:
        return np.zeros(0), np.zeros(0)
    dt = np.diff(t)
    # cumulative heading via trapezoid: psi[k+1] = psi[k] + 0.5*(yr[k]+yr[k+1])*dt
    psi = np.zeros(n)
    psi[1:] = np.cumsum(0.5 * (yaw_rate[:-1] + yaw_rate[1:]) * dt)
    # position via trapezoid on (v*cos psi, v*sin psi)
    cos_psi = np.cos(psi)
    sin_psi = np.sin(psi)
    vx = v * cos_psi
    vy = v * sin_psi
    x = np.zeros(n)
    y = np.zeros(n)
    x[1:] = np.cumsum(0.5 * (vx[:-1] + vx[1:]) * dt)
    y[1:] = np.cumsum(0.5 * (vy[:-1] + vy[1:]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame with `yaw_rate_pred_rads`, `x_m`, `y_m`, aligned to sim_df.index."""
    yr = _predict_yaw(sim_df, platform)
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    x, y = _integrate_trajectory(t, v, yr)
    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yr,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    return out
