"""Final lateral-fidelity model — agent-08.

Per-platform understeer-corrected scaling of the V0 KS baseline, with a
first-order lag (tau) and a small yaw-rate-derivative damping term (kdot):

    yv0_lag  = lowpass(yv0, tau)             # first-order lag on V0 yaw
    dyv0_dt  = d/dt yv0
    yaw_pred = (G * yv0_lag) / (1 + Kus * v^2) + kdot * dyv0_dt + bias

Coefficients are fit per platform against a yaw + CTE blend, so the model
both reduces yaw-rate RMSE and pulls in the signed CTE drift.

Tesla is held at identity (G=1, all else 0) because the Tesla sim has no
independent truth channel — psi_dot_rads IS the V0 KS output; deviating
from V0 can only increase RMSE on Tesla.

Coefficients live in `coeffs.json` next to this file.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json") as _fh:
    COEFFS: dict[str, dict] = json.load(_fh)

DEFAULT_COEFFS = {"G": 1.0, "Kus": 0.0, "bias": 0.0, "tau": 0.0, "kdot": 0.0}


def _lowpass(y: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """First-order discrete low-pass filter, time-varying dt."""
    if tau <= 1e-6:
        return y.copy()
    out = np.empty_like(y)
    out[0] = y[0]
    dt = np.diff(t)
    for i in range(1, len(y)):
        a = dt[i - 1] / (tau + dt[i - 1])
        out[i] = out[i - 1] + a * (y[i] - out[i - 1])
    return out


def _integrate(dt: np.ndarray, v: np.ndarray, yr: np.ndarray):
    n = len(v)
    psi = np.empty(n)
    psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n)
    x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y = np.empty(n)
    y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y, psi


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    c = COEFFS.get(platform, DEFAULT_COEFFS)
    G    = float(c.get("G", 1.0))
    Kus  = float(c.get("Kus", 0.0))
    bias = float(c.get("bias", 0.0))
    tau  = float(c.get("tau", 0.0))
    kdot = float(c.get("kdot", 0.0))

    v   = sim_df["v_mps"].to_numpy(dtype=float)
    yv0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    t   = sim_df["t_s"].to_numpy(dtype=float)

    yv0_lag = _lowpass(yv0, t, tau) if tau > 1e-6 else yv0

    if len(yv0) >= 2:
        dyv0 = np.empty_like(yv0)
        dyv0[0] = 0.0
        dyv0[1:] = (yv0[1:] - yv0[:-1]) / np.maximum(np.diff(t), 1e-6)
    else:
        dyv0 = np.zeros_like(yv0)

    yaw_pred = (G * yv0_lag) / (1.0 + Kus * v * v) + kdot * dyv0 + bias

    # Trajectory (optional) — integrate yaw with measured v.
    if len(v) >= 2:
        dt = np.diff(t)
        x, y, _ = _integrate(dt, v, yaw_pred)
    else:
        x = np.zeros_like(v)
        y = np.zeros_like(v)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": yaw_pred, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
