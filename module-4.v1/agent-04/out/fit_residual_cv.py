"""Per-platform 5-fold segment-grouped CV: fit residual head + decide apply.

Strategy:
- Split segments deterministically into 5 folds.
- For each fold: fit on the other 4, score the held-out fold's pooled yaw RMSE
  with and without head.
- If CV-mean(with head) < CV-mean(without), apply=True else apply=False.
- Final fit on ALL segments for shipped coeffs.
- Test multiple feature sets / lambdas, pick best.
"""
from __future__ import annotations
import sys, json, hashlib, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import importlib.util as _iu
_spec = _iu.spec_from_file_location("v1b", ROOT/"code"/"v1_baseline.py")
_v1m = _iu.module_from_spec(_spec); _spec.loader.exec_module(_v1m)
predict_v1 = _v1m.predict_v1

ALLOWLIST = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]

FEATURE_SETS = {
    "minimal": ["delta","v_delta","yr_v1"],
    "rich":    ["delta","v_delta","v2_delta","yr_v1","v_yr_v1","a_long"],
    "midline": ["delta","v_delta","yr_v1","v_yr_v1"],
}

def build(df, platform):
    sim_in = df[[c for c in ALLOWLIST if c in df.columns]].copy()
    for c in ALLOWLIST:
        if c not in sim_in.columns:
            sim_in[c] = 0.0
    yr_v1 = predict_v1(sim_in, platform)["yaw_rate_pred_rads"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    a_long = df["a_long_mps2"].to_numpy() if "a_long_mps2" in df.columns else np.zeros(len(df))
    feats = {
        "delta": delta,
        "v_delta": v*delta,
        "v2_delta": (v*v)*delta,
        "yr_v1": yr_v1,
        "v_yr_v1": v*yr_v1,
        "a_long": a_long,
    }
    yr_truth = df["yaw_rate_meas_rads"].to_numpy()
    return feats, yr_v1, yr_truth

def fold_of(path, k=5):
    h = int(hashlib.md5(str(path).encode()).hexdigest()[:8], 16)
    return h % k

def gather_feats(segs, platform, names):
    Xs, ys_res, ys_v1 = [], [], []
    for p in segs:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        feats, yr_v1, yr_truth = build(df, platform)
        X = np.column_stack([feats[n] for n in names])
        m = np.isfinite(X).all(axis=1) & np.isfinite(yr_truth) & np.isfinite(yr_v1)
        Xs.append(X[m])
        ys_res.append((yr_truth-yr_v1)[m])
        ys_v1.append(yr_v1[m])
    if not Xs: return None
    return np.vstack(Xs), np.concatenate(ys_res), np.concatenate(ys_v1)

def ridge(X, y, lam):
    n, k = X.shape
    Xi = np.column_stack([np.ones(n), X])
    A = Xi.T @ Xi
    A[1:,1:] += lam*np.eye(k)
    return np.linalg.solve(A, Xi.T @ y)

def cv_score(platform, segs, names, lam=1.0, k=5):
    folds = [[] for _ in range(k)]
    for p in segs:
        folds[fold_of(p,k)].append(p)
    cv_v1, cv_head = [], []
    for i in range(k):
        val = folds[i]
        train = [p for j in range(k) if j!=i for p in folds[j]]
        gt = gather_feats(train, platform, names)
        gv = gather_feats(val, platform, names)
        if gt is None or gv is None: continue
        Xtr, rtr, _ = gt
        Xva, rva, yv1_va = gv
        w = ridge(Xtr, rtr, lam)
        Xi = np.column_stack([np.ones(len(Xva)), Xva])
        r_hat = Xi @ w
        rmse_v1 = math.sqrt(np.mean(rva**2))
        rmse_head = math.sqrt(np.mean((rva - r_hat)**2))
        cv_v1.append(rmse_v1); cv_head.append(rmse_head)
    return cv_v1, cv_head

def main():
    out = {}
    for plat in PLATFORMS:
        pdir = ROOT/"data"/"sim"/"segments"/plat
        segs = sorted(pdir.rglob("sim.csv"))
        print(f"\n=== {plat} ({len(segs)} segs) ===")
        best = None
        for fname, feats in FEATURE_SETS.items():
            for lam in [0.1, 1.0, 10.0, 100.0]:
                v1_rmses, head_rmses = cv_score(plat, segs, feats, lam=lam)
                v1_m = float(np.mean(v1_rmses)); v1_s = float(np.std(v1_rmses))
                hd_m = float(np.mean(head_rmses)); hd_s = float(np.std(head_rmses))
                gain = v1_m - hd_m
                print(f"  feats={fname:7s} lam={lam:6.1f}  V1={v1_m:.5f}±{v1_s:.5f}  head={hd_m:.5f}±{hd_s:.5f}  gain={gain:+.5f}")
                if best is None or hd_m < best["hd_m"]:
                    best = dict(features=feats, fname=fname, lam=lam, v1_m=v1_m, hd_m=hd_m, gain=gain)
        # Final fit on all data
        g = gather_feats(segs, plat, best["features"])
        Xall, res_all, _ = g
        w = ridge(Xall, res_all, lam=best["lam"])
        apply_head = best["gain"] > 0
        print(f"  ==> best feats={best['fname']} lam={best['lam']} apply={apply_head}")
        out[plat] = {
            "apply": bool(apply_head),
            "intercept": float(w[0]),
            "features": best["features"],
            "coefs": [float(x) for x in w[1:]],
            "cv_v1_rmse": best["v1_m"],
            "cv_head_rmse": best["hd_m"],
            "feature_set": best["fname"],
            "lambda": best["lam"],
        }
    coef_path = ROOT/"models"/"v2_residual_head"/"coeffs.json"
    coef_path.parent.mkdir(parents=True, exist_ok=True)
    coef_path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {coef_path}")

if __name__ == "__main__":
    main()
