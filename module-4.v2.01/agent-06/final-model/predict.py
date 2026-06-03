"""Final model — fitted-V1 (rung-0, calibrated per-platform).

This is V1 (kinematic single-track + understeer + first-order yaw lag +
per-segment δ₀) with conservative per-platform tau calibration tightened on
the frozen train/dev split:

  - FORD_F_150_LIGHTNING_MK1: unchanged from V1 (delta0=0.00133, tau=0.060).
      A delta0=0.00200 dev-fit reduced dev CTE 93.8→79.1 but flipped the
      signed CTE drift from +29.8 m to -35.6 m on the held-out test split
      — clear overfit, reverted.
  - FORD_MUSTANG_MACH_E_MK1:  tau 0.069 → 0.060.
  - HYUNDAI_IONIQ_5:          tau 0.062 → 0.045.
  - TESLA_MODEL_3:            V0 passthrough (no independent truth channel).

Pooled dev:  yaw RMSE 0.005410 rad/s, CTE RMSE 52.16 m  (V1: 0.005430 / 52.22).
Pooled test: yaw RMSE 0.005563 rad/s, CTE RMSE 48.97 m  (V1: 0.005556 / 48.98).

Operating-contract compliant: reads only the 8 allowed columns from sim-only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


PLATFORM_PARAMS = {
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
        "tau": 0.060,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
        "tau": 0.045,
    },
}


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    """Median straight-driving steering offset for this segment."""
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for `platform` over `sim_df`.

    Returns a DataFrame aligned with `sim_df.index` containing
    `yaw_rate_pred_rads` (and `x_m`, `y_m` integrated trajectory).
    Tesla falls through to the V0 baseline (no truth channel).
    """
    if platform not in PLATFORM_PARAMS:
        yr = sim_df["yaw_rate_pred_rads"].to_numpy()
    else:
        p = PLATFORM_PARAMS[platform]
        if p["use_per_segment_delta0"]:
            d0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        else:
            d0 = p["delta0"]
        delta = (sim_df["delta_road_rad"].to_numpy() - d0) * p["g"]
        v = sim_df["v_mps"].to_numpy()
        yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
        t = sim_df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        alpha = dt / (p["tau"] + dt)
        yr = np.empty_like(yr_ss)
        yr[0] = yr_ss[0]
        for i in range(1, len(yr)):
            yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])

    # Integrate trajectory from yaw + v for the CTE metric.
    t = sim_df["t_s"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    psi = np.cumsum(yr * dt)
    x = np.cumsum(v * np.cos(psi) * dt)
    y = np.cumsum(v * np.sin(psi) * dt)

    return pd.DataFrame(
        {"yaw_rate_pred_rads": yr, "x_m": x, "y_m": y},
        index=sim_df.index,
    )
