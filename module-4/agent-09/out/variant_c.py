"""Variant C: V1 with full-dataset refit coefficients."""
import sys, json
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

import numpy as np
import pandas as pd
from score import score


PARAMS = json.loads((ROOT / "out" / "fitted_coeffs_full.json").read_text())


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
    print(f"Variant C  yaw={res['yaw_rate_rmse']:.6f}  cte={res['cte_rmse']:.4f}")
    for plat, m in res["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f} bias={m['yaw_residual_mean']:+.5f}")
