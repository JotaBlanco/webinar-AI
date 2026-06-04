"""Final model — rung-0 KS + steering scale + understeer + first-order lag
+ per-segment δ₀ (legal cousin, platform-gated).

Per-platform coefficients fitted on this dataset against pooled yaw RMSE
(scipy.optimize, route-grouped train/dev split, ~80/20).

- FORD_F_150_LIGHTNING_MK1: global δ₀, fitted coeffs.
- FORD_MUSTANG_MACH_E_MK1:  per-segment δ₀ from input-only straight gate.
- HYUNDAI_IONIQ_5:           per-segment δ₀ from input-only straight gate.
- TESLA_MODEL_3:             V0 passthrough (no truth channel to fit against).

Straight-gate uses only allowlist channels:
  mask = |yaw_rate_pred_rads| < 0.03  ∧  v_mps > 5
This is legal at grading time — no `yaw_rate_meas_rads` / `a_lat_meas_mps2`
peeking.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
with open(_HERE / "coeffs.json") as f:
    _COEFFS = json.load(f)


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    """Median delta_road over straight-driving rows in this segment.

    Uses only input channels (yaw_rate_pred_rads, v_mps, delta_road_rad).
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate (and integrated trajectory via grader fallback).

    Returns a DataFrame aligned with sim_df.index with at minimum the
    `yaw_rate_pred_rads` column. The grader integrates x,y from this and v_mps.
    """
    if platform not in _COEFFS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = _COEFFS[platform]

    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0"])
    else:
        delta0 = p["delta0"]

    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)

    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
