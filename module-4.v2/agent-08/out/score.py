"""Local scorer: pooled yaw-rate RMSE + pooled CTE RMSE across all sim/ segments.

Uses sim/segments (full schema) for truth. For Tesla, truth channel is
'psi_dot_rads'; for others, 'yaw_rate_meas_rads'.

Hands the predict() function a sim_df restricted to the 8-column allowlist
to mimic the grader contract.
"""
from __future__ import annotations
import sys
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-08")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT))
from traj_metrics import cte_rmse_segment  # type: ignore

SIM_ROOT = ROOT / "data" / "sim" / "segments"

ALLOW = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
    "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
]

TRUTH_BY_PLATFORM = {
    "TESLA_MODEL_3": "psi_dot_rads",
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
}


def find_sims(platform_dir: Path):
    return sorted(platform_dir.rglob("sim.csv"))


def score_platform(predict_fn, platform: str, sim_paths=None, max_segs=None):
    plat_dir = SIM_ROOT / platform
    if sim_paths is None:
        sim_paths = find_sims(plat_dir)
    if max_segs:
        sim_paths = sim_paths[:max_segs]

    truth_col = TRUTH_BY_PLATFORM[platform]

    sum_sq_yr = 0.0
    n_yr = 0
    sum_sq_cte = 0.0
    n_cte = 0
    used = 0

    for p in sim_paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if truth_col not in df.columns:
            continue
        # Always pull the sim-only mirror to get the 8-column allowlist exactly.
        rel = p.relative_to(SIM_ROOT)
        simonly = ROOT / "data" / "sim-only" / "segments" / rel
        if not simonly.exists():
            continue
        df_so = pd.read_csv(simonly)
        # Truth (and any other cols we need) come from df; pred sim_df is df_so.
        sim_df = df_so[ALLOW].copy()
        try:
            out = predict_fn(sim_df, platform)
        except Exception as e:
            print(f"  predict failed on {p.name}: {e}")
            continue
        yr_pred = np.asarray(out["yaw_rate_pred_rads"].to_numpy(), dtype=float)
        yr_truth = df[truth_col].to_numpy(dtype=float)
        n = min(len(yr_pred), len(yr_truth))
        diff = yr_pred[:n] - yr_truth[:n]
        sum_sq_yr += float((diff * diff).sum())
        n_yr += n

        t = df["t_s"].to_numpy(dtype=float)[:n]
        v = df["v_mps"].to_numpy(dtype=float)[:n]
        s2, nb, _ = cte_rmse_segment(t, v, yr_truth[:n], yr_pred[:n])
        sum_sq_cte += s2
        n_cte += nb
        used += 1

    yr_rmse = math.sqrt(sum_sq_yr / n_yr) if n_yr else float("nan")
    cte_rmse = math.sqrt(sum_sq_cte / n_cte) if n_cte else float("nan")
    return {
        "platform": platform,
        "n_segs": used,
        "n_yr_samples": n_yr,
        "n_cte_bins": n_cte,
        "yr_rmse": yr_rmse,
        "cte_rmse": cte_rmse,
        "sum_sq_yr": sum_sq_yr,
        "sum_sq_cte": sum_sq_cte,
    }


def score_all(predict_fn, platforms=None, max_segs=None):
    if platforms is None:
        platforms = list(TRUTH_BY_PLATFORM.keys())
    results = []
    tot_yr_sq = 0.0
    tot_yr_n = 0
    tot_cte_sq = 0.0
    tot_cte_n = 0
    for plat in platforms:
        r = score_platform(predict_fn, plat, max_segs=max_segs)
        results.append(r)
        tot_yr_sq += r["sum_sq_yr"]; tot_yr_n += r["n_yr_samples"]
        tot_cte_sq += r["sum_sq_cte"]; tot_cte_n += r["n_cte_bins"]
        print(f"  {plat:30s} segs={r['n_segs']:3d} yr_rmse={r['yr_rmse']:.6f} cte_rmse={r['cte_rmse']:.4f}")
    pooled_yr = math.sqrt(tot_yr_sq / tot_yr_n) if tot_yr_n else float("nan")
    pooled_cte = math.sqrt(tot_cte_sq / tot_cte_n) if tot_cte_n else float("nan")
    print(f"  POOLED:                       yr_rmse={pooled_yr:.6f} cte_rmse={pooled_cte:.4f}")
    return {"per_platform": results, "pooled_yr_rmse": pooled_yr, "pooled_cte_rmse": pooled_cte}


if __name__ == "__main__":
    import importlib.util
    target = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "code" / "v1_baseline.py")
    fn_name = sys.argv[2] if len(sys.argv) > 2 else "predict"
    spec = importlib.util.spec_from_file_location("mod", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, fn_name)
    max_segs = int(sys.argv[3]) if len(sys.argv) > 3 else None
    print(f"Scoring {target}::{fn_name}, max_segs={max_segs}")
    score_all(fn, max_segs=max_segs)
