"""Local scoring harness.

Discovers segments under data/sim-only/segments/, calls predict() with the
input-only schema (mimics grading), and uses data/sim/segments/ truth to
compute yaw RMSE and pooled distance-resampled CTE RMSE.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-10")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment  # noqa: E402


SIM_ONLY_COLS = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
    "a_long_mps2", "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads",
]


def load_predict(path: Path):
    spec = importlib.util.spec_from_file_location("user_predict", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.predict


def find_segments(root: Path):
    """Yield (platform, seg_id, sim.csv path) under root/segments/."""
    segs_root = root / "segments"
    for plat_dir in sorted(segs_root.iterdir()):
        if not plat_dir.is_dir():
            continue
        for p in sorted(plat_dir.rglob("sim.csv")):
            rel = p.relative_to(plat_dir).parent
            yield plat_dir.name, str(rel), p


def score(predict_path: Path, platforms=None, max_segs=None, verbose=False):
    predict = load_predict(predict_path)
    sim_root = ROOT / "data" / "sim"  # truth
    sim_only_root = ROOT / "data" / "sim-only"  # input

    per_platform = {}
    pooled_sum_sq_yaw = 0.0
    pooled_n_yaw = 0
    pooled_sum_sq_cte = 0.0
    pooled_n_cte = 0

    for plat, seg_id, sim_only_path in find_segments(sim_only_root):
        if platforms is not None and plat not in platforms:
            continue
        truth_path = sim_root / "segments" / plat / seg_id / "sim.csv"
        if not truth_path.exists():
            continue

        df_in = pd.read_csv(sim_only_path)
        # Schema sanity — drop any non-allowed columns to mimic grader strictness.
        missing = [c for c in SIM_ONLY_COLS if c not in df_in.columns]
        if missing:
            if verbose:
                print(f"SKIP {plat}/{seg_id}: missing input cols {missing}")
            continue
        df_in = df_in[SIM_ONLY_COLS].copy()

        df_truth = pd.read_csv(truth_path)
        if "yaw_rate_meas_rads" not in df_truth.columns:
            # Tesla — no truth. Skip from scoring.
            continue

        try:
            out = predict(df_in, plat)
        except Exception as e:
            if verbose:
                print(f"ERROR {plat}/{seg_id}: {e}")
            continue

        if "yaw_rate_pred_rads" not in out.columns:
            continue
        yr_pred = out["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df_truth["yaw_rate_meas_rads"].to_numpy()
        t = df_in["t_s"].to_numpy()
        v = df_in["v_mps"].to_numpy()

        n = min(len(yr_pred), len(yr_truth))
        resid = yr_pred[:n] - yr_truth[:n]
        sum_sq_yaw = float((resid * resid).sum())
        sum_sq_cte, n_bins, total = cte_rmse_segment(t[:n], v[:n], yr_truth[:n], yr_pred[:n])

        pp = per_platform.setdefault(plat, {"yaw_sum_sq": 0.0, "yaw_n": 0,
                                            "cte_sum_sq": 0.0, "cte_n": 0,
                                            "n_segs": 0})
        pp["yaw_sum_sq"] += sum_sq_yaw
        pp["yaw_n"] += n
        pp["cte_sum_sq"] += sum_sq_cte
        pp["cte_n"] += n_bins
        pp["n_segs"] += 1

        pooled_sum_sq_yaw += sum_sq_yaw
        pooled_n_yaw += n
        pooled_sum_sq_cte += sum_sq_cte
        pooled_n_cte += n_bins

        if max_segs and pp["n_segs"] >= max_segs:
            # Per-platform cap. Continue but only for OTHER platforms.
            pass

    print(f"{'platform':<32} {'n':>3} {'yawRMSE':>10} {'cteRMSE':>10}")
    for plat, pp in sorted(per_platform.items()):
        yr = math.sqrt(pp["yaw_sum_sq"] / pp["yaw_n"]) if pp["yaw_n"] else float("nan")
        cr = math.sqrt(pp["cte_sum_sq"] / pp["cte_n"]) if pp["cte_n"] else float("nan")
        print(f"{plat:<32} {pp['n_segs']:>3} {yr:>10.6f} {cr:>10.4f}")
    yr_pool = math.sqrt(pooled_sum_sq_yaw / pooled_n_yaw) if pooled_n_yaw else float("nan")
    cr_pool = math.sqrt(pooled_sum_sq_cte / pooled_n_cte) if pooled_n_cte else float("nan")
    print(f"{'POOLED':<32} {'':>3} {yr_pool:>10.6f} {cr_pool:>10.4f}")
    return {"yaw_rmse": yr_pool, "cte_rmse": cr_pool, "per_platform": per_platform}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("predict", type=Path)
    ap.add_argument("--platforms", nargs="*", default=None)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    score(args.predict, platforms=args.platforms, verbose=args.verbose)
