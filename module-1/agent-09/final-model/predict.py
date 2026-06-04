"""V1 lateral fidelity predictor.

Model (per-platform):

    yaw_ss(t) = v(t) * delta(t) / (L + K * v(t)^2)        # linear bicycle SS
    yaw_pred(t) = first_order_lag(yaw_ss; tau)(t) + bias  # transient + bias

Trajectory: integrate yaw_pred with measured v.
    psi(t)   = cumtrapz(yaw_pred, t)
    x(t)     = cumtrapz(v * cos(psi), t)
    y(t)     = cumtrapz(v * sin(psi), t)

Per-platform coefficients (L, K, tau, bias) are in coeffs.json next to this
file. Tesla falls back to V0 KS (`yaw_rate_pred_rads` in sim_df) because the
Tesla sim CSVs ship no measured-yaw truth to fit against.
"""
from __future__ import annotations
import json
import os
from typing import Any
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_COEFFS_PATH = os.path.join(_HERE, "coeffs.json")

with open(_COEFFS_PATH) as _f:
    _COEFFS = json.load(_f)


def _lowpass(x: np.ndarray, tau: float, dt: float) -> np.ndarray:
    if tau is None or tau <= 1e-6:
        return x.copy()
    alpha = dt / (tau + dt)
    y = np.empty_like(x, dtype=float)
    y[0] = x[0]
    for i in range(1, len(x)):
        y[i] = y[i-1] + alpha * (x[i] - y[i-1])
    return y


def _cumtrapz(y: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Cumulative trapezoidal integral with leading zero (so output length == input)."""
    if len(y) < 2:
        return np.zeros_like(y, dtype=float)
    dt = np.diff(t)
    increments = 0.5 * (y[:-1] + y[1:]) * dt
    out = np.empty_like(y, dtype=float)
    out[0] = 0.0
    out[1:] = np.cumsum(increments)
    return out


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return yaw_rate_pred_rads (and x_m, y_m) aligned with sim_df.index."""
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    coeff = _COEFFS.get(platform)
    if coeff is None:
        # Unknown platform — use V0 fallback (already in sim_df).
        if "yaw_rate_pred_rads" in sim_df.columns:
            yaw = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            # Last-ditch KS guess with Tesla wheelbase
            yaw = v * np.tan(delta) / 2.875
    else:
        L = float(coeff["L"])
        K = float(coeff["K"])
        tau = float(coeff.get("tau", 0.0))
        bias = float(coeff.get("bias", 0.0))
        use_v0 = bool(coeff.get("use_v0", False))
        if use_v0 and "yaw_rate_pred_rads" in sim_df.columns:
            yaw = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            # Steady-state linear bicycle gain
            ss = v * delta / (L + K * v * v)
            dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.02
            yaw = _lowpass(ss, tau, dt) + bias

    # Integrate trajectory from yaw + measured v
    psi = _cumtrapz(yaw, t)
    x = _cumtrapz(v * np.cos(psi), t)
    y = _cumtrapz(v * np.sin(psi), t)

    return pd.DataFrame(
        {
            "yaw_rate_pred_rads": yaw,
            "x_m": x,
            "y_m": y,
        },
        index=sim_df.index,
    )
