"""Final model — polynomial g + per-segment δ₀ + first-order yaw-rate lag.

Per platform: yr_ss = v · g(δ - δ₀) / (L_eff + K_us · v²) with g(δ) = g0 + g2·δ²,
followed by a first-order low-pass with time constant τ.

Tesla: V0 passthrough (no truth channel to fit against).

Inputs allowed (per the operating contract):
  t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
  accel_pedal_pct, brake_pressed, yaw_rate_pred_rads
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open() as f:
    PLATFORM_PARAMS: dict[str, dict] = json.load(f)


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float,
                        v_thresh: float = 5.0, min_rows: int = 50) -> float:
    """Estimate δ₀ from THIS segment's straight-driving rows. Input-only.

    Uses the V0 baseline yaw-rate prediction as a straight-detector proxy
    for lateral acceleration (a_lat_meas_mps2 is NOT in the grading allowlist).
    A row is "straight" when |v · yr_v0| < 0.3 m/s² and v > 5 m/s.
    """
    if "yaw_rate_pred_rads" not in sim_df.columns:
        return fallback
    v = sim_df["v_mps"].to_numpy(dtype=float)
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    a_lat_proxy = np.abs(v * yr_v0)
    mask = (a_lat_proxy < 0.3) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(sim_df.loc[mask, "delta_road_rad"].to_numpy()))


def _predict_yaw(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0"]
    delta_in = sim_df["delta_road_rad"].to_numpy(dtype=float) - delta0
    g_eff = p["g0"] + p.get("g2", 0.0) * delta_in * delta_in
    delta = delta_in * g_eff
    v = sim_df["v_mps"].to_numpy(dtype=float)
    L_eff = max(p["L_eff"], 0.5)
    yr_ss = v * delta / (L_eff + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy(dtype=float)
    dt = np.diff(t, prepend=t[0])
    tau = max(p["tau"], 1e-4)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def _integrate_trajectory(t: np.ndarray, v: np.ndarray, yr: np.ndarray
                          ) -> tuple[np.ndarray, np.ndarray]:
    """Trapezoidal integration of heading then position. psi(0)=0, (x,y)(0)=0."""
    dt = np.diff(t, prepend=t[0])
    dt[0] = 0.0
    psi = np.cumsum(yr * dt)  # ψ(t) = ∫ ψ̇ dt
    x = np.cumsum(v * np.cos(psi) * dt)
    y = np.cumsum(v * np.sin(psi) * dt)
    return x, y


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw_rate_pred_rads (and x_m, y_m) for the given platform.

    Tesla / unknown platforms: passthrough V0 yaw-rate.
    """
    if platform not in PLATFORM_PARAMS:
        # V0 passthrough — Tesla has no truth, so the only honest move
        # is to return the baseline.
        if "yaw_rate_pred_rads" in sim_df.columns:
            yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        else:
            yr = np.zeros(len(sim_df), dtype=float)
    else:
        yr = _predict_yaw(sim_df, PLATFORM_PARAMS[platform])

    out = pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    # Optional trajectory — integrate from predicted yaw and measured v.
    if "t_s" in sim_df.columns and "v_mps" in sim_df.columns:
        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        if len(t) >= 2 and np.all(np.diff(t) > 0):
            x, y = _integrate_trajectory(t, v, yr)
            out["x_m"] = x
            out["y_m"] = y
    return out
