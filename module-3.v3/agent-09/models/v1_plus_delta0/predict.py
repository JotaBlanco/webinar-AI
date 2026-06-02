"""Model B — V1 with per-segment δ₀ enabled for ALL non-Tesla platforms.

V1 currently uses a fixed δ₀ for Lightning (0.00133); Mach-E and IONIQ-5 use
per-segment δ₀ inferred from straight-row median. The shape change here is
small but structurally meaningful: it lets the steering-zero offset float per
segment for Lightning too, on the hypothesis that minor calibration drift
between segments is causing residual CTE accumulation even on Lightning's
already-good fit.

It also widens the v_thresh slightly to capture more straight-running data
for the median.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {"delta0_fallback": 0.00133, "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060},
    "FORD_MUSTANG_MACH_E_MK1":  {"delta0_fallback": -0.0001, "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069},
    "HYUNDAI_IONIQ_5":          {"delta0_fallback": 0.0,     "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062},
}


def _per_segment_delta0(sim_df, fallback, yr_thresh=0.02, v_thresh=5.0, min_rows=30):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PARAMS:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)
    p = PARAMS[platform]
    delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
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
