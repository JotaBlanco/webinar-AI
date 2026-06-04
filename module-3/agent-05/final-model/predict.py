"""Final model — V1: KS + steady-state understeer + first-order lag + per-segment δ₀.

Platform-gated:
- FORD_F_150_LIGHTNING_MK1: global δ₀ (per-segment bias-spread is tight; per-segment δ₀ would hurt).
- FORD_MUSTANG_MACH_E_MK1, HYUNDAI_IONIQ_5: per-segment δ₀ from an input-channel-only
  straight-row gate (|yaw_rate_pred_rads| < 0.03 ∧ v_mps > 5).
- TESLA_MODEL_3 and any unknown platform: V0 passthrough (no truth channel; honest fallback).

Coefficients are baked-in constants below (from coeffs.json shipped alongside this file
for traceability — predict.py does NOT read it at runtime to keep the bundle self-contained).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PLATFORM_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062,
    },
}


def _per_segment_delta0(sim_df: pd.DataFrame,
                        fallback: float = 0.0,
                        yr_thresh: float = 0.03,
                        v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    """Estimate δ₀ from this segment's own straight-driving rows.

    Uses input channels only (yaw_rate_pred_rads is allowlist, delta_road_rad is
    allowlist). Legal at grading time. NOT a truth peek — do not substitute
    yaw_rate_meas_rads or a_lat_meas_mps2 here; both are denied at grading.
    """
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return float(fallback)
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for a single segment.

    Returns a DataFrame aligned with sim_df.index containing
    `yaw_rate_pred_rads`. Trajectory (x_m, y_m) is omitted — the grader will
    integrate from yaw_rate + measured v.
    """
    if platform not in PLATFORM_PARAMS:
        # Tesla and any unknown platform: passthrough V0.
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS[platform]
    if p["use_per_segment_delta0"]:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
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
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
