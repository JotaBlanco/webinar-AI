"""Local scoring harness using sim-only (input-only) columns + truth from sim.

For each segment:
  - load the sim-only sim.csv (8 input columns)
  - run a model's predict() on it (mirrors the grading contract)
  - load truth (yaw_rate_meas_rads) from the matching sim/ file
  - accumulate sample yaw-rate RMSE and pooled-CTE RMSE

Outputs per-platform and overall pooled metrics.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-08")
SHARED = ROOT / "_shared"
sys.path.insert(0, str(SHARED))
from traj_metrics import cte_rmse_segment  # noqa: E402


SIM_ONLY = ROOT / "data" / "sim-only" / "segments"
SIM_TRUTH = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]


def load_predict(predict_path: str, func: str = "predict"):
    spec = importlib.util.spec_from_file_location("agent_predict", predict_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func)


def iter_segments(platform: str, root: Path = SIM_ONLY):
    base = root / platform
    if not base.exists():
        return
    for sim_csv in base.rglob("sim.csv"):
        yield sim_csv


def truth_path_for(sim_only_csv: Path) -> Path:
    rel = sim_only_csv.relative_to(SIM_ONLY)
    return SIM_TRUTH / rel


def score_model(predict_fn, limit_per_platform: int | None = None, skip_platforms: tuple[str, ...] = ("TESLA_MODEL_3",)):
    rows = []
    total_yaw_sq = 0.0
    total_yaw_n = 0
    total_cte_sumsq = 0.0
    total_cte_bins = 0
    per_platform = {}
    for platform in PLATFORMS:
        if platform in skip_platforms:
            continue
        p_yaw_sq = 0.0
        p_yaw_n = 0
        p_cte_sumsq = 0.0
        p_cte_bins = 0
        n_seg = 0
        for sim_csv in iter_segments(platform):
            truth_csv = truth_path_for(sim_csv)
            if not truth_csv.exists():
                continue
            try:
                sim_df = pd.read_csv(sim_csv)
                truth_df = pd.read_csv(truth_csv, usecols=["yaw_rate_meas_rads"])
            except Exception:
                continue
            if "yaw_rate_meas_rads" not in truth_df.columns:
                continue
            if len(sim_df) != len(truth_df):
                continue
            if limit_per_platform is not None and n_seg >= limit_per_platform:
                break
            try:
                out = predict_fn(sim_df, platform)
            except Exception as e:
                print(f"predict error {platform} {sim_csv.parent.name}: {e}", file=sys.stderr)
                continue
            yr_pred = np.asarray(out["yaw_rate_pred_rads"], dtype=float)
            yr_truth = truth_df["yaw_rate_meas_rads"].to_numpy(dtype=float)
            mask = np.isfinite(yr_pred) & np.isfinite(yr_truth)
            if not mask.any():
                continue
            err = yr_pred[mask] - yr_truth[mask]
            p_yaw_sq += float((err * err).sum())
            p_yaw_n += int(mask.sum())

            t = sim_df["t_s"].to_numpy(dtype=float)
            v = sim_df["v_mps"].to_numpy(dtype=float)
            sum_sq, n_bins, _ = cte_rmse_segment(t, v, yr_truth, yr_pred)
            p_cte_sumsq += sum_sq
            p_cte_bins += n_bins
            n_seg += 1

        if p_yaw_n > 0:
            per_platform[platform] = {
                "yaw_rmse": math.sqrt(p_yaw_sq / p_yaw_n),
                "cte_rmse": math.sqrt(p_cte_sumsq / p_cte_bins) if p_cte_bins > 0 else float("nan"),
                "n_seg": n_seg,
                "n_samp": p_yaw_n,
            }
            total_yaw_sq += p_yaw_sq
            total_yaw_n += p_yaw_n
            total_cte_sumsq += p_cte_sumsq
            total_cte_bins += p_cte_bins

    pooled = {
        "yaw_rmse": math.sqrt(total_yaw_sq / total_yaw_n) if total_yaw_n > 0 else float("nan"),
        "cte_rmse": math.sqrt(total_cte_sumsq / total_cte_bins) if total_cte_bins > 0 else float("nan"),
    }
    return pooled, per_platform


def fmt(p, pp):
    s = [f"POOLED: yaw_rmse={p['yaw_rmse']:.6f}  cte_rmse={p['cte_rmse']:.4f}"]
    for k, v in pp.items():
        s.append(f"  {k}: yaw={v['yaw_rmse']:.6f}  cte={v['cte_rmse']:.4f}  n_seg={v['n_seg']}")
    return "\n".join(s)


if __name__ == "__main__":
    path = sys.argv[1]
    fn = sys.argv[2] if len(sys.argv) > 2 else "predict"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    predict_fn = load_predict(path, fn)
    pooled, pp = score_model(predict_fn, limit_per_platform=limit)
    print(fmt(pooled, pp))
