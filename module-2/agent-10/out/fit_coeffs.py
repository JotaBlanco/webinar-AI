"""Fit per-platform steady-state bicycle coefficients.

Model:
    yaw_rate = v * tan(gain * delta_road + delta0) / (L_eff + K * v^2)

Fitted on route-grouped train split, validated on dev split.
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

SIM = ROOT / "data" / "sim" / "segments"
SIM_ONLY = ROOT / "data" / "sim-only" / "segments"

TRUTH_COL_BY_PLATFORM = {
    "TESLA_MODEL_3": "psi_dot_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
}


def list_segments():
    return sorted(SIM.glob("*/*/*/*/sim.csv"))


def route_split(paths, seed=0, dev_frac=0.2):
    by_plat = defaultdict(lambda: defaultdict(list))
    for p in paths:
        by_plat[p.parts[-5]][p.parts[-3]].append(p)
    train, dev = [], []
    rng = random.Random(seed)
    for plat, routes in by_plat.items():
        keys = sorted(routes.keys())
        rng.shuffle(keys)
        n_dev = max(1, int(len(keys) * dev_frac))
        dev_routes = set(keys[:n_dev])
        for r, paths_ in routes.items():
            (dev if r in dev_routes else train).extend(paths_)
    return train, dev


def load_for_fit(paths_for_plat, truth_col, v_min=3.0):
    deltas, vs, yrs = [], [], []
    for p in paths_for_plat:
        try:
            df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps", truth_col])
        except (ValueError, KeyError):
            continue
        m = (df["v_mps"] > v_min).to_numpy() & np.isfinite(df[truth_col].to_numpy())
        if not m.any():
            continue
        deltas.append(df.loc[m, "delta_road_rad"].to_numpy())
        vs.append(df.loc[m, "v_mps"].to_numpy())
        yrs.append(df.loc[m, truth_col].to_numpy())
    return (np.concatenate(deltas) if deltas else np.array([]),
            np.concatenate(vs) if vs else np.array([]),
            np.concatenate(yrs) if yrs else np.array([]))


def fit_platform(d, v, yr, init=(3.0, 0.002, 0.0, 1.0)):
    if len(d) < 100:
        return None
    def residual(p):
        L, K, d0, g = p
        L = max(L, 0.5)
        denom = L + K * v * v
        # avoid div-by-zero; clamp denom positive
        denom = np.where(denom > 0.1, denom, 0.1)
        return (v * np.tan(g * d + d0)) / denom - yr
    res = least_squares(residual, init, max_nfev=500)
    L, K, d0, g = res.x
    pred = (v * np.tan(g * d + d0)) / np.maximum(L + K * v * v, 0.1)
    rmse = float(np.sqrt(np.mean((pred - yr) ** 2)))
    return {"L": float(L), "K": float(K), "delta0": float(d0), "gain": float(g),
            "fit_rmse": rmse, "n_samples": int(len(d))}


def score_dev(coeffs_by_plat, dev_paths, v_thresh=2.0):
    yaw_ss, yaw_n = 0.0, 0
    cte_ss, cte_n = 0.0, 0
    per = {}
    for p in dev_paths:
        plat = p.parts[-5]
        truth_col = TRUTH_COL_BY_PLATFORM[plat]
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if truth_col not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        yr_t = df[truth_col].to_numpy(float)
        c = coeffs_by_plat.get(plat)
        if c is None:
            yr_p = (v / 2.875) * np.tan(d)
        else:
            denom = np.maximum(c["L"] + c["K"] * v * v, 0.1)
            yr_p = (v * np.tan(c["gain"] * d + c["delta0"])) / denom
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue
        m = v > v_thresh
        if m.any():
            r = yr_p[m] - yr_t[m]
            yaw_ss += float((r ** 2).sum())
            yaw_n += int(m.sum())
            pd_ = per.setdefault(plat, {"ys": 0.0, "yn": 0, "cs": 0.0, "cn": 0})
            pd_["ys"] += float((r ** 2).sum())
            pd_["yn"] += int(m.sum())
        cte = cte_diagnostics_segment(t, v, yr_t, yr_p)
        cte_ss += cte["sum_sq_m2"]
        cte_n += cte["n_bins"]
        pd_ = per.setdefault(plat, {"ys": 0.0, "yn": 0, "cs": 0.0, "cn": 0})
        pd_["cs"] += cte["sum_sq_m2"]
        pd_["cn"] += cte["n_bins"]
    return {
        "yaw_rmse": math.sqrt(yaw_ss / yaw_n) if yaw_n else float("nan"),
        "cte_rmse": math.sqrt(cte_ss / cte_n) if cte_n else float("nan"),
        "per_platform": {
            pf: {"yaw_rmse": math.sqrt(d["ys"] / d["yn"]) if d["yn"] else float("nan"),
                 "cte_rmse": math.sqrt(d["cs"] / d["cn"]) if d["cn"] else float("nan")}
            for pf, d in per.items()
        },
    }


def main():
    all_paths = list_segments()
    train_paths, dev_paths = route_split(all_paths, seed=0, dev_frac=0.2)
    print(f"Total: {len(all_paths)}  train: {len(train_paths)}  dev: {len(dev_paths)}")

    coeffs = {}
    for plat, truth_col in TRUTH_COL_BY_PLATFORM.items():
        plat_train = [p for p in train_paths if p.parts[-5] == plat]
        d, v, yr = load_for_fit(plat_train, truth_col)
        print(f"{plat}: train samples={len(d)}")
        fit = fit_platform(d, v, yr)
        if fit is None:
            print(f"  fit FAILED for {plat}")
            continue
        coeffs[plat] = {k: fit[k] for k in ("L", "K", "delta0", "gain")}
        print(f"  fit: L={fit['L']:.4f}  K={fit['K']:.6f}  d0={fit['delta0']:+.5f}  gain={fit['gain']:.4f}  train_rmse={fit['fit_rmse']:.5f}")

    # Score on dev
    print("\nDev scores:")
    dev_res = score_dev(coeffs, dev_paths)
    print(f"  pooled yaw_rmse: {dev_res['yaw_rmse']:.6f} rad/s")
    print(f"  pooled cte_rmse: {dev_res['cte_rmse']:.4f} m")
    for pf, m in dev_res["per_platform"].items():
        print(f"  {pf}: yaw={m['yaw_rmse']:.5f}  cte={m['cte_rmse']:.3f}")

    # Save
    out = {
        "coeffs": coeffs,
        "dev_score": dev_res,
        "n_train": len(train_paths),
        "n_dev": len(dev_paths),
    }
    (ROOT / "out" / "coeffs.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {ROOT / 'out' / 'coeffs.json'}")


if __name__ == "__main__":
    main()
