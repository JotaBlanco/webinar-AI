"""Fast pooled scorer: pooled yaw RMSE + pooled distance-resampled CTE RMSE.

Loads segment CSVs once via pandas; calls a `predict(sim_df, platform)` callable.
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from _shared.frozen_split import dev_paths, train_paths
from _shared.traj_metrics import cte_rmse_segment

PLATFORMS = ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1",
             "HYUNDAI_IONIQ_5", "TESLA_MODEL_3")

SIM_ONLY_COLS = ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
                 "a_long_mps2", "accel_pedal_pct", "brake_pressed",
                 "yaw_rate_pred_rads"]


def platform_of(p: Path) -> str:
    return p.parts[-5]


def score_paths(paths, predict_fn, label="dev"):
    by_plat = {pl: {"sse_yaw": 0.0, "n_yaw": 0, "sse_cte": 0.0, "n_bins": 0,
                    "n_seg": 0, "n_short": 0} for pl in PLATFORMS}
    for p in paths:
        plat = platform_of(p)
        df = pd.read_csv(p)
        # Build sim_only df (input contract)
        cols = [c for c in SIM_ONLY_COLS if c in df.columns]
        sim_only = df[cols].copy()
        # Fill any missing optional cols with zeros to match input contract
        for c in SIM_ONLY_COLS:
            if c not in sim_only.columns:
                sim_only[c] = 0.0
        try:
            out = predict_fn(sim_only, plat)
        except Exception as e:
            print(f"  predict ERROR on {p}: {e}", file=sys.stderr)
            continue
        yr_pred = out["yaw_rate_pred_rads"].to_numpy()
        if "yaw_rate_meas_rads" in df.columns:
            yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        else:
            # Tesla case
            yr_truth = None
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        if yr_truth is not None:
            mask_v = v > 2.0
            r = (yr_pred - yr_truth)[mask_v]
            by_plat[plat]["sse_yaw"] += float(np.sum(r * r))
            by_plat[plat]["n_yaw"] += int(len(r))
            sum_sq, n_bins, _ = cte_rmse_segment(t, v, yr_truth, yr_pred)
            if n_bins > 0:
                by_plat[plat]["sse_cte"] += sum_sq
                by_plat[plat]["n_bins"] += n_bins
                by_plat[plat]["n_seg"] += 1
            else:
                by_plat[plat]["n_short"] += 1
    # Pool
    pool_yaw_sse = 0.0
    pool_yaw_n = 0
    pool_cte_sse = 0.0
    pool_cte_n = 0
    rows = {}
    for pl, d in by_plat.items():
        yr = math.sqrt(d["sse_yaw"] / d["n_yaw"]) if d["n_yaw"] else None
        cte = math.sqrt(d["sse_cte"] / d["n_bins"]) if d["n_bins"] else None
        rows[pl] = {"yaw_rmse": yr, "cte_rmse": cte, "n_seg": d["n_seg"],
                    "n_short": d["n_short"]}
        # pool only platforms with truth (skip Tesla)
        if d["n_yaw"] > 0:
            pool_yaw_sse += d["sse_yaw"]
            pool_yaw_n += d["n_yaw"]
        if d["n_bins"] > 0:
            pool_cte_sse += d["sse_cte"]
            pool_cte_n += d["n_bins"]
    pool_yaw = math.sqrt(pool_yaw_sse / pool_yaw_n) if pool_yaw_n else None
    pool_cte = math.sqrt(pool_cte_sse / pool_cte_n) if pool_cte_n else None
    return {"split": label, "pooled_yaw_rmse": pool_yaw,
            "pooled_cte_rmse": pool_cte, "by_platform": rows}


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "code"))
    from v1_baseline import predict_v1
    paths = dev_paths()
    res = score_paths(paths, predict_v1, "dev")
    print(json.dumps(res, indent=2))
