"""V2: bicycle with per-platform fitted coefficients."""
import json
import numpy as np
import pandas as pd
from pathlib import Path

_COEFFS_PATH = Path(__file__).parent / "coeffs_v2.json"
with open(_COEFFS_PATH) as f:
    PLATFORM_PARAMS = json.load(f)


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.02, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    if "yaw_rate_pred_rads" in sim_df.columns:
        yr_proxy = sim_df["yaw_rate_pred_rads"].to_numpy()
        mask = (np.abs(yr_proxy) < yr_thresh) & (v > v_thresh)
    else:
        mask = (sim_df["delta_road_rad"].abs() < 0.005) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df, platform):
    if platform not in PLATFORM_PARAMS:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                            index=sim_df.index)
    p = PLATFORM_PARAMS[platform]
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=p.get("delta0", 0.0))
    else:
        delta0 = p.get("delta0", 0.0)
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
