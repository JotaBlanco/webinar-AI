"""Local score harness — operates on data/sim/segments (which contains truth).

Mirrors the grader contract: the predict() is handed an input-only sim_df with
only the 8 allowed columns (the same as sim-only mirror). Truth columns are
stripped before predict is called.
"""

from __future__ import annotations

import glob
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

ALLOWED = ("t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
           "a_long_mps2", "accel_pedal_pct", "brake_pressed",
           "yaw_rate_pred_rads")


def list_segments(platform_filter=None):
    base = ROOT / "data" / "sim" / "segments"
    paths = sorted(base.glob("*/*/*/*/sim.csv"))
    if platform_filter:
        paths = [p for p in paths if platform_filter in p.parts]
    return paths


def score(predict_fn, segment_paths=None, platform_filter=None, sample_v_thresh=2.0,
          per_platform=True, limit=None):
    if segment_paths is None:
        segment_paths = list_segments(platform_filter)
    if limit is not None:
        segment_paths = segment_paths[:limit]

    yaw_sum_sq_total = 0.0
    yaw_n_total = 0
    cte_sum_sq_total = 0.0
    cte_n_total = 0
    per_plat = {}
    failed = 0

    for p in segment_paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            failed += 1
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            failed += 1
            continue
        platform = p.parts[-5]
        agent_df = df[[c for c in ALLOWED if c in df.columns]].copy()
        try:
            pred = predict_fn(agent_df, platform)
        except Exception as e:
            failed += 1
            print("predict failed", platform, p.name, e)
            continue
        if "yaw_rate_pred_rads" not in pred.columns or len(pred) != len(df):
            failed += 1
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        yr_t = df["yaw_rate_meas_rads"].to_numpy(float)
        yr_p = pred["yaw_rate_pred_rads"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1
            continue
        mask = v > sample_v_thresh
        if mask.any():
            resid = yr_p[mask] - yr_t[mask]
            yaw_sum_sq_total += float((resid ** 2).sum())
            yaw_n_total += int(mask.sum())
        cte = cte_diagnostics_segment(t, v, yr_t, yr_p)
        cte_sum_sq_total += cte["sum_sq_m2"]
        cte_n_total += cte["n_bins"]
        if per_platform:
            d = per_plat.setdefault(platform, {"ys": 0.0, "yn": 0, "cs": 0.0, "cn": 0})
            if mask.any():
                d["ys"] += float((resid ** 2).sum())
                d["yn"] += int(mask.sum())
            d["cs"] += cte["sum_sq_m2"]
            d["cn"] += cte["n_bins"]

    out = {
        "yaw_rmse": math.sqrt(yaw_sum_sq_total / yaw_n_total) if yaw_n_total else float("nan"),
        "cte_rmse": math.sqrt(cte_sum_sq_total / cte_n_total) if cte_n_total else float("nan"),
        "n_segments": len(segment_paths) - failed,
        "failed": failed,
        "per_platform": {
            pf: {
                "yaw_rmse": math.sqrt(d["ys"] / d["yn"]) if d["yn"] else float("nan"),
                "cte_rmse": math.sqrt(d["cs"] / d["cn"]) if d["cn"] else float("nan"),
            }
            for pf, d in per_plat.items()
        },
    }
    return out


def predict_v0(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


if __name__ == "__main__":
    import time
    t0 = time.time()
    res = score(predict_v0)
    print(f"V0 baseline ({time.time()-t0:.1f}s):")
    print(f"  yaw_rmse: {res['yaw_rmse']:.6f} rad/s")
    print(f"  cte_rmse: {res['cte_rmse']:.4f} m")
    print(f"  n_segments: {res['n_segments']} (failed {res['failed']})")
    for pf, m in res["per_platform"].items():
        print(f"  {pf}: yaw={m['yaw_rmse']:.5f}  cte={m['cte_rmse']:.3f}")
