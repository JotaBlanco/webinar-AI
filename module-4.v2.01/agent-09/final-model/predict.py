"""Final-model predict for module-4.v2.01-agent-09.

After running the prefilled candidates (M1, M3, M4, M5) and re-fitting
where it mattered, V1 still wins on the frozen held-out test split:

  V1 test pooled: yaw_rmse=0.005556 rad/s, cte_rmse=48.98 m
  M4 test pooled: yaw_rmse=0.005759 rad/s, cte_rmse=48.87 m  (M4 yaw -3.7%)
  M1 dev pooled : yaw_rmse=0.00919  rad/s, cte_rmse=116.89 m (rung-1 attempted)

The cohort gate requires at least one rung >= 1 candidate logged — that's
M1 in MODELS.md and M4 (orthogonal) as the closest non-V1 contender. The
*shipped* model is V1 because that's what the held-out numbers say.

This predict() is a self-contained copy of `code/v1_baseline.py:predict_v1`
so the final-model bundle has no cross-module imports at grading time.
Honours the operating contract: reads only the 8 allowlisted columns.
Tesla falls through to V0 passthrough (no truth channel).
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
    """V1 — kinematic single-track + understeer + first-order yaw lag + per-segment delta0."""
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
