"""Fast M1 (linear dynamic single-track) fit on a sub-sampled train set.

CPU is contended (parallel agents). Full-train Nelder-Mead with 1187 RK4
runs per call is too slow. Strategy:

- preload a stratified sub-sample of ~30 segments per platform (longer
  segments preferred for signal density)
- scale params to unit O(1) for L-BFGS-B
- optimise yaw RMSE on train, evaluate on dev once

Writes coeffs.json next to the m1 model.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "phases" / "3-implement" / "models" / "m1-linear-dynamic-st"))

from _shared.frozen_split import train_paths, dev_paths
from _shared.physics_core import prior, V_MIN_DYNAMIC, safe_dt
from model import predict_factory

PLATFORMS = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]

MAX_TRAIN_SEGS_PER_PLATFORM = 30
TRUTH_COL = "yaw_rate_meas_rads"


def platform_of(p: Path) -> str:
    return p.resolve().parents[3].name


def bucket(paths):
    out = defaultdict(list)
    for p in paths:
        out[platform_of(p)].append(p)
    return out


def preload(paths):
    out = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if TRUTH_COL not in df.columns or "v_mps" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        if len(t) < 50 or np.any(np.diff(t) <= 0):
            continue
        # We only need the columns predict_factory uses
        sim_df = df[["t_s", "delta_road_rad", "v_mps", "yaw_rate_pred_rads"]].copy()
        out.append({
            "sim_df": sim_df,
            "truth": df[TRUTH_COL].to_numpy(float),
            "v": df["v_mps"].to_numpy(float),
            "n": len(t),
        })
    return out


def yaw_rmse(preloaded, predict_fn, v_floor=2.0):
    sse = 0.0
    n = 0
    for s in preloaded:
        try:
            yp = predict_fn(s["sim_df"])
        except Exception:
            return float("inf")
        yp = np.asarray(yp, float)
        if yp.shape != s["truth"].shape or not np.all(np.isfinite(yp)):
            return float("inf")
        mask = s["v"] > v_floor
        sse += float(np.sum((yp[mask] - s["truth"][mask]) ** 2))
        n += int(mask.sum())
    if n == 0:
        return float("inf")
    return math.sqrt(sse / n)


def fit_platform(platform, train_pre, dev_pre):
    p0 = prior(platform)
    # log-scale variables for stability across 1e3..1e6
    x0 = np.log(np.array([p0["C_alpha_f"], p0["C_alpha_r"], p0["I_z"]]))
    # bounds: 0.3x .. 3x in linear space ~ log(0.3)..log(3) shift
    bounds = [
        (x0[0] + math.log(0.3), x0[0] + math.log(3.0)),
        (x0[1] + math.log(0.3), x0[1] + math.log(3.0)),
        (x0[2] + math.log(0.4), x0[2] + math.log(2.5)),
    ]

    def fun(x):
        c = {
            "C_alpha_f": float(np.exp(x[0])),
            "C_alpha_r": float(np.exp(x[1])),
            "I_z":       float(np.exp(x[2])),
        }
        fn = predict_factory(platform, c)
        return yaw_rmse(train_pre, fn)

    # Use Nelder-Mead in log space — derivative-free but stable
    res = minimize(
        fun, x0, method="Nelder-Mead",
        options={"maxiter": 200, "xatol": 1e-3, "fatol": 1e-5, "disp": False},
    )
    coeffs = {
        "C_alpha_f": float(np.exp(res.x[0])),
        "C_alpha_r": float(np.exp(res.x[1])),
        "I_z":       float(np.exp(res.x[2])),
    }
    train_obj = float(res.fun)
    fn = predict_factory(platform, coeffs)
    dev_obj = yaw_rmse(dev_pre, fn)
    return coeffs, train_obj, dev_obj, int(res.nit), bool(res.success)


def main():
    train = train_paths()
    dev = dev_paths()
    print(f"split: {len(train)} train, {len(dev)} dev")

    train_by = bucket(train)
    dev_by = bucket(dev)

    coeffs_path = ROOT / "phases" / "3-implement" / "models" / "m1-linear-dynamic-st" / "coeffs.json"
    with coeffs_path.open() as f:
        all_coeffs = json.load(f)

    results = {}
    for plat in PLATFORMS:
        tr = train_by.get(plat, [])
        # prefer longer segments — sort by file size desc as a quick proxy
        tr_sorted = sorted(tr, key=lambda p: -p.stat().st_size)[:MAX_TRAIN_SEGS_PER_PLATFORM]
        dv = dev_by.get(plat, [])

        print(f"\n=== {plat} ===")
        print(f"  train sub: {len(tr_sorted)} of {len(tr)} segments")
        print(f"  dev      : {len(dv)} segments")
        train_pre = preload(tr_sorted)
        dev_pre = preload(dv)
        print(f"  preloaded: {len(train_pre)} train, {len(dev_pre)} dev")

        coeffs, t_obj, d_obj, nit, ok = fit_platform(plat, train_pre, dev_pre)
        print(f"  -> n_iter={nit}, success={ok}")
        print(f"     C_alpha_f={coeffs['C_alpha_f']:.0f}  C_alpha_r={coeffs['C_alpha_r']:.0f}  I_z={coeffs['I_z']:.0f}")
        print(f"     train_obj={t_obj:.6f}  dev_obj={d_obj:.6f}")

        all_coeffs[plat] = coeffs
        results[plat] = {
            "coeffs": coeffs,
            "train_obj": t_obj,
            "dev_obj": d_obj,
            "n_iter": nit,
            "success": ok,
        }

    with coeffs_path.open("w") as f:
        json.dump(all_coeffs, f, indent=2)
    print(f"\nwrote {coeffs_path}")

    with (HERE / "fast_fit_results.json").open("w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
