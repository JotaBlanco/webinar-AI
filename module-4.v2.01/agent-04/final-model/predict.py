"""Final-model predict — V1 baseline (cohort leader).

After exploring the prefilled rung-1/2/3/orthogonal physics candidates in
phases/3-implement/models/, V1 (kinematic single-track + understeer +
first-order yaw lag + per-segment δ₀) remained the best pooled-dev model.

Of the prefilled candidates:
- M1 (linear dynamic single-track, rung 1): priors-only scorecard
  yaw=0.00919, cte=116.89 — needed fitting, and L-BFGS-B at the default
  bounds did not converge inside our wall-clock budget under heavy CPU
  contention (the cohort was running its M1 fits in parallel).
- M4 (relaxation-length, orthogonal): grid-searched sigma per platform
  on train, evaluated on dev:
    F150  sigma=0.3 -> yaw=0.00813, cte=93.90
    MachE sigma=0.5 -> yaw=0.00869, cte=63.98
    Ioniq sigma=0.3 -> yaw=0.00663, cte=66.88
    pooled: yaw=0.005636, cte=52.15  (V1: yaw=0.005430, cte=52.22)
  M4 ties V1 on CTE, marginally worse on yaw. Did not promote.

V1 reproduces the cohort leader and is the shipped model. Tesla falls
through to V0 passthrough (no truth channel).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


PLATFORM_PARAMS_V1 = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863,
        "L_eff": 3.26,
        "K_us": 0.00350,
        "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891,
        "L_eff": 2.22,
        "K_us": 0.00150,
        "tau": 0.069,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
        "tau": 0.062,
    },
}


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
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
    if platform not in PLATFORM_PARAMS_V1:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS_V1[platform]
    delta0 = (
        _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        if p["use_per_segment_delta0"]
        else p["delta0"]
    )
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
