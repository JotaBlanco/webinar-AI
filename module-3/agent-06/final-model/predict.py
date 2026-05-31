"""Lateral-fidelity predictor (agent-06).

Per-platform kinematic single-track with:
  - steering scale  g
  - steering offset delta0  (per-platform; for Mach-E blended with a per-segment
    self-calibrated delta0 estimated from low |a_lat| samples — that's signal
    the bicycle model only sees indirectly)
  - linear understeer term K_us
  - first-order yaw-rate lag with time constant tau

Fits live in coeffs.json. Tesla falls back to V0 passthrough because the
dataset carries no truth channel for Tesla to fit against.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with _COEFFS_PATH.open("r") as _fh:
    _COEFFS = json.load(_fh)


def _first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 1e-6:
        return yr_ss.copy()
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = float(yr_ss[0])
    for i in range(1, n):
        dt = t[i] - t[i - 1]
        if dt <= 0:
            y[i] = y[i - 1]
            continue
        alpha = dt / (tau + dt)
        y[i] = y[i - 1] + alpha * (yr_ss[i] - y[i - 1])
    return y


def _self_delta0(delta: np.ndarray, v: np.ndarray, a_lat: np.ndarray,
                 v_min: float = 5.0, a_lat_max: float = 0.3,
                 min_n: int = 50) -> float | None:
    mask = (np.abs(a_lat) < a_lat_max) & (v > v_min)
    if int(mask.sum()) >= min_n:
        return float(np.median(delta[mask]))
    return None


def _integrate_xy(t: np.ndarray, v: np.ndarray, yr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Euler integrate (yr, v) from (0,0,0,0). Returns x, y arrays."""
    n = len(t)
    if n < 2:
        return np.zeros(n), np.zeros(n)
    dt = np.diff(t)
    psi = np.empty(n); psi[0] = 0.0
    psi[1:] = np.cumsum(yr[:-1] * dt)
    x = np.empty(n); x[0] = 0.0
    x[1:] = np.cumsum(v[:-1] * np.cos(psi[:-1]) * dt)
    y = np.empty(n); y[0] = 0.0
    y[1:] = np.cumsum(v[:-1] * np.sin(psi[:-1]) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate (and trajectory) for a single segment.

    Args:
        sim_df: per-sample DataFrame; must include t_s, v_mps, delta_road_rad.
            For Mach-E we also use a_lat_meas_mps2 if available.
        platform: e.g. "FORD_MUSTANG_MACH_E_MK1".

    Returns:
        DataFrame with index == sim_df.index and columns
        [yaw_rate_pred_rads, x_m, y_m].
    """
    n = len(sim_df)
    idx = sim_df.index

    # Tesla: passthrough V0.
    if platform not in _COEFFS:
        if "yaw_rate_pred_rads" in sim_df.columns:
            yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            yr = np.zeros(n)
        out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=idx)
        if n >= 2 and "t_s" in sim_df.columns and "v_mps" in sim_df.columns:
            t = sim_df["t_s"].to_numpy(dtype=float)
            v = sim_df["v_mps"].to_numpy(dtype=float)
            x, y = _integrate_xy(t, v, yr)
            out["x_m"] = x
            out["y_m"] = y
        return out

    c = _COEFFS[platform]
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)

    # Per-segment self-calibrated delta0 (uses a_lat if available).
    d0_self = None
    if "a_lat_meas_mps2" in sim_df.columns:
        a_lat = sim_df["a_lat_meas_mps2"].to_numpy(dtype=float)
        d0_self = _self_delta0(delta, v, a_lat)
    if d0_self is None:
        d0_self = c["d0_fallback"]

    lam = float(c["self_delta0_blend"])  # 0 => pure platform, 1 => pure self
    d0 = (1.0 - lam) * float(c["delta0_platform"]) + lam * d0_self

    # Steady-state yaw rate with understeer.
    delta_eff = float(c["g"]) * (delta - d0)
    denom = float(c["L"]) + float(c["K_us"]) * v * v
    yr_ss = v * delta_eff / np.maximum(denom, 1e-6)

    # First-order yaw-rate lag.
    if n < 2 or np.any(np.diff(t) <= 0):
        yr_pred = yr_ss
    else:
        yr_pred = _first_order_lag(yr_ss, t, float(c["tau"]))

    out = pd.DataFrame({"yaw_rate_pred_rads": yr_pred}, index=idx)
    if n >= 2 and not np.any(np.diff(t) <= 0):
        x, y = _integrate_xy(t, v, yr_pred)
        out["x_m"] = x
        out["y_m"] = y
    else:
        out["x_m"] = 0.0
        out["y_m"] = 0.0
    return out
