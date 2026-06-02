"""Fit per-platform linear residual head on top of V1.

We learn yr_residual = yr_truth - yr_v1 from features that are *deterministic
functions of inputs* (allowlist) — i.e. delta_road_rad, v_mps, yr_v1 (which
itself is on the input allowlist as `yaw_rate_pred_rads` from V0; we also
compute V1 internally), a_long, accel_pedal, brake_pressed.

Train on a held-out 80% of segments per platform, validate on 20%.
Output: out/residual_coeffs.json with {platform: {feat: coef}} and intercept.
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

def build_features(df: pd.DataFrame, platform: str) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    sim_in = df[[c for c in ALLOWLIST if c in df.columns]].copy()
    yr_v1 = predict_v1(sim_in, platform)["yaw_rate_pred_rads"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    a_long = df.get("a_long_mps2", pd.Series(np.zeros(len(df)))).to_numpy()
    # Features (no constant — we add intercept):
    feats = {
        "delta": delta,
        "v_delta": v*delta,
        "v2_delta": (v*v)*delta,
        "yr_v1": yr_v1,
        "v_yr_v1": v*yr_v1,
        "a_long": a_long,
    }
    X = np.column_stack(list(feats.values()))
    feat_names = list(feats.keys())
    yr_truth = df["yaw_rate_meas_rads"].to_numpy()
    res = yr_truth - yr_v1
    return X, res, feat_names

def split_segments(segments, frac=0.8):
    # deterministic by hash of path
    train, val = [], []
    for s in segments:
        h = int(hashlib.md5(str(s).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        (train if h < frac else val).append(s)
    return train, val

def gather(platform, paths):
    Xs, ys = [], []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        # Some sims may not have accel_pedal_pct/brake_pressed in older files — skip those
        missing = [c for c in ALLOWLIST if c not in df.columns]
        if missing:
            # fill zeros so V1 still works
            for c in missing:
                df[c] = 0.0
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        X, r, feat_names = build_features(df, platform)
        m = np.isfinite(X).all(axis=1) & np.isfinite(r)
        Xs.append(X[m]); ys.append(r[m])
    if not Xs:
        return None, None, None
    return np.vstack(Xs), np.concatenate(ys), feat_names

def ridge_fit(X, y, lam=1e-3):
    # add intercept
    n, k = X.shape
    Xi = np.column_stack([np.ones(n), X])
    A = Xi.T @ Xi
    A[1:, 1:] += lam * np.eye(k)  # don't penalise intercept
    b = Xi.T @ y
    w = np.linalg.solve(A, b)
    return w  # w[0]=intercept, w[1:]=coefs

def main():
    out = {}
    for plat in PLATFORMS:
        pdir = ROOT/"data"/"sim"/"segments"/plat
        segs = sorted(pdir.rglob("sim.csv"))
        train_segs, val_segs = split_segments(segs, frac=0.8)
        Xtr, ytr, names = gather(plat, train_segs)
        Xva, yva, _ = gather(plat, val_segs)
        if Xtr is None:
            print(f"{plat}: no data"); continue
        w = ridge_fit(Xtr, ytr, lam=1.0)
        # Validate
        Xi_va = np.column_stack([np.ones(len(Xva)), Xva])
        pred_res = Xi_va @ w
        # Baseline val: predict 0 residual (== V1)
        rmse_v1 = math.sqrt(np.mean(yva**2))
        rmse_corrected = math.sqrt(np.mean((yva - pred_res)**2))
        print(f"=== {plat} ===")
        print(f"  n_train={len(Xtr)} n_val={len(Xva)}")
        print(f"  V1 residual RMSE (val) = {rmse_v1:.6f}")
        print(f"  V1+head residual RMSE (val) = {rmse_corrected:.6f}")
        print(f"  intercept = {w[0]:+.6f}")
        for n,c in zip(names, w[1:]):
            print(f"  {n:>10s} = {c:+.6f}")
        out[plat] = {
            "intercept": float(w[0]),
            "features": names,
            "coefs": [float(x) for x in w[1:]],
            "val_rmse_v1": rmse_v1,
            "val_rmse_corrected": rmse_corrected,
        }
    outpath = ROOT/"out"/"residual_coeffs.json"
    outpath.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {outpath}")

if __name__ == "__main__":
    main()
