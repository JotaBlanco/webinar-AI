"""V1 — KS + understeer + tau + per-segment delta0 (input-only).

Recipe lifted from anti-patterns.md worked example (m3-agent-09), adapted
because sim-only schema does NOT include a_lat_meas_mps2. We instead
reconstruct an a_lat proxy from V0's pre-computed yaw_rate_pred_rads:
    a_lat_proxy = v_mps * yaw_rate_pred_rads
This is input-only (legal at inference).
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
        "g": 0.891, "L_eff": 2.22, "K_us": 0.00202, "tau": 0.069,
    },
}


def _per_segment_delta0(sim_df, fallback=0.0,
                        ax_thresh=0.3, v_thresh=5.0, min_rows=50):
    # a_lat proxy from V0 pre-computed yaw
    v = sim_df["v_mps"].to_numpy()
    yr0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    a_lat = v * yr0
    delta_road = sim_df["delta_road_rad"].to_numpy()
    mask = (np.abs(a_lat) < ax_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def _ks_pred(sim_df, p, delta0):
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
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PLATFORM_PARAMS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS[platform]
    delta0 = (_per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
              if p["use_per_segment_delta0"] else p["delta0"])
    yr = _ks_pred(sim_df, p, delta0)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
