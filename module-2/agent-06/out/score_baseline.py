"""Pooled yaw RMSE + CTE for V0 baseline using yaw_rate_pred_rads as predictions.

Reads sim/segments/<PLAT>/<DEVICE>/<ROUTE>/<IDX>/sim.csv. Tesla has older schema
(psi_dot_rads); we coerce it.
"""
from __future__ import annotations
import math, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa

DATA = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-06/data/sim/segments")

def load_segment(p: Path):
    df = pd.read_csv(p)
    # Normalise truth col name
    if "yaw_rate_meas_rads" not in df.columns and "psi_dot_rads" in df.columns:
        df["yaw_rate_meas_rads"] = df["psi_dot_rads"]
    return df

def score_v0(pred_col="yaw_rate_pred_rads", platform_filter=None, v_min=2.0):
    pools = {}
    total = {"yaw_sq": 0.0, "yaw_n": 0, "cte_sq": 0.0, "cte_n": 0}
    for plat_dir in sorted(DATA.iterdir()):
        plat = plat_dir.name
        if platform_filter and plat != platform_filter:
            continue
        pools.setdefault(plat, {"yaw_sq": 0.0, "yaw_n": 0, "cte_sq": 0.0, "cte_n": 0, "nseg": 0})
        for p in plat_dir.glob("*/*/*/sim.csv"):
            try:
                df = load_segment(p)
            except Exception:
                continue
            if "yaw_rate_meas_rads" not in df.columns or pred_col not in df.columns:
                continue
            t = df["t_s"].to_numpy(float)
            v = df["v_mps"].to_numpy(float)
            yr_t = df["yaw_rate_meas_rads"].to_numpy(float)
            yr_p = df[pred_col].to_numpy(float)
            if len(t) < 2 or np.any(np.diff(t) <= 0):
                continue
            mask = v > v_min
            r = yr_p[mask] - yr_t[mask]
            pools[plat]["yaw_sq"] += float((r*r).sum())
            pools[plat]["yaw_n"] += int(mask.sum())
            cte = cte_diagnostics_segment(t, v, yr_t, yr_p)
            pools[plat]["cte_sq"] += cte["sum_sq_m2"]
            pools[plat]["cte_n"] += cte["n_bins"]
            pools[plat]["nseg"] += 1
            total["yaw_sq"] += float((r*r).sum())
            total["yaw_n"] += int(mask.sum())
            total["cte_sq"] += cte["sum_sq_m2"]
            total["cte_n"] += cte["n_bins"]
    print(f"OVERALL yaw_rmse={math.sqrt(total['yaw_sq']/total['yaw_n']):.5f}  cte_rmse={math.sqrt(total['cte_sq']/total['cte_n']):.3f}m  (n_yaw={total['yaw_n']:,}, n_cte={total['cte_n']:,})")
    for plat, p in pools.items():
        if p["yaw_n"] == 0:
            print(f"  {plat}: no segments scored")
            continue
        print(f"  {plat}: yaw={math.sqrt(p['yaw_sq']/p['yaw_n']):.5f}  cte={math.sqrt(p['cte_sq']/p['cte_n']):.3f}m  nseg={p['nseg']}")
    return pools, total

if __name__ == "__main__":
    score_v0()
