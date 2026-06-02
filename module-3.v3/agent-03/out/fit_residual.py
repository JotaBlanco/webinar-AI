"""Fit a per-platform linear residual model:

    resid = w · phi(delta, d_delta, yr_v0, v, yr_v1, ...)

Features (allowlist-safe):
  - delta_road_rad
  - d_delta_dt
  - v_mps
  - yaw_rate_pred_rads (V0)
  - yr_v1 (our V1 prediction — derivable from inputs)
  - |a_lat_proxy| = |v_mps * yr_v0|
  - delta * v
  - d_delta * v
  - 1 (bias)

Save to coeffs.json keyed by platform.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v1_baseline", ROOT / "code" / "v1_baseline.py")
v1mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(v1mod)
predict_v1 = v1mod.predict_v1

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
data_full = ROOT / "data" / "sim" / "segments"


def make_features(df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = df["t_s"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    # safe gradient
    d_delta = np.gradient(delta, t) if len(t) > 1 else np.zeros_like(delta)
    d_yr_v1 = np.gradient(yr_v1, t) if len(t) > 1 else np.zeros_like(yr_v1)
    a_lat_proxy = v * yr_v0
    feats = np.column_stack([
        np.ones_like(delta),
        delta,
        d_delta,
        v,
        yr_v0,
        yr_v1,
        a_lat_proxy,
        delta * v,
        d_delta * v,
        d_yr_v1,
        np.sign(delta) * delta * delta,  # quadratic with sign
    ])
    return feats


FEAT_NAMES = ["1", "delta", "d_delta", "v", "yr_v0", "yr_v1", "a_lat_proxy", "delta*v", "d_delta*v", "d_yr_v1", "delta^2*sign"]


def fit_platform(plat: str):
    X_list = []
    y_list = []
    seg_ids = []
    n_seg = 0
    for sim_csv in sorted((data_full / plat).rglob("sim.csv")):
        df = pd.read_csv(sim_csv)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        pred = predict_v1(df, plat)
        yr_v1 = pred["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        feats = make_features(df, yr_v1)
        resid = yr_truth - yr_v1
        m = np.isfinite(resid) & np.all(np.isfinite(feats), axis=1)
        X_list.append(feats[m])
        y_list.append(resid[m])
        seg_ids.append(np.full(int(m.sum()), n_seg))
        n_seg += 1
    X = np.concatenate(X_list)
    y = np.concatenate(y_list)
    seg_ids = np.concatenate(seg_ids)
    # Ridge regression with small lambda
    lam = 1e-4
    XtX = X.T @ X
    Xty = X.T @ y
    A = XtX + lam * np.eye(X.shape[1]) * (np.trace(XtX) / X.shape[1])
    w = np.linalg.solve(A, Xty)
    yhat = X @ w
    rss = np.sum((y - yhat) ** 2)
    tss = np.sum(y * y)
    r2 = 1 - rss / tss
    rmse_resid = np.sqrt(rss / len(y))
    rmse_orig = np.sqrt(tss / len(y))
    print(f"  {plat}: N={len(y)}, segs={n_seg}, R2={r2:.4f}, RMSE_resid_pre={rmse_orig:.5f} -> post={rmse_resid:.5f}")
    return {"weights": w.tolist(), "feature_names": FEAT_NAMES, "n_samples": int(len(y)), "r2": float(r2)}


def main():
    out = {}
    for plat in PLATFORMS:
        print(f"\n--- {plat} ---")
        out[plat] = fit_platform(plat)
    (ROOT / "models" / "residual_learner" / "coeffs.json").write_text(json.dumps(out, indent=2))
    print("\nSaved", ROOT / "models" / "residual_learner" / "coeffs.json")


if __name__ == "__main__":
    main()
