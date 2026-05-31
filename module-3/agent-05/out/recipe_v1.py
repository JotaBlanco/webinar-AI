"""Recipe v1: m3-agent-09's known-good formula, applied to all 3 truth platforms.

Per-platform fit will replace the placeholder constants below.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _per_segment_delta0(sim_df, fallback=0.0, ax_thresh=0.3, v_thresh=5.0, min_rows=50):
    """Estimate δ₀ from THIS segment's input-derived straight-driving rows.
    Uses a_lat surrogate computed from v * yaw_rate_pred_rads (V0 yaw) when
    a_lat_meas not present — but here we use the simpler delta_road_rad-only
    proxy: rows with low |delta_road_rad| and v > thresh.
    """
    # Use delta_road_rad magnitude as a proxy for "going straight" because
    # a_lat_meas_mps2 is stripped at grading time.
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    mask = (np.abs(delta) < 0.01) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta[mask]))


# Placeholder params — to be replaced via fit.
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
    "HYUNDAI_IONIQ_5": {
        # filler — needs fit
        "use_per_segment_delta0": False,
        "delta0": 0.0,
        "g": 0.88, "L_eff": 2.6, "K_us": 0.0025, "tau": 0.065,
    },
}


def predict_with_params(sim_df, platform, p):
    delta_in_raw = sim_df["delta_road_rad"].to_numpy()
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p.get("delta0_fallback", 0.0))
    else:
        delta0 = p.get("delta0", 0.0)
    delta = (delta_in_raw - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    tau = p["tau"]
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


def predict(sim_df, platform):
    if platform not in PLATFORM_PARAMS:
        return sim_df[["yaw_rate_pred_rads"]].copy()
    return predict_with_params(sim_df, platform, PLATFORM_PARAMS[platform])
