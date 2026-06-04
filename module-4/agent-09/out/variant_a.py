"""Variant A: V1 + per-segment delta0 for Lightning too (instead of fixed 0.00133)."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

import numpy as np
import pandas as pd
from score import score


PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.00133,
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


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df, platform):
    if platform not in PARAMS:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)
    p = PARAMS[platform]
    delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"]) if p["use_per_segment_delta0"] else p["delta0"]
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


if __name__ == "__main__":
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(predict, segment_paths=segs)
    print(f"Variant A  yaw={res['yaw_rate_rmse']:.6f}  cte={res['cte_rmse']:.4f}")
    for plat, m in res["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f} bias={m['yaw_residual_mean']:+.5f}")
