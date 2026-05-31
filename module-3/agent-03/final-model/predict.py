"""Lateral-fidelity predict() — per-platform refined KS + understeer + lag + per-segment δ₀.

Operating contract:
- Input columns available (sim-only allowlist): t_s, delta_wheel_deg, delta_road_rad,
  v_mps, a_long_mps2, accel_pedal_pct, brake_pressed, yaw_rate_pred_rads.
- NO truth (yaw_rate_meas_rads), NO a_lat_meas_mps2 — so straight-row detection uses
  only |delta_road_rad| and v_mps thresholds.

Model per platform (Mach-E, Lightning, Hyundai):
    delta_eff = (delta_road_rad - delta0) * g
    yr_ss     = v * delta_eff / (L_eff + K_us * v^2)
    yr[i]     = yr[i-1] + (dt/(tau+dt)) * (yr_ss[i] - yr[i-1])    # first-order lag

Tesla: V0 passthrough (no truth channel in sim, V0 IS the canonical answer).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS_CACHE = None


def _load_coeffs():
    global _COEFFS_CACHE
    if _COEFFS_CACHE is None:
        with open(_COEFFS_PATH) as f:
            _COEFFS_CACHE = json.load(f)
    return _COEFFS_CACHE


def _per_segment_delta0(sim_df, fallback=0.0, v_thresh=8.0, delta_thresh=0.005, min_rows=80):
    """Estimate δ₀ from rows that look like straight driving, using INPUT columns only.

    Without a_lat_meas (not in the sim-only allowlist), we approximate "straight" by:
    (a) small road-wheel angle: |delta_road_rad| < delta_thresh,
    (b) above v_thresh m/s (excludes very low-speed manoeuvring).
    The intersection is the segment's near-zero-steering rows; their median delta_road_rad
    is the residual steering offset.
    """
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    mask = (np.abs(delta) < delta_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta[mask]))


def _first_order_lag(yr_ss: np.ndarray, dt: np.ndarray, tau: float) -> np.ndarray:
    """Discrete first-order lag with per-step alpha = dt/(tau+dt)."""
    n = len(yr_ss)
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    if tau <= 1e-9:
        return yr_ss.copy()
    for i in range(1, n):
        alpha = dt[i] / (tau + dt[i])
        yr[i] = yr[i - 1] + alpha * (yr_ss[i] - yr[i - 1])
    return yr


def _predict_platform(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    delta_raw = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(
            sim_df,
            fallback=p.get("delta0_fallback", 0.0),
            v_thresh=p.get("v_thresh", 8.0),
            delta_thresh=p.get("delta_thresh", 0.005),
            min_rows=p.get("min_rows", 80),
        )
    else:
        delta0 = p.get("delta0", 0.0)

    g = p["g"]
    L_eff = p["L_eff"]
    K_us = p["K_us"]
    tau = p.get("tau", 0.0)

    delta_eff = (delta_raw - delta0) * g
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)

    if len(t) >= 2:
        dt = np.diff(t, prepend=t[0])
        dt[0] = dt[1] if len(dt) > 1 else 0.02
        yr = _first_order_lag(yr_ss, dt, tau)
    else:
        yr = yr_ss
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    coeffs = _load_coeffs()

    if platform == "TESLA_MODEL_3":
        # No truth channel; V0 passthrough is the honest answer.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    if platform not in coeffs:
        # Unknown platform — fall back to V0 baseline.
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    yr = _predict_platform(sim_df, coeffs[platform])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
