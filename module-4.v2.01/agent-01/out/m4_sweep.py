"""Sweep sigma per platform for M4 (relaxation length).

M4 is V1 with distance-domain phase lag instead of time-domain.
Sweep sigma in {0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0} per platform
on train, pick best per-platform, evaluate combined model on dev.
"""
from __future__ import annotations
import json, math, sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
M4_DIR = ROOT / "phases" / "3-implement" / "models" / "m4-relaxation-length"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(M4_DIR))

from _shared.frozen_split import train_paths, dev_paths
from model import predict_factory

TRUTH_COL = "yaw_rate_meas_rads"
V_FLOOR = 2.0

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def platform_of(p): return Path(p).resolve().parents[3].name


def preload_for(plat, paths):
    out = []
    for p in paths:
        if platform_of(p) != plat:
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if TRUTH_COL not in df.columns:
            continue
        sim_df = df[["t_s", "delta_road_rad", "v_mps", "yaw_rate_pred_rads"]].copy()
        out.append({
            "sim_df": sim_df,
            "truth": df[TRUTH_COL].to_numpy(float),
            "v": df["v_mps"].to_numpy(float),
        })
    return out


def yaw_rmse(preloaded, fn):
    sse = 0.0; n = 0
    for s in preloaded:
        try:
            y = fn(s["sim_df"])
        except Exception:
            return float("inf")
        y = np.asarray(y, float)
        if y.shape != s["truth"].shape or not np.all(np.isfinite(y)):
            return float("inf")
        m = s["v"] > V_FLOOR
        sse += float(np.sum((y[m] - s["truth"][m]) ** 2))
        n += int(m.sum())
    return math.sqrt(sse / n) if n > 0 else float("inf")


def main():
    train = train_paths()
    dev = dev_paths()
    sigmas = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0]

    best_sigma = {}
    for plat in PLATFORMS:
        print(f"\n=== {plat} ===")
        tr_pre = preload_for(plat, train)
        dv_pre = preload_for(plat, dev)
        print(f"  train={len(tr_pre)} dev={len(dv_pre)}")
        best_s, best_obj = None, float("inf")
        print(f"  {'sigma':>6}  {'train':>10}  {'dev':>10}")
        for s in sigmas:
            fn = predict_factory(plat, {"sigma": s})
            tr_obj = yaw_rmse(tr_pre, fn)
            dv_obj = yaw_rmse(dv_pre, fn)
            print(f"  {s:>6.2f}  {tr_obj:>10.6f}  {dv_obj:>10.6f}")
            if tr_obj < best_obj:
                best_obj, best_s = tr_obj, s
        # Refine near best
        if 0 < best_s < 5.0:
            lo = max(0.0, best_s - 0.5)
            hi = best_s + 0.5
            for s in np.linspace(lo, hi, 11):
                fn = predict_factory(plat, {"sigma": float(s)})
                tr_obj = yaw_rmse(tr_pre, fn)
                if tr_obj < best_obj:
                    best_obj, best_s = tr_obj, float(s)
        print(f"  best by train: sigma={best_s:.3f}, train_obj={best_obj:.6f}")
        best_sigma[plat] = best_s

    # Write coeffs
    coeffs_path = M4_DIR / "coeffs.json"
    if coeffs_path.is_file():
        with coeffs_path.open() as f:
            cur = json.load(f)
    else:
        cur = {}
    for plat, s in best_sigma.items():
        cur[plat] = {"sigma": float(s)}
    with coeffs_path.open("w") as f:
        json.dump(cur, f, indent=2)
    print(f"\nwrote {coeffs_path}")
    with (HERE / "m4_best_sigma.json").open("w") as f:
        json.dump(best_sigma, f, indent=2)


if __name__ == "__main__":
    main()
