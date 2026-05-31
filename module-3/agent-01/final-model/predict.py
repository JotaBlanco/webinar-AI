"""Final lateral-fidelity predictor.

Model: kinematic-bicycle steady-state yaw rate, per-platform calibrated, with a
first-order yaw lag.

    yr_ss(t) = v(t) * g * (delta(t) - delta_0) / (L + K_us * v(t)^2)

The output is then low-passed with a first-order filter of time constant tau:

    yr_pred[k] = yr_pred[k-1] + (dt / (tau + dt)) * (yr_ss[k] - yr_pred[k-1])

Trajectory `(x_m, y_m)` is integrated by forward-Euler using measured speed and
the predicted yaw rate, starting from `(0, 0)` with heading 0.

Tesla segments lack a truth channel and are not fit; we fall through to the V0
passthrough (`yaw_rate_pred_rads` from the sim.csv) for them.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with open(_COEFFS_PATH) as _f:
    _CFG = json.load(_f)

_TAU = float(_CFG.get("tau_s", 0.0))
_COEFFS = {k: v for k, v in _CFG.items() if isinstance(v, dict)}


def _steady_state(delta: np.ndarray, v: np.ndarray, c: dict) -> np.ndarray:
    return v * c["g"] * (delta - c["delta_0"]) / (c["L"] + c["K_us"] * v * v)


def _apply_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 0 or len(yr_ss) < 2:
        return yr_ss.copy()
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    for i in range(1, len(yr_ss)):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            y[i] = y[i - 1]
            continue
        alpha = dt / (tau + dt)
        y[i] = y[i - 1] + alpha * (yr_ss[i] - y[i - 1])
    return y


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray):
    n = len(t)
    x = np.zeros(n)
    y = np.zeros(n)
    psi = np.zeros(n)
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            x[i] = x[i - 1]; y[i] = y[i - 1]; psi[i] = psi[i - 1]
            continue
        psi_mid = psi[i - 1] + 0.5 * yr[i - 1] * dt
        v_mid = 0.5 * (v[i - 1] + v[i])
        x[i] = x[i - 1] + v_mid * np.cos(psi_mid) * dt
        y[i] = y[i - 1] + v_mid * np.sin(psi_mid) * dt
        psi[i] = psi[i - 1] + 0.5 * (yr[i - 1] + yr[i]) * dt
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate (and trajectory) from measured (delta, v).

    Falls back to V0 passthrough (the sim.csv's existing `yaw_rate_pred_rads`)
    for platforms that have no fitted coefficients (Tesla).
    """
    out = pd.DataFrame(index=sim_df.index)

    if platform not in _COEFFS:
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
        if {"x_m", "y_m"}.issubset(sim_df.columns):
            out["x_m"] = sim_df["x_m"].astype(float).to_numpy()
            out["y_m"] = sim_df["y_m"].astype(float).to_numpy()
        return out

    c = _COEFFS[platform]
    delta = sim_df["delta_road_rad"].astype(float).to_numpy()
    v = sim_df["v_mps"].astype(float).to_numpy()
    t = sim_df["t_s"].astype(float).to_numpy()

    yr_ss = _steady_state(delta, v, c)
    yr = _apply_lag(yr_ss, t, _TAU)

    out["yaw_rate_pred_rads"] = yr
    x, y = _integrate_xy(t, v, yr)
    out["x_m"] = x
    out["y_m"] = y
    return out
