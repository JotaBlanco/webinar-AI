"""Fit understeer K and steady-state delta scale per platform.

Model: yr = v * (s * delta - d0) / (L + K * v^2)

We fit (K, s, d0) per platform to minimise weighted SSE on yaw_rate residual.
Weighting filters v > 2 m/s.

Splits: route-grouped train/dev split (80/20). Trains on train, reports on both.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-06")
DATA = ROOT / "data" / "sim" / "segments"

# wheelbase by platform (from code/parameters.py)
WHEELBASE = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.00,  # known wheelbase
}


def load_all(plat):
    pdir = DATA / plat
    segs = []
    for p in sorted(pdir.glob("*/*/*/sim.csv")):
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            if "psi_dot_rads" in df.columns:
                df["yaw_rate_meas_rads"] = df["psi_dot_rads"]
            else:
                continue
        if "delta_road_rad" not in df.columns or "v_mps" not in df.columns:
            continue
        df = df[["t_s","v_mps","delta_road_rad","yaw_rate_meas_rads"]].copy()
        df["route"] = p.parts[-3]
        df["seg"] = str(p)
        segs.append(df)
    return segs


def fit_platform(segs, L):
    # Build training arrays (pool all segs, filter v>2)
    cat = pd.concat(segs, ignore_index=True)
    cat = cat[cat["v_mps"] > 2.0]
    v = cat["v_mps"].to_numpy(float)
    d = cat["delta_road_rad"].to_numpy(float)
    yr = cat["yaw_rate_meas_rads"].to_numpy(float)

    # Initial: KS formula tan ≈ delta for small angles; here we use delta directly.
    # Model: yr_hat = v * (s*d - d0) / (L + K*v^2)
    def predict(p):
        K, s, d0 = p
        return v * (s * d - d0) / (L + K * v * v)
    def loss(p):
        return float(np.mean((predict(p) - yr) ** 2))
    # Init
    x0 = np.array([0.002, 1.0, 0.0])
    res = minimize(loss, x0, method="Nelder-Mead", options={"xatol":1e-7,"fatol":1e-10,"maxiter":5000})
    return res.x.tolist(), float(res.fun)


def score_platform(segs, L, params, v_min=2.0):
    K, s, d0 = params
    yaw_sq = 0.0; yaw_n = 0
    cte_sq = 0.0; cte_n = 0
    for df in segs:
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        yr_t = df["yaw_rate_meas_rads"].to_numpy(float)
        yr_p = v * (s * d - d0) / (L + K * v * v)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue
        mask = v > v_min
        r = yr_p[mask] - yr_t[mask]
        yaw_sq += float((r*r).sum()); yaw_n += int(mask.sum())
        cte = cte_diagnostics_segment(t, v, yr_t, yr_p)
        cte_sq += cte["sum_sq_m2"]; cte_n += cte["n_bins"]
    return {
        "yaw_rmse": math.sqrt(yaw_sq/yaw_n) if yaw_n else float("nan"),
        "cte_rmse": math.sqrt(cte_sq/cte_n) if cte_n else float("nan"),
        "n_yaw": yaw_n, "n_cte": cte_n,
    }


def score_baseline_platform(segs, L, v_min=2.0):
    # V0 baseline: yr = (v/L) * tan(delta)
    yaw_sq = 0.0; yaw_n = 0
    cte_sq = 0.0; cte_n = 0
    for df in segs:
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        yr_t = df["yaw_rate_meas_rads"].to_numpy(float)
        yr_p = (v / L) * np.tan(d)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue
        mask = v > v_min
        r = yr_p[mask] - yr_t[mask]
        yaw_sq += float((r*r).sum()); yaw_n += int(mask.sum())
        cte = cte_diagnostics_segment(t, v, yr_t, yr_p)
        cte_sq += cte["sum_sq_m2"]; cte_n += cte["n_bins"]
    return {
        "yaw_rmse": math.sqrt(yaw_sq/yaw_n) if yaw_n else float("nan"),
        "cte_rmse": math.sqrt(cte_sq/cte_n) if cte_n else float("nan"),
        "n_yaw": yaw_n, "n_cte": cte_n,
    }


def main():
    import random
    coefs = {}
    summary = {}
    for plat in sorted(WHEELBASE.keys()):
        if not (DATA / plat).exists():
            continue
        L = WHEELBASE[plat]
        print(f"\n=== {plat} (L={L}) ===")
        segs = load_all(plat)
        print(f"  loaded {len(segs)} segments")
        if not segs:
            continue
        # Route-grouped train/dev split
        routes = sorted(set(df["route"].iloc[0] for df in segs))
        random.Random(42).shuffle(routes)
        n_train = max(1, int(0.8 * len(routes)))
        train_routes = set(routes[:n_train])
        train_segs = [df for df in segs if df["route"].iloc[0] in train_routes]
        dev_segs = [df for df in segs if df["route"].iloc[0] not in train_routes]
        print(f"  train: {len(train_segs)} segs ({len(train_routes)} routes) | dev: {len(dev_segs)} segs")
        params, loss = fit_platform(train_segs, L)
        K, s, d0 = params
        print(f"  fit: K={K:.5g}  s={s:.5f}  d0={d0:.6g}  (train MSE={loss:.6g})")
        base_train = score_baseline_platform(train_segs, L)
        base_dev = score_baseline_platform(dev_segs, L) if dev_segs else None
        fit_train = score_platform(train_segs, L, params)
        fit_dev = score_platform(dev_segs, L, params) if dev_segs else None
        print(f"  V0 train: yaw={base_train['yaw_rmse']:.5f}  cte={base_train['cte_rmse']:.2f}m")
        print(f"  V1 train: yaw={fit_train['yaw_rmse']:.5f}  cte={fit_train['cte_rmse']:.2f}m")
        if base_dev:
            print(f"  V0  dev: yaw={base_dev['yaw_rmse']:.5f}  cte={base_dev['cte_rmse']:.2f}m")
            print(f"  V1  dev: yaw={fit_dev['yaw_rmse']:.5f}  cte={fit_dev['cte_rmse']:.2f}m")
        coefs[plat] = {"L": L, "K": K, "s": s, "d0": d0}
        summary[plat] = {"v0_dev": base_dev, "v1_dev": fit_dev}
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "coefs.json").write_text(json.dumps(coefs, indent=2))
    (out / "fit_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\nWrote", out / "coefs.json")

if __name__ == "__main__":
    main()
