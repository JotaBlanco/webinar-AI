"""Local pooled scorer over data/sim/segments/ (all 4 platforms).

Usage: python3 score.py <predict_module_path>:predict
Imports the predict callable and pooled-scores it on sim segments using
truth from full-fidelity view but only the 8 allowlist columns are passed
into predict() (mimics grading contract).
"""
from __future__ import annotations
import sys, os, math, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _shared.traj_metrics import cte_rmse_segment

ALLOWLIST = [
    "t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
    "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads",
]

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5","TESLA_MODEL_3"]

def iter_sim_csvs(platform_dir: Path):
    for p in platform_dir.rglob("sim.csv"):
        yield p

def load_predict(spec: str):
    path, _, fn = spec.partition(":")
    fn = fn or "predict"
    p = Path(path)
    if not p.is_absolute():
        p = (ROOT / path).resolve()
    name = p.stem + "_mod"
    s = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return getattr(m, fn)

def score(predict_callable, segments_root=None, limit_per_platform=None):
    if segments_root is None:
        segments_root = ROOT / "data" / "sim" / "segments"
    results = {}
    pooled_yaw_sumsq = 0.0
    pooled_yaw_n = 0
    pooled_cte_sumsq = 0.0
    pooled_cte_bins = 0
    for platform in PLATFORMS:
        pdir = segments_root / platform
        if not pdir.exists():
            continue
        plat_y_sumsq = 0.0
        plat_y_n = 0
        plat_c_sumsq = 0.0
        plat_c_bins = 0
        n_segs = 0
        for csv in iter_sim_csvs(pdir):
            try:
                df = pd.read_csv(csv)
            except Exception:
                continue
            if "yaw_rate_meas_rads" not in df.columns:
                continue
            sim_in = df[[c for c in ALLOWLIST if c in df.columns]].copy()
            try:
                out = predict_callable(sim_in, platform)
            except Exception as e:
                print(f"predict error on {csv}: {e}", file=sys.stderr)
                continue
            yr_pred = np.asarray(out["yaw_rate_pred_rads"].to_numpy(), dtype=float)
            yr_truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
            mask = np.isfinite(yr_pred) & np.isfinite(yr_truth)
            if mask.sum() < 2:
                continue
            res = yr_pred[mask] - yr_truth[mask]
            plat_y_sumsq += float(np.sum(res*res))
            plat_y_n += int(mask.sum())
            t = df["t_s"].to_numpy(dtype=float)
            v = df["v_mps"].to_numpy(dtype=float)
            sumsq, nbins, total = cte_rmse_segment(t, v, yr_truth, yr_pred)
            plat_c_sumsq += sumsq
            plat_c_bins += nbins
            n_segs += 1
            if limit_per_platform is not None and n_segs >= limit_per_platform:
                break
        results[platform] = {
            "n_segments": n_segs,
            "yaw_rmse_rads": math.sqrt(plat_y_sumsq/plat_y_n) if plat_y_n else None,
            "cte_rmse_m": math.sqrt(plat_c_sumsq/plat_c_bins) if plat_c_bins else None,
            "n_samples": plat_y_n,
            "n_bins": plat_c_bins,
        }
        pooled_yaw_sumsq += plat_y_sumsq
        pooled_yaw_n += plat_y_n
        pooled_cte_sumsq += plat_c_sumsq
        pooled_cte_bins += plat_c_bins
    results["POOLED"] = {
        "yaw_rmse_rads": math.sqrt(pooled_yaw_sumsq/pooled_yaw_n) if pooled_yaw_n else None,
        "cte_rmse_m": math.sqrt(pooled_cte_sumsq/pooled_cte_bins) if pooled_cte_bins else None,
        "n_samples": pooled_yaw_n,
        "n_bins": pooled_cte_bins,
    }
    return results

if __name__ == "__main__":
    spec = sys.argv[1] if len(sys.argv) > 1 else "code/v1_baseline.py:predict_v1"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    fn = load_predict(spec)
    r = score(fn, limit_per_platform=limit)
    print(json.dumps(r, indent=2))
