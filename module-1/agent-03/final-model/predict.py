"""Final lateral-fidelity model — Agent 03.

Per-platform corrected steady-state yaw-rate model:

    yaw_rate = a * (v/L) * tan(delta) / (1 + K * v^2) + b

Coefficients (a, K, b, L) fit per platform on a 70/30 train/held split of
Ford segments using L-BFGS / Nelder-Mead. Tesla has no measured-truth
yaw-rate column in the provided segments, so we pass through V0 (the
kinematic-single-track baseline) for that platform.

The predict() function also integrates yaw rate forward (Euler) with the
measured velocity to produce x_m, y_m for the cross-track-error KPI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent

with open(_HERE / "coeffs.json", "r") as _fh:
    _COEFFS = json.load(_fh)


def _correct_yaw_rate(v: np.ndarray, delta: np.ndarray, plat_coef: dict) -> np.ndarray:
    """Apply the per-platform corrected yaw-rate model."""
    a = plat_coef["a"]
    K = plat_coef["K"]
    b = plat_coef["b"]
    L = plat_coef["L"]
    y0 = (v / L) * np.tan(delta)
    return a * y0 / (1.0 + K * v * v) + b


def _integrate_trajectory(
    t: np.ndarray, v: np.ndarray, yaw_rate: np.ndarray,
    x0: float = 0.0, y0: float = 0.0, psi0: float = 0.0,
):
    """Integrate (x, y, psi) forward using trapezoidal rule.

    Heading psi from yaw_rate (trapz), then x/y from v*cos(psi), v*sin(psi)
    using midpoint velocity for stability.
    """
    n = len(t)
    psi = np.empty(n)
    x = np.empty(n)
    y = np.empty(n)
    psi[0] = psi0
    x[0] = x0
    y[0] = y0
    for k in range(n - 1):
        dt = t[k + 1] - t[k]
        # Trapezoidal integration of yaw rate
        psi[k + 1] = psi[k] + 0.5 * (yaw_rate[k] + yaw_rate[k + 1]) * dt
        # Trapezoidal integration of position using mean heading and mean speed
        psi_mid = 0.5 * (psi[k] + psi[k + 1])
        v_mid = 0.5 * (v[k] + v[k + 1])
        x[k + 1] = x[k] + v_mid * np.cos(psi_mid) * dt
        y[k + 1] = y[k] + v_mid * np.sin(psi_mid) * dt
    return x, y, psi


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict lateral behaviour for a single sim segment.

    Parameters
    ----------
    sim_df : pd.DataFrame
        Must contain columns: t_s, v_mps, delta_road_rad. Optional: x_m, y_m,
        psi_rad (for initial conditions — if absent, start at zero).
    platform : str
        One of the keys in coeffs.json.

    Returns
    -------
    pd.DataFrame
        Same index as sim_df, with columns:
          - yaw_rate_pred_rads (rad/s)
          - x_m, y_m (m) — integrated forward from the corrected yaw rate.
    """
    if platform not in _COEFFS:
        # Unknown platform: fall back to the bare KS baseline.
        plat_coef = {"a": 1.0, "K": 0.0, "b": 0.0, "L": 2.9}
    else:
        plat_coef = _COEFFS[platform]

    t = sim_df["t_s"].values.astype(float)
    v = sim_df["v_mps"].values.astype(float)
    delta = sim_df["delta_road_rad"].values.astype(float)

    yaw_rate = _correct_yaw_rate(v, delta, plat_coef)

    # Initial conditions from sim_df if available
    x0 = float(sim_df["x_m"].iloc[0]) if "x_m" in sim_df.columns else 0.0
    y0 = float(sim_df["y_m"].iloc[0]) if "y_m" in sim_df.columns else 0.0
    psi0 = float(sim_df["psi_rad"].iloc[0]) if "psi_rad" in sim_df.columns else 0.0

    x, y, _psi = _integrate_trajectory(t, v, yaw_rate, x0=x0, y0=y0, psi0=psi0)

    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yaw_rate,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    return out
