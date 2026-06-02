"""Local scoring harness. Pooled yaw-rate RMSE + distance-resampled CTE RMSE.

Uses sim-only/segments/ to match grader contract. Loads truth from sim/segments/
view ONLY for scoring (not in predict()) — caller passes truth channel separately.
"""
from __future__ import annotations

import sys
from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-02")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))

from traj_metrics import cte_rmse_segment, cte_diagnostics_segment  # noqa: E402

SIM_ONLY = ROOT / "data" / "sim-only" / "segments"
SIM_FULL = ROOT / "data" / "sim" / "segments"

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def list_segments(platform: str):
    base = SIM_ONLY / platform
    out = []
    for p in base.rglob("sim.csv"):
        rel = p.relative_to(base).parent
        out.append((str(rel), p))
    return sorted(out)


def load_pair(platform: str, rel: str):
    sim_only_path = SIM_ONLY / platform / rel / "sim.csv"
    sim_full_path = SIM_FULL / platform / rel / "sim.csv"
    sim_in = pd.read_csv(sim_only_path)
    sim_truth = pd.read_csv(sim_full_path)
    return sim_in, sim_truth


def score_predict_fn(predict_fn, platforms=None, verbose=False):
    """Score predict(sim_df, platform) across the dev set."""
    if platforms is None:
        platforms = PLATFORMS
    per_platform = {}
    pooled_sse_yaw = 0.0
    pooled_n_yaw = 0
    pooled_sum_sq_cte = 0.0
    pooled_n_bins = 0
    for plat in platforms:
        sse = 0.0
        n = 0
        sum_sq = 0.0
        n_bins = 0
        sum_signed = 0.0
        n_segs = 0
        for rel, _ in list_segments(plat):
            sim_in, sim_truth = load_pair(plat, rel)
            try:
                out = predict_fn(sim_in, plat)
            except Exception as e:
                if verbose:
                    print(f"  {plat}/{rel}: predict failed: {e}")
                continue
            yr_pred = out["yaw_rate_pred_rads"].to_numpy()
            yr_truth = sim_truth["yaw_rate_meas_rads"].to_numpy()
            r = yr_pred - yr_truth
            sse += float(np.sum(r * r))
            n += len(r)
            t = sim_in["t_s"].to_numpy()
            v = sim_in["v_mps"].to_numpy()
            diag = cte_diagnostics_segment(t, v, yr_truth, yr_pred)
            sum_sq += diag["sum_sq_m2"]
            n_bins += diag["n_bins"]
            sum_signed += diag["sum_signed_m"]
            n_segs += 1
        yaw_rmse = math.sqrt(sse / n) if n else float("nan")
        cte_rmse = math.sqrt(sum_sq / n_bins) if n_bins else float("nan")
        per_platform[plat] = {
            "yaw_rmse": yaw_rmse,
            "cte_rmse": cte_rmse,
            "n_samples": n,
            "n_bins": n_bins,
            "n_segs": n_segs,
            "cte_signed_mean": sum_signed / n_bins if n_bins else float("nan"),
        }
        pooled_sse_yaw += sse
        pooled_n_yaw += n
        pooled_sum_sq_cte += sum_sq
        pooled_n_bins += n_bins
    pooled = {
        "yaw_rmse": math.sqrt(pooled_sse_yaw / pooled_n_yaw),
        "cte_rmse": math.sqrt(pooled_sum_sq_cte / pooled_n_bins),
    }
    return {"per_platform": per_platform, "pooled": pooled}


def print_score(result, label=""):
    print(f"=== {label} ===")
    for plat, m in result["per_platform"].items():
        print(f"  {plat:30s} yaw={m['yaw_rmse']:.5f} cte={m['cte_rmse']:7.2f} "
              f"signed={m['cte_signed_mean']:+7.2f}  n={m['n_samples']} segs={m['n_segs']}")
    p = result["pooled"]
    print(f"  POOLED                          yaw={p['yaw_rmse']:.5f} cte={p['cte_rmse']:7.2f}")
