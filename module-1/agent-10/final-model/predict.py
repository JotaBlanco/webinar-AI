"""V1 lateral-fidelity predict — steady-state bicycle with understeer gradient.

Model:
    delta_eff = LP1(delta_road_rad - d0; tau_steer)
    yaw_ss(t) = v * delta_eff / (L_eff + K_us * v^2)
    yaw(t)    = LP1(yaw_ss; tau_yaw)         (first-order lag)

Trajectory: integrate (yaw, v_meas) to (x_m, y_m) with trapezoidal/Euler scheme.

Per-platform coefficients live in coeffs.json (fit on data/sim/segments truth).
TESLA_MODEL_3 has no truth in the workshop dataset — fallback is to passthrough
the V0 KS prediction supplied as `yaw_rate_pred_rads` in the input.

Input schema (sim-only):
    t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
    accel_pedal_pct, brake_pressed, yaw_rate_pred_rads

Returns a DataFrame aligned with sim_df.index with at minimum:
    yaw_rate_pred_rads, x_m, y_m
"""
from __future__ import annotations

import json
import os
from typing import Dict, Any

import numpy as np
import pandas as pd

_COEFFS_PATH = os.path.join(os.path.dirname(__file__), "coeffs.json")
with open(_COEFFS_PATH, "r") as _f:
    COEFFS: Dict[str, Dict[str, Any]] = json.load(_f)


def _lp1(x: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """First-order low-pass with time-varying dt."""
    if tau <= 0.0:
        return x
    y = np.empty_like(x, dtype=float)
    y[0] = x[0]
    for i in range(1, len(x)):
        dt = t[i] - t[i - 1]
        if not np.isfinite(dt) or dt <= 0:
            y[i] = x[i]
            continue
        a = dt / (tau + dt)
        y[i] = y[i - 1] + a * (x[i] - y[i - 1])
    return y


def _integrate_trajectory(t: np.ndarray, v: np.ndarray, yaw: np.ndarray):
    """Integrate (yaw, v) -> (x, y, psi). Trapezoidal."""
    n = len(t)
    psi = np.zeros(n)
    x = np.zeros(n)
    y = np.zeros(n)
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        if not np.isfinite(dt) or dt <= 0:
            psi[i] = psi[i - 1]
            x[i] = x[i - 1]
            y[i] = y[i - 1]
            continue
        # heading via trapezoidal yaw
        psi[i] = psi[i - 1] + 0.5 * (yaw[i] + yaw[i - 1]) * dt
        # position via trapezoidal v * (cos/sin psi)
        vx_prev = v[i - 1] * np.cos(psi[i - 1])
        vy_prev = v[i - 1] * np.sin(psi[i - 1])
        vx_cur = v[i] * np.cos(psi[i])
        vy_cur = v[i] * np.sin(psi[i])
        x[i] = x[i - 1] + 0.5 * (vx_prev + vx_cur) * dt
        y[i] = y[i - 1] + 0.5 * (vy_prev + vy_cur) * dt
    return x, y, psi


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index.

    Required columns out: yaw_rate_pred_rads, x_m, y_m
    """
    coeff = COEFFS.get(platform)

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    if coeff is None or coeff.get("passthrough", False):
        # Tesla / unknown platform: passthrough KS V0
        yaw = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    else:
        delta_road = sim_df["delta_road_rad"].to_numpy(dtype=float)
        L = float(coeff["L_eff"])
        K = float(coeff["K_us"])
        d0 = float(coeff.get("d0", 0.0))
        tau_y = float(coeff.get("tau_yaw", 0.0))
        tau_s = float(coeff.get("tau_steer", 0.0))

        delta_eff = _lp1(delta_road - d0, t, tau_s)
        denom = L + K * v * v
        denom = np.where(np.abs(denom) < 1e-6, 1e-6, denom)
        yaw_ss = v * delta_eff / denom
        yaw = _lp1(yaw_ss, t, tau_y)
        # safety: keep finite
        yaw = np.where(np.isfinite(yaw), yaw,
                       sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float))

    x, y, psi = _integrate_trajectory(t, v, yaw)

    return pd.DataFrame(
        {
            "yaw_rate_pred_rads": yaw,
            "x_m": x,
            "y_m": y,
            "psi_rad": psi,
        },
        index=sim_df.index,
    )
