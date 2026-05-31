"""V1: anti-patterns recipe for Ford platforms; passthrough elsewhere."""
import numpy as np
import pandas as pd


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.02, v_thresh=5.0, min_rows=50):
    """Estimate per-segment steering offset using V0 yaw-rate prediction as
    a straight-driving detector. ALLOWED columns only."""
    v = sim_df["v_mps"].to_numpy()
    if "yaw_rate_pred_rads" in sim_df.columns:
        yr_proxy = sim_df["yaw_rate_pred_rads"].to_numpy()
        mask = (np.abs(yr_proxy) < yr_thresh) & (v > v_thresh)
    else:
        mask = (sim_df["delta_road_rad"].abs() < 0.005) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


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
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.9, "L_eff": 2.9, "K_us": 0.0025, "tau": 0.065,
    },
}


def _predict_bicycle(sim_df, p):
    delta0 = (_per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
              if p["use_per_segment_delta0"] else p["delta0"])
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


def predict(sim_df, platform):
    if platform not in PLATFORM_PARAMS:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                            index=sim_df.index)
    p = PLATFORM_PARAMS[platform]
    yr = _predict_bicycle(sim_df, p)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
