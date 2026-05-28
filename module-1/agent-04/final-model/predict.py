"""Final lateral-fidelity model for agent-04.

Model form (V3 — speed-known kinematic single-track with three calibrated
corrections layered on top of the KS baseline):

    delta_eff[k] = lowpass_tau( delta_road[k] - delta_off )
    psi_dot[k]   = a * (v[k] / L) * tan(delta_eff[k]) / (1 + b * v[k]**2)

where, per-platform:
  - L          : wheelbase (carParams; same as V0)
  - a          : scale of the bicycle response (catches steering-ratio /
                 effective-radius bias)
  - b          : understeer-gradient term (linearised bicycle-model effect
                 K_us / L; degrades the linear-tyre yaw gain with v^2)
  - delta_off  : constant road-wheel steering offset
  - tau        : first-order lag between commanded delta and effective delta
                 (steering-rack + tyre relaxation, lumped)

Coefficients are loaded from `coeffs.json` (fit on a 80/20 train/val
split-by-route, Nelder-Mead least squares on yaw-rate). TESLA_MODEL_3 falls
back to identity (V0) — there is no truth channel for Tesla in the dataset
so fitting it is impossible without exfiltrating outside the agent.

Trajectory (x, y) is integrated from the predicted yaw rate using the
measured longitudinal speed (`v_mps`) at the same dt as the sim sample.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
_COEFFS = json.loads((_THIS_DIR / "coeffs.json").read_text())

# Fallback for unknown platforms — pure KS (V0) with a placeholder L.
_FALLBACK = {"L": 2.9, "a": 1.0, "b": 0.0, "delta_off": 0.0, "tau": 0.0}


def _lowpass(x: np.ndarray, dt: float, tau: float) -> np.ndarray:
    """First-order exponential lowpass. tau<=0 returns x unchanged."""
    if tau <= 1e-6 or len(x) < 2:
        return x.copy()
    out = np.empty_like(x)
    out[0] = x[0]
    alpha = dt / (tau + dt)
    for k in range(1, len(x)):
        out[k] = out[k - 1] + alpha * (x[k] - out[k - 1])
    return out


def _integrate_xy(yaw_rate: np.ndarray, v: np.ndarray, dt: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Forward-Euler integration of yaw_rate -> heading -> (x, y).

    All arrays length N; dt is either scalar or length N (uses dt[k] for step k).
    """
    n = len(yaw_rate)
    psi = np.zeros(n)
    x = np.zeros(n)
    y = np.zeros(n)
    if n < 2:
        return x, y, psi
    # vector dt (treat element k as the step from sample k-1 to k)
    dt_arr = dt if np.ndim(dt) else np.full(n, float(dt))
    for k in range(1, n):
        d = dt_arr[k]
        psi[k] = psi[k - 1] + yaw_rate[k - 1] * d
        x[k] = x[k - 1] + v[k - 1] * np.cos(psi[k - 1]) * d
        y[k] = y[k - 1] + v[k - 1] * np.sin(psi[k - 1]) * d
    return x, y, psi


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict lateral state for one segment.

    Required input columns:
        - t_s              [s]   uniform time grid
        - v_mps            [m/s] measured longitudinal speed
        - delta_road_rad   [rad] measured road-wheel angle (post-ratio)

    Returns a DataFrame aligned on sim_df.index with columns
    `yaw_rate_pred_rads`, `x_m`, `y_m`.
    """
    p = _COEFFS.get(platform, _FALLBACK)
    L = float(p["L"])
    a = float(p["a"])
    b = float(p["b"])
    delta_off = float(p["delta_off"])
    tau = float(p["tau"])

    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    dlt = sim_df["delta_road_rad"].to_numpy(dtype=float)

    n = len(t)
    if n == 0:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": [], "x_m": [], "y_m": []},
            index=sim_df.index,
        )

    # Time step. Use the median diff as the lag-filter dt to be robust to
    # any duplicate-timestamp glitches; use per-step dt for trajectory
    # integration.
    if n >= 2:
        dt_med = float(np.median(np.diff(t)))
        if not np.isfinite(dt_med) or dt_med <= 0:
            dt_med = 0.02
        dt_per = np.diff(t, prepend=t[0])
        dt_per[0] = dt_med
        # clamp negatives / zeros
        dt_per = np.where(dt_per > 0, dt_per, dt_med)
    else:
        dt_med = 0.02
        dt_per = np.array([dt_med])

    # Effective steering: subtract offset, then apply first-order lag.
    delta_eff = _lowpass(dlt - delta_off, dt_med, tau)

    # Yaw rate prediction with understeer correction.
    yaw_pred = a * (v / L) * np.tan(delta_eff) / (1.0 + b * v * v)

    # Trajectory integration (forward Euler, consistent with grader pattern).
    x_m, y_m, _psi = _integrate_xy(yaw_pred, v, dt_per)

    out = pd.DataFrame(
        {"yaw_rate_pred_rads": yaw_pred, "x_m": x_m, "y_m": y_m},
        index=sim_df.index,
    )
    return out
