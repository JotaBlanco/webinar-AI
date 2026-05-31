"""Score V0 baseline using the existing yaw_rate_pred_rads channel."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

import pandas as pd
import math
import numpy as np
from traj_metrics import cte_diagnostics_segment

SEG_ROOT = ROOT / "data" / "sim" / "segments"
ALL_PATHS = sorted(SEG_ROOT.glob("*/*/*/*/sim.csv"))
print(f"Found {len(ALL_PATHS)} segments")


def score_predict(predict_fn, paths, sample_filter_v_mps=2.0):
    """predict_fn(sim_df, platform) -> DataFrame with yaw_rate_pred_rads (and optional x_m,y_m)."""
    per_platform = {}
    yaw_sum_sq_tot = 0.0
    yaw_n_tot = 0
    cte_sum_sq_tot = 0.0
    cte_n_tot = 0
    failed = 0
    for p in paths:
        platform = p.parents[3].name
        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue
        if "yaw_rate_meas_rads" not in sim_df.columns:
            failed += 1
            continue
        # strip to allowed input columns (mimic grader)
        allowed = {"t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
                   "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"}
        sim_df_in = sim_df[[c for c in sim_df.columns if c in allowed]]
        try:
            pred_df = predict_fn(sim_df_in, platform)
        except Exception as e:
            failed += 1
            continue
        if "yaw_rate_pred_rads" not in pred_df.columns or len(pred_df) != len(sim_df):
            failed += 1
            continue
        t = sim_df["t_s"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        yr_t = sim_df["yaw_rate_meas_rads"].to_numpy(float)
        yr_p = pred_df["yaw_rate_pred_rads"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue
        mask_v = v > sample_filter_v_mps
        resid = (yr_p - yr_t)[mask_v]
        yr_sum_sq = float(np.sum(resid**2))
        yr_sum_sg = float(np.sum(resid))
        yaw_sum_sq_tot += yr_sum_sq
        yaw_n_tot += int(mask_v.sum())
        cte = cte_diagnostics_segment(t, v, yr_t, yr_p, grid_step_m=1.0, min_distance_m=20.0)
        cte_sum_sq_tot += cte["sum_sq_m2"]
        cte_n_tot += cte["n_bins"]
        pp = per_platform.setdefault(platform, {"y_sq":0.0,"y_n":0,"y_sg":0.0,"c_sq":0.0,"c_n":0})
        pp["y_sq"] += yr_sum_sq; pp["y_n"] += int(mask_v.sum()); pp["y_sg"] += yr_sum_sg
        pp["c_sq"] += cte["sum_sq_m2"]; pp["c_n"] += cte["n_bins"]
    res = {
        "yaw_rate_rmse": math.sqrt(yaw_sum_sq_tot / yaw_n_tot) if yaw_n_tot else float("nan"),
        "cte_rmse": math.sqrt(cte_sum_sq_tot / cte_n_tot) if cte_n_tot else float("nan"),
        "n_segments_failed": failed,
        "per_platform": {},
    }
    for pl, d in per_platform.items():
        res["per_platform"][pl] = {
            "yaw_rmse": math.sqrt(d["y_sq"]/d["y_n"]) if d["y_n"] else float("nan"),
            "yaw_bias": d["y_sg"]/d["y_n"] if d["y_n"] else float("nan"),
            "cte_rmse": math.sqrt(d["c_sq"]/d["c_n"]) if d["c_n"] else float("nan"),
            "n": d["y_n"],
        }
    return res


def v0_predict(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()


if __name__ == "__main__":
    res = score_predict(v0_predict, ALL_PATHS)
    print(f"V0 yaw_rate_rmse: {res['yaw_rate_rmse']:.6f} rad/s")
    print(f"V0 cte_rmse:      {res['cte_rmse']:.4f} m")
    print(f"failed: {res['n_segments_failed']}")
    print("per-platform:")
    for pl, d in res["per_platform"].items():
        print(f"  {pl:30s} yaw_rmse={d['yaw_rmse']:.5f}  yaw_bias={d['yaw_bias']:+.5f}  cte_rmse={d['cte_rmse']:.3f}  n={d['n']:,}")
