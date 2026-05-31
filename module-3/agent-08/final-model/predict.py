"""Lateral-fidelity model — V2 ship.

Per-platform fit of a kinematic single-track steady-state yaw rate with:
  - polynomial steering scale  g(delta) = g0 + g2 * delta^2
  - steering offset            delta0
  - speed-quadratic understeer K_us
  - first-order yaw-rate lag   tau

Equation:
    yr_ss(t) = v(t) * (g(delta(t)) * delta(t) - delta0) / (L + K_us * v(t)^2)
    yr_pred(t)  = first_order_lag(yr_ss, tau)

Coefficients are fit per Ford platform on all available FORD_*/sim.csv data
under data/sim/segments/, using yaw_rate_meas_rads as truth and filtering
samples with v > 2 m/s.

Tesla has no truth channel — V0 passthrough.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with (_HERE / "coeffs.json").open() as _fh:
    COEFFS = json.load(_fh)


def _yr_lag(yr_ss: np.ndarray, dt: np.ndarray, tau: float) -> np.ndarray:
    """First-order lag: dy/dt = (yr_ss - y) / tau, discrete update."""
    if tau <= 1e-4 or len(yr_ss) < 2:
        return yr_ss.copy()
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    for i in range(1, len(yr_ss)):
        a = dt[i - 1] / (tau + dt[i - 1])
        y[i] = y[i - 1] + a * (yr_ss[i] - y[i - 1])
    return y


def _v0_passthrough(sim_df: pd.DataFrame) -> pd.DataFrame:
    if "yaw_rate_pred_rads" in sim_df.columns:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)},
            index=sim_df.index,
        )
    # Last-resort zero column
    return pd.DataFrame(
        {"yaw_rate_pred_rads": np.zeros(len(sim_df))}, index=sim_df.index
    )


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate (rad/s) for a single segment.

    Parameters
    ----------
    sim_df : pandas.DataFrame
        Must contain columns ``t_s``, ``v_mps``, ``delta_road_rad``.
        For Tesla (no calibrated coefficients) we fall back to V0's
        ``yaw_rate_pred_rads`` column if present.
    platform : str
        One of FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1, TESLA_MODEL_3.

    Returns
    -------
    pandas.DataFrame indexed identically to ``sim_df``, with column
    ``yaw_rate_pred_rads``.
    """
    if platform not in COEFFS:
        return _v0_passthrough(sim_df)

    p = COEFFS[platform]
    try:
        L = float(p["L"])
        g0 = float(p["g0"])
        g2 = float(p["g2"])
        delta0 = float(p["delta0"])
        K_us = float(p["K_us"])
        tau = float(p["tau"])
    except KeyError:
        return _v0_passthrough(sim_df)

    if not {"v_mps", "delta_road_rad", "t_s"}.issubset(sim_df.columns):
        return _v0_passthrough(sim_df)

    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    n = len(v)
    if n < 2 or np.any(np.diff(t) <= 0):
        return _v0_passthrough(sim_df)

    dt = np.diff(t)
    g_eff = g0 + g2 * delta * delta
    yr_ss = v * (g_eff * delta - delta0) / (L + K_us * v * v)
    yr = _yr_lag(yr_ss, dt, tau)

    # Replace any non-finite (e.g. div-by-zero on v=0 with negative L paths)
    if not np.all(np.isfinite(yr)):
        yr = np.where(np.isfinite(yr), yr, 0.0)

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
