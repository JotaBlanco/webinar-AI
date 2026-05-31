"""Lateral-fidelity predict() — per-platform algebraic corrections on V0.

We start from the V0 kinematic single-track prediction ``yaw_rate_pred_rads``
already present in sim_df (the canonical grader provides it), then apply a
small per-platform correction fitted on the training set.

Per-platform best variants (selected on dev CTE-RMSE):

  FORD_F_150_LIGHTNING_MK1: V4  yr = a*yp + b*yp*v^2
  FORD_MUSTANG_MACH_E_MK1:  V2  yr = a*yp + b*yp^3
  HYUNDAI_IONIQ_5:          V4  yr = a*yp + b*yp*v^2
  TESLA_MODEL_3:            V0  yr = yp                (pred == truth in shared sim)

Coefficients are refit on full sim/segments/ (train + dev) and embedded as a
literal dict for reproducibility — no JSON I/O at predict time, so the bundle
is self-contained.

Trajectory (x, y) is integrated from the corrected yaw rate and measured speed
using forward Euler — matches the scoring CTE pipeline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# -- Per-platform coefficients (refit on full sim/segments/) ------------------
COEFS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "variant": "V4",
        "a": 0.9177983862255628,
        "b": -0.00043852098870204983,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "variant": "V2",
        "a": 1.0081143973509814,
        "b": 0.6698582934359751,
    },
    "HYUNDAI_IONIQ_5": {
        "variant": "V4",
        "a": 0.9119858350223977,
        "b": -0.0004967382938350903,
    },
    "TESLA_MODEL_3": {
        "variant": "V0",
    },
}


def _apply(yp: np.ndarray, v: np.ndarray, coefs: dict) -> np.ndarray:
    v0 = coefs["variant"]
    if v0 == "V0":
        return yp
    if v0 == "V1":
        return coefs["a"] * yp
    if v0 == "V2":
        return coefs["a"] * yp + coefs["b"] * yp ** 3
    if v0 == "V4":
        return coefs["a"] * yp + coefs["b"] * yp * v ** 2
    raise ValueError(f"unknown variant: {v0}")


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Forward-Euler integrate heading -> (x, y) using measured v and predicted yaw rate."""
    n = len(t)
    psi = np.zeros(n)
    x = np.zeros(n)
    y = np.zeros(n)
    if n < 2:
        return x, y
    dt = np.diff(t)
    # Heading: psi[k+1] = psi[k] + yr[k]*dt[k]
    for k in range(n - 1):
        psi[k + 1] = psi[k] + yr[k] * dt[k]
        x[k + 1] = x[k] + v[k] * np.cos(psi[k]) * dt[k]
        y[k + 1] = y[k] + v[k] * np.sin(psi[k]) * dt[k]
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index containing yaw_rate_pred_rads, x_m, y_m."""
    coefs = COEFS.get(platform, {"variant": "V0"})
    yp = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)
    yr = _apply(yp, v, coefs)
    x, y = _integrate_xy(t, v, yr)
    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
