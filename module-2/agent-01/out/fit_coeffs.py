"""Fit per-platform coefficients for the bicycle-with-understeer affine model.

Model: yr_pred = gain * (v * delta_road / (L + K * v^2)) + bias

Fits a 2D grid over K then closed-form linear regression for (gain, bias).
Also fits a richer linear model in [v*tan(delta), v*delta, v^2*delta, delta, bias].

Saves a coefficients JSON.

Route-grouped train/dev split. Reports both train and dev RMSE.
"""
from __future__ import annotations
import sys, glob, math, json, hashlib
from pathlib import Path
sys.path.insert(0, "_shared")
import pandas as pd
import numpy as np

L_BY_PLAT = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          2.9,   # unknown; use sedan-ish
    "TESLA_MODEL_3":            2.875,
}

def route_hash_bucket(route: str, n_buckets: int = 5) -> int:
    h = int(hashlib.md5(route.encode()).hexdigest(), 16)
    return h % n_buckets

def fit_platform(paths, plat):
    L = L_BY_PLAT[plat]
    # train / dev: 80/20 by route hash
    train_dfs, dev_dfs = [], []
    for p in paths:
        route = p.split("/")[-3]
        bucket = route_hash_bucket(route, 5)
        df = pd.read_csv(p, usecols=["t_s","v_mps","delta_road_rad","yaw_rate_meas_rads"])
        if df.shape[0] < 50: continue
        mask = df["v_mps"] > 2.0
        if mask.sum() < 50: continue
        sub = df[mask].copy()
        if bucket == 0:
            dev_dfs.append(sub)
        else:
            train_dfs.append(sub)
    train = pd.concat(train_dfs, ignore_index=True)
    dev   = pd.concat(dev_dfs,   ignore_index=True)

    def feat(df):
        v = df["v_mps"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        return v, d, df["yaw_rate_meas_rads"].to_numpy(float)

    v_tr, d_tr, y_tr = feat(train)
    v_dv, d_dv, y_dv = feat(dev)

    # Grid-search K
    best = (None, 1e9)
    Ks = np.linspace(-0.005, 0.02, 51)
    for K in Ks:
        pr = v_tr * d_tr / (L + K * v_tr * v_tr)
        A = np.column_stack([pr, np.ones_like(pr)])
        coef, *_ = np.linalg.lstsq(A, y_tr, rcond=None)
        pred = A @ coef
        rms = math.sqrt(np.mean((pred - y_tr) ** 2))
        if rms < best[1]:
            best = ((K, coef[0], coef[1]), rms)
    K, gain, bias = best[0]

    # Eval on dev
    pr_dv = v_dv * d_dv / (L + K * v_dv * v_dv)
    pred_dv = gain * pr_dv + bias
    rmse_dv = math.sqrt(np.mean((pred_dv - y_dv) ** 2))

    # Also baseline V0 RMSE on dev
    v0_dv = v_dv * np.tan(d_dv) / L
    rmse_v0_dv = math.sqrt(np.mean((v0_dv - y_dv) ** 2))

    return {
        "L": L,
        "K": float(K),
        "gain": float(gain),
        "bias": float(bias),
        "train_n": int(len(y_tr)),
        "dev_n": int(len(y_dv)),
        "train_rmse": float(best[1]),
        "dev_rmse": float(rmse_dv),
        "dev_v0_rmse": float(rmse_v0_dv),
    }


def main():
    ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01")
    paths = sorted(ROOT.glob("data/sim/segments/*/*/*/*/sim.csv"))
    paths = [str(p) for p in paths if "TESLA" not in str(p)]
    by_plat = {}
    for p in paths:
        plat = p.split("/")[-5]
        by_plat.setdefault(plat, []).append(p)
    coeffs = {}
    for plat, ps in by_plat.items():
        print(f"Fitting {plat} n_paths={len(ps)}")
        c = fit_platform(ps, plat)
        coeffs[plat] = c
        print(f"  K={c['K']:.4f} gain={c['gain']:.4f} bias={c['bias']:+.5f}  "
              f"train_rmse={c['train_rmse']:.5f} dev_rmse={c['dev_rmse']:.5f} v0_dev={c['dev_v0_rmse']:.5f}")
    # Tesla: passthrough V0 (no truth)
    coeffs["TESLA_MODEL_3"] = {
        "L": 2.875, "K": 0.0, "gain": 1.0, "bias": 0.0,
        "passthrough": True,
        "note": "Tesla sim/ has no ground-truth yaw rate (psi_dot_rads is the V0 output itself). "
                "Use V0 KS formula as predict.",
    }
    out_path = ROOT / "final-model" / "coeffs.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out_path}")

if __name__ == "__main__":
    main()
