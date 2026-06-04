"""idea-01 lateral fidelity — predict.

Variants:
  V0 (KS):            psi_dot = (v / L) * tan(delta_road)
  V1 (understeer):    psi_dot = gain * v * delta / (L + K * v^2)
  V2 (understeer+lag): same with first-order LP on delta (time constant tau)

Per-platform coefficients are fitted offline (see ../out/fit.py) on the
sim/segments truth column (yaw_rate_meas_rads where present; falls back to
psi_dot_rads for the older Tesla schema, which turns out to literally BE the
V0 prediction — hence Tesla picks V0).

Inputs available at grading time (sim-only schema, 8 cols):
  t_s, delta_wheel_deg, delta_road_rad, v_mps,
  a_long_mps2, accel_pedal_pct, brake_pressed, yaw_rate_pred_rads

Outputs:
  yaw_rate_pred_rads  (required)
  x_m, y_m            (integrated from corrected yaw_rate + measured v_mps)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_COEFFS_PATH = _HERE / "coeffs.json"

with open(_COEFFS_PATH) as _f:
    COEFFS = json.load(_f)

# Fallback for any platform not in the coeffs file: pure KS.
DEFAULT_L = 2.875


def _first_order_lp(x: np.ndarray, tau: float, dt: float) -> np.ndarray:
    if tau <= 1e-4 or dt <= 0:
        return x.astype(float).copy()
    a = float(np.exp(-dt / tau))
    y = np.empty_like(x, dtype=float)
    y[0] = x[0]
    one_minus_a = 1.0 - a
    for k in range(1, len(x)):
        y[k] = a * y[k - 1] + one_minus_a * x[k]
    return y


def _first_order_lp_var_dt(x: np.ndarray, tau: float, t: np.ndarray) -> np.ndarray:
    """LP for non-uniform sample times (uses per-step alpha)."""
    if tau <= 1e-4:
        return x.astype(float).copy()
    y = np.empty_like(x, dtype=float)
    y[0] = x[0]
    for k in range(1, len(x)):
        dt = t[k] - t[k - 1]
        a = float(np.exp(-max(dt, 0.0) / tau))
        y[k] = a * y[k - 1] + (1.0 - a) * x[k]
    return y


def _predict_yaw(delta_road: np.ndarray, v: np.ndarray, t: np.ndarray, coeffs: dict) -> np.ndarray:
    L = float(coeffs.get("L", DEFAULT_L))
    variant = coeffs.get("variant", "V0_KS")
    if variant == "V0_KS":
        return (v / L) * np.tan(delta_road)
    gain = float(coeffs.get("gain", 1.0))
    K = float(coeffs.get("K", 0.0))
    if variant == "V2_ust_lag":
        tau = float(coeffs.get("tau", 0.0))
        d_used = _first_order_lp_var_dt(delta_road, tau, t)
    else:
        d_used = delta_road
    return gain * v * d_used / (L + K * v * v)


def _integrate_traj(yaw_rate: np.ndarray, v: np.ndarray, t: np.ndarray):
    """Integrate (x, y, psi) from yaw_rate and measured v.

    Trapezoidal for psi; midpoint velocity for x,y.
    """
    n = len(t)
    psi = np.zeros(n)
    x = np.zeros(n)
    y = np.zeros(n)
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        psi[k] = psi[k - 1] + 0.5 * (yaw_rate[k - 1] + yaw_rate[k]) * dt
        # midpoint heading and speed for nicer x,y
        psi_mid = 0.5 * (psi[k - 1] + psi[k])
        v_mid = 0.5 * (v[k - 1] + v[k])
        x[k] = x[k - 1] + v_mid * np.cos(psi_mid) * dt
        y[k] = y[k - 1] + v_mid * np.sin(psi_mid) * dt
    return x, y, psi


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return DataFrame aligned with sim_df.index with yaw_rate_pred_rads, x_m, y_m."""
    coeffs = COEFFS.get(platform)
    if coeffs is None:
        # Unknown platform: graceful fallback to pure KS at default wheelbase
        coeffs = {"L": DEFAULT_L, "variant": "V0_KS"}

    t = sim_df["t_s"].to_numpy(dtype=float)
    delta_road = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    yaw_pred = _predict_yaw(delta_road, v, t, coeffs)
    x_m, y_m, _ = _integrate_traj(yaw_pred, v, t)

    out = pd.DataFrame(
        {
            "yaw_rate_pred_rads": yaw_pred,
            "x_m": x_m,
            "y_m": y_m,
        },
        index=sim_df.index,
    )
    return out
