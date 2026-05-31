"""Final-model predict() for agent-04.

Model: per-platform kinematic single-track with
    - polynomial steering scale: g_eff(delta) = g0 + g1 * |delta|
    - steering offset: delta0
    - speed-dependent understeer term in the closed-form steady-state yaw:
          yr_ss = v * g_eff * (delta - delta0) / (L + K_us * v^2)
    - first-order yaw-rate lag with time constant tau:
          yr_pred[k] = (1-alpha) * yr_pred[k-1] + alpha * yr_ss[k]
          alpha       = dt / (tau + dt)

Parameters were fitted per platform on a train split that holds out whole
(device_id, route_id) groups (see make-train-dev-split skill). Coefficients
live in coeffs.json next to this file.

Tesla has no truth channel; we fall back to V0 passthrough for it.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open("r") as _fh:
    _COEFFS_DOC = json.load(_fh)
_COEFFS = _COEFFS_DOC["platforms"]


def _predict_yr(t: np.ndarray, v: np.ndarray, delta: np.ndarray,
                g0: float, g1: float, delta0: float,
                K_us: float, tau: float, L: float) -> np.ndarray:
    g_eff = g0 + g1 * np.abs(delta)
    yr_ss = v * g_eff * (delta - delta0) / (L + K_us * v * v)
    n = len(t)
    if n == 0:
        return yr_ss
    if tau <= 1e-6:
        return yr_ss
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            yr[i] = yr[i - 1]
            continue
        alpha = dt / (tau + dt)
        yr[i] = (1.0 - alpha) * yr[i - 1] + alpha * yr_ss[i]
    return yr


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Integrate trajectory from (0,0,0). Mirrors _shared/traj_metrics.integrate_trajectory."""
    n = len(v)
    x = np.zeros(n)
    y = np.zeros(n)
    if n < 2:
        return x, y
    dt = np.diff(t)
    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw-rate (and x, y) for the given segment.

    Args:
        sim_df: per-segment sim.csv DataFrame. Must contain
            't_s', 'v_mps', 'delta_road_rad'. For Tesla passthrough
            'yaw_rate_pred_rads' is also needed.
        platform: one of 'FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1',
            'TESLA_MODEL_3'. Other platforms fall through to the V0 passthrough.

    Returns:
        DataFrame aligned with sim_df.index containing 'yaw_rate_pred_rads',
        'x_m', 'y_m'.
    """
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)

    if platform in _COEFFS and "delta_road_rad" in sim_df.columns:
        c = _COEFFS[platform]
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
        yr = _predict_yr(t, v, delta,
                         c["g0"], c["g1"], c["delta0"],
                         c["K_us"], c["tau"], c["L"])
    elif "yaw_rate_pred_rads" in sim_df.columns:
        # Tesla / unknown platform — fall back to V0.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    else:
        # No V0 to fall back on — return zeros (safer than NaN).
        yr = np.zeros_like(v)

    # Trajectory integration from yr + v (same scheme as the grader).
    x, y = _integrate_xy(t, v, yr)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
