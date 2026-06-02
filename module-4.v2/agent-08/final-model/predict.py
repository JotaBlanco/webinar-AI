"""Final model — V1 structure with locally-refit coefficients + optional
steering-rate feedforward.

Structure (per platform with truth data):
    delta0     = per-segment median of delta_road on near-straight bins, with
                 a constant fallback if too few bins.
    yr_ss      = v * g * (delta_road - delta0) / (L_eff + K_us * v^2)
                  + alpha_sr * d(delta_road)/dt
    yr         = first-order lag of yr_ss with time constant tau.

Tesla has no measured-yaw truth: pass through V0 (yaw_rate_pred_rads).

Trajectory (x_m, y_m) is left to the grader's default integration of
yaw_rate_pred + measured v.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).parent / "coeffs.json"
with _COEFFS_PATH.open() as fh:
    _COEFFS = json.load(fh)


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in _COEFFS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    c = _COEFFS[platform]
    g = c["g"]; L_eff = c["L_eff"]; K_us = c["K_us"]; tau = c["tau"]
    delta0_fb = c["delta0_fallback"]
    alpha_sr = c.get("alpha_steer_rate", 0.0)
    use_per_seg = c.get("use_per_segment_delta0", True)

    delta0 = _per_segment_delta0(sim_df, delta0_fb) if use_per_seg else delta0_fb

    delta_road = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()

    delta = (delta_road - delta0) * g
    yr_ss = v * delta / (L_eff + K_us * v * v)

    if alpha_sr != 0.0 and len(t) > 1:
        ddelta = np.gradient(delta_road, t)
        yr_ss = yr_ss + alpha_sr * ddelta

    dt = np.diff(t, prepend=t[0])
    # First-order lag (discrete)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
