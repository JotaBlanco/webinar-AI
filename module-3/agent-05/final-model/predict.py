"""Lateral-fidelity predictor.

Per-platform steady-state understeer model with first-order yaw lag:

    yr_ss[k] = v[k] * (g * delta_road[k] + delta_offset) / (L + K_us * v[k]^2)
    yr[k]    = (1 - alpha[k-1]) * yr[k-1] + alpha[k-1] * yr_ss[k]
    alpha[k] = dt[k] / (tau + dt[k])

Coefficients (g, delta_offset, K_us, tau, L) are fit per Ford platform from train
segments only (whole-route hold-out). For Tesla (no truth channel), we passthrough
V0's `yaw_rate_pred_rads`.

Trajectory (x, y) is integrated zero-order-hold from yaw_rate + v_meas — same
scheme as _shared/traj_metrics.integrate_trajectory — so the grader can use it
directly if desired (the grader integrates anyway, so this is for transparency).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open("r") as _fh:
    _COEFFS = json.load(_fh)


def _predict_yaw(t: np.ndarray, v: np.ndarray, delta: np.ndarray, c: dict) -> np.ndarray:
    g = float(c["g"])
    d0 = float(c["delta_offset"])
    K_us = float(c["K_us"])
    tau = float(c["tau"])
    L = float(c["L"])

    yr_ss = v * (g * delta + d0) / (L + K_us * v * v)
    n = len(t)
    if n == 0:
        return np.zeros(0)
    if n == 1 or tau <= 1e-6:
        return yr_ss.copy()
    dt = np.diff(t)
    # Guard against non-positive dt — fall back to no lag for those steps
    alpha = np.where(dt > 0, dt / (tau + dt), 1.0)
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    for k in range(1, n):
        yr[k] = (1.0 - alpha[k - 1]) * yr[k - 1] + alpha[k - 1] * yr_ss[k]
    return yr


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(t)
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
    """Predict lateral behaviour for one segment.

    Required input columns: t_s, v_mps, delta_road_rad (Ford). Tesla falls back
    to passthrough of `yaw_rate_pred_rads`.
    """
    idx = sim_df.index

    if platform not in _COEFFS:
        # No truth channel for Tesla — passthrough V0.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=idx)
        return out

    c = _COEFFS[platform]
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    # NaN-safe: replace NaNs with last-good or 0
    if np.isnan(v).any():
        v = pd.Series(v).ffill().bfill().fillna(0.0).to_numpy()
    if np.isnan(delta).any():
        delta = pd.Series(delta).ffill().bfill().fillna(0.0).to_numpy()

    yr = _predict_yaw(t, v, delta, c)
    x, y = _integrate_xy(t, v, yr)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=idx,
    )
