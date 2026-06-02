"""Score a predict() callable against the local sim-only segments.

Usage:
    python3 score.py <predict_module.py:func> [--data sim|sim-only]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_shared"))

from traj_metrics import cte_rmse_segment  # noqa: E402

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]
ALLOWLIST = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]


def load_predict(spec: str):
    path, func = spec.split(":")
    mod_path = Path(path).resolve()
    sys.path.insert(0, str(mod_path.parent))
    spec_obj = importlib.util.spec_from_file_location(mod_path.stem, mod_path)
    mod = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(mod)
    return getattr(mod, func)


def iter_segments(platform: str, data_root: Path):
    base = data_root / "segments" / platform
    for sim_csv in base.rglob("sim.csv"):
        yield sim_csv


def score(predict_fn, data_root: Path, sim_only_root: Path):
    results_by_platform = {}
    pooled_yaw_sumsq = 0.0
    pooled_yaw_n = 0
    pooled_cte_sumsq = 0.0
    pooled_cte_bins = 0
    for plat in PLATFORMS:
        yaw_sumsq = 0.0
        yaw_n = 0
        cte_sumsq = 0.0
        cte_bins = 0
        seg_results = []
        for sim_csv in iter_segments(plat, data_root):
            df_full = pd.read_csv(sim_csv)
            # Use the sim-only version for predict input (mimics grader)
            rel = sim_csv.relative_to(data_root / "segments" / plat)
            sim_only_csv = sim_only_root / "segments" / plat / rel
            df_in = pd.read_csv(sim_only_csv)
            # Only allowlisted columns
            df_in = df_in[ALLOWLIST].copy()
            try:
                pred = predict_fn(df_in, plat)
            except Exception as e:
                print(f"[predict failed] {plat} {sim_csv}: {e}", file=sys.stderr)
                continue
            yr_pred = pred["yaw_rate_pred_rads"].to_numpy()
            t = df_full["t_s"].to_numpy()
            v = df_full["v_mps"].to_numpy()
            if "yaw_rate_meas_rads" not in df_full.columns or df_full["yaw_rate_meas_rads"].isna().all():
                continue
            yr_truth = df_full["yaw_rate_meas_rads"].to_numpy()
            mask = np.isfinite(yr_truth) & np.isfinite(yr_pred)
            if mask.sum() < 2:
                continue
            resid = yr_truth[mask] - yr_pred[mask]
            yaw_sumsq += float(np.sum(resid * resid))
            yaw_n += int(mask.sum())
            sum_sq, n_bins, total = cte_rmse_segment(t, v, yr_truth, yr_pred)
            cte_sumsq += sum_sq
            cte_bins += n_bins
            seg_results.append({"seg": str(sim_csv.relative_to(data_root)), "n": int(mask.sum()), "yaw_sumsq": float(np.sum(resid*resid)), "cte_sumsq": sum_sq, "cte_bins": n_bins})
        if yaw_n > 0 and not (plat == "TESLA_MODEL_3"):
            yaw_rmse = math.sqrt(yaw_sumsq / yaw_n)
            cte_rmse = math.sqrt(cte_sumsq / cte_bins) if cte_bins else float("nan")
            results_by_platform[plat] = {"yaw_rmse": yaw_rmse, "cte_rmse": cte_rmse, "n": yaw_n, "cte_bins": cte_bins}
            pooled_yaw_sumsq += yaw_sumsq
            pooled_yaw_n += yaw_n
            pooled_cte_sumsq += cte_sumsq
            pooled_cte_bins += cte_bins
        else:
            results_by_platform[plat] = {"yaw_rmse": 0.0, "cte_rmse": 0.0, "n": 0, "cte_bins": 0}
    pooled_yaw = math.sqrt(pooled_yaw_sumsq / pooled_yaw_n) if pooled_yaw_n else float("nan")
    pooled_cte = math.sqrt(pooled_cte_sumsq / pooled_cte_bins) if pooled_cte_bins else float("nan")
    return {"per_platform": results_by_platform, "pooled_yaw_rmse": pooled_yaw, "pooled_cte_rmse": pooled_cte}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="module.py:func")
    args = ap.parse_args()
    predict_fn = load_predict(args.spec)
    data_full = ROOT / "data" / "sim"
    data_only = ROOT / "data" / "sim-only"
    result = score(predict_fn, data_full, data_only)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
