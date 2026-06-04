"""Lateral-fidelity prediction (V1).

V0 baseline is the kinematic single-track yaw rate `(v/L)·tan(delta_road)`.

V1 fits a steady-state understeer correction per platform:

    ψ̇ = v · δ / (L_eff + K_us · v²)

Coefficients per platform are stored in `coeffs.json`, fit on
`data/sim/segments/*` (truth column `yaw_rate_meas_rads`).

Trajectory (x, y) is integrated from the corrected ψ̇ and the *measured*
longitudinal speed `v_mps`, starting from the origin with heading 0.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json") as f:
    _COEFFS = json.load(f)

# Fallback defaults if an unseen platform shows up.
_DEFAULTS = dict(L=2.9, L_eff=2.9, K_us=0.003)


def _platform_coeffs(platform: str) -> dict:
    if platform in _COEFFS:
        return _COEFFS[platform]
    return dict(L=_DEFAULTS["L"], best="M2_understeer",
                m2=dict(L_eff=_DEFAULTS["L_eff"], K_us=_DEFAULTS["K_us"]))


def _yaw_rate(v: np.ndarray, delta: np.ndarray, coef: dict) -> np.ndarray:
    """Apply the per-platform V1 yaw-rate model."""
    L_eff = float(coef["m2"]["L_eff"])
    K_us = float(coef["m2"]["K_us"])
    denom = L_eff + K_us * v * v
    # Avoid division-by-zero blowups at standstill.
    denom = np.where(np.abs(denom) < 1e-6, 1e-6, denom)
    return v * delta / denom


def _integrate_xy(t: np.ndarray, v: np.ndarray, psi_dot: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Integrate (x, y) from yaw rate and measured speed.

    Uses midpoint heading to reduce trapezoid bias on curved arcs.
    """
    N = len(t)
    dt = np.diff(t, prepend=t[0])
    # Heading via cumulative trapezoid on yaw rate.
    psi = np.zeros(N)
    if N > 1:
        psi[1:] = np.cumsum(0.5 * (psi_dot[:-1] + psi_dot[1:]) * (t[1:] - t[:-1]))
    # Position: integrate v·(cos psi, sin psi) using midpoint psi.
    x = np.zeros(N)
    y = np.zeros(N)
    if N > 1:
        psi_mid = 0.5 * (psi[:-1] + psi[1:])
        v_mid = 0.5 * (v[:-1] + v[1:])
        dt_s = t[1:] - t[:-1]
        dx = v_mid * np.cos(psi_mid) * dt_s
        dy = v_mid * np.sin(psi_mid) * dt_s
        x[1:] = np.cumsum(dx)
        y[1:] = np.cumsum(dy)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate and trajectory.

    Inputs (from sim_df, sim-only contract):
        t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
        accel_pedal_pct, brake_pressed, yaw_rate_pred_rads
    """
    coef = _platform_coeffs(platform)
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    psi_dot = _yaw_rate(v, delta, coef)
    x, y = _integrate_xy(t, v, psi_dot)

    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": psi_dot,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
    return out
