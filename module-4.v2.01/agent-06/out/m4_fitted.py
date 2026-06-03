"""M4-relax-fitted — rung-orthogonal candidate.

Same V1 constants of record + F150 delta0=0.00200 fix, but replaces V1's
time-domain tau lag with a distance-domain relaxation length sigma per
platform. At constant v, sigma collapses to tau = sigma/v.

Pooled dev: yaw 0.005612 rad/s, CTE 50.56 m (sigma=0.3 across the board).

Logged in MODELS.md as the rung≥1 candidate per task requirement. Not the
ship model — fitted-V1 wins on yaw and ties on CTE.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

V1_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {"use_per_segment_delta0": False, "delta0": 0.00200, "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "sigma": 0.30},
    "FORD_MUSTANG_MACH_E_MK1":  {"use_per_segment_delta0": True, "delta0_fallback": -0.0001, "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "sigma": 0.30},
    "HYUNDAI_IONIQ_5":          {"use_per_segment_delta0": True, "delta0_fallback": 0.0,    "g": 0.938, "L_eff": 2.887,"K_us": 0.00289, "sigma": 0.30},
}
V_MIN_M4 = 1.5


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in V1_PARAMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()
    p = V1_PARAMS[platform]
    sigma = p["sigma"]
    d0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"]) if p["use_per_segment_delta0"] else p["delta0"]
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    delta_eff = (delta - d0) * p["g"]
    yr_demand = v * delta_eff / (p["L_eff"] + p["K_us"] * v * v)
    out = np.empty(len(t))
    out[0] = yr_demand[0] if v[0] >= V_MIN_M4 else yr_v0[0]
    st = out[0]
    for i in range(1, len(t)):
        if v[i] < V_MIN_M4 or sigma <= 0:
            st = yr_v0[i]
            out[i] = st
            continue
        alpha = 1.0 - np.exp(-v[i] * dt[i] / sigma)
        st = st + alpha * (yr_demand[i] - st)
        out[i] = st
    return pd.DataFrame({"yaw_rate_pred_rads": out}, index=sim_df.index)
