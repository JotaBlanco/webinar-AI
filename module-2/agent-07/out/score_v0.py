"""Baseline V0 scoring against data/sim/segments — recompute using V0 predictor.

V0 = the ks_model with delta clamped to measured, v clamped to measured.
The predicted yaw_rate stored in sim.csv as `yaw_rate_pred_rads` already
reflects V0 (kinematic). We can either re-derive it (yr = v/L * tan(delta))
or use the column as-is. We re-derive to confirm.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from traj_metrics import cte_diagnostics_segment  # noqa
from parameters import PARAM_BY_PLATFORM  # noqa

# Approximate wheelbase for Hyundai Ioniq 5 (and fallback for Tesla in sim-only path).
WHEELBASE_M = {
    "TESLA_MODEL_3":            2.875,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5":          3.00,   # spec wheelbase 3000 mm
}


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Pure V0 KS: yaw = v * tan(delta_road) / L."""
    L = WHEELBASE_M.get(platform, 2.95)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    yr = (v / L) * np.tan(delta)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)


def score(predict_fn, platforms=("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"), sample_filter_v_mps=2.0):
    segs = []
    for plat in platforms:
        segs.extend(sorted((ROOT / "data" / "sim" / "segments" / plat).rglob("sim.csv")))

    rows = []
    total_yaw_sq = 0.0
    total_yaw_n = 0
    total_cte_sq = 0.0
    total_cte_n = 0
    per_plat = {}
    for p in segs:
        platform = p.parents[3].name
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        # strip to allowlist
        allow = {"t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"}
        sim_df_agent = df[[c for c in df.columns if c in allow]].copy()
        try:
            pred = predict_fn(sim_df_agent, platform)
        except Exception as e:
            print(f"FAIL {p}: {e}")
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        truth = df["yaw_rate_meas_rads"].to_numpy(float)
        pred_y = pred["yaw_rate_pred_rads"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue
        mask = v > sample_filter_v_mps
        n = int(mask.sum())
        if n == 0:
            continue
        ss = float(np.sum((pred_y[mask] - truth[mask])**2))
        total_yaw_sq += ss
        total_yaw_n += n
        cte = cte_diagnostics_segment(t, v, truth, pred_y)
        total_cte_sq += cte["sum_sq_m2"]
        total_cte_n += cte["n_bins"]
        ppl = per_plat.setdefault(platform, {"yss":0.0,"yn":0,"css":0.0,"cn":0,"nseg":0})
        ppl["yss"] += ss
        ppl["yn"] += n
        ppl["css"] += cte["sum_sq_m2"]
        ppl["cn"] += cte["n_bins"]
        ppl["nseg"] += 1

    yaw_rmse = math.sqrt(total_yaw_sq / total_yaw_n) if total_yaw_n else float("nan")
    cte_rmse = math.sqrt(total_cte_sq / total_cte_n) if total_cte_n else float("nan")
    return {
        "yaw_rate_rmse": yaw_rmse,
        "cte_rmse": cte_rmse,
        "n_samples": total_yaw_n,
        "n_bins": total_cte_n,
        "per_platform": {k: {
            "yaw_rmse": math.sqrt(v["yss"]/v["yn"]) if v["yn"] else float("nan"),
            "cte_rmse": math.sqrt(v["css"]/v["cn"]) if v["cn"] else float("nan"),
            "n_seg": v["nseg"],
        } for k,v in per_plat.items()},
    }


if __name__ == "__main__":
    res = score(predict_v0)
    print(f"V0 (re-derived): yaw_rmse={res['yaw_rate_rmse']:.5f}  cte_rmse={res['cte_rmse']:.3f}")
    for k,v in res["per_platform"].items():
        print(f"  {k}: yaw={v['yaw_rmse']:.5f} cte={v['cte_rmse']:.3f} n_seg={v['n_seg']}")

    # Also score the column-as-shipped (using yaw_rate_pred_rads from input as "predict")
    def predict_column(sim_df, platform):
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy(float)}, index=sim_df.index)
    res2 = score(predict_column)
    print(f"V0 (column):     yaw_rmse={res2['yaw_rate_rmse']:.5f}  cte_rmse={res2['cte_rmse']:.3f}")
    for k,v in res2["per_platform"].items():
        print(f"  {k}: yaw={v['yaw_rmse']:.5f} cte={v['cte_rmse']:.3f} n_seg={v['n_seg']}")
