"""Expanded residual learner with regime-gated nonlinear features.

We add:
  - sign(d_delta)*sqrt(|d_delta|)  -- transient kick
  - tanh(d_delta * 5)
  - delta * yr_v0  (cross term)
  - clip(a_lat_proxy, -10, 10) -- proxy for tyre nonlinearity
  - segment-wise zero-mean residual capture via per-route median offset (no — leak)

And use per-platform fit with ridge.
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


def features(df, yr_v1):
    t = df["t_s"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    d_delta = np.gradient(delta, t) if len(t) > 1 else np.zeros_like(delta)
    d_yr_v1 = np.gradient(yr_v1, t) if len(t) > 1 else np.zeros_like(yr_v1)
    a_lat_proxy = v * yr_v0
    sqd = np.sign(d_delta) * np.sqrt(np.abs(d_delta))
    th_dd = np.tanh(d_delta * 5.0)
    return np.column_stack([
        np.ones_like(delta),         # 0  bias
        delta,                       # 1
        d_delta,                     # 2
        v,                           # 3
        yr_v0,                       # 4
        yr_v1,                       # 5
        a_lat_proxy,                 # 6
        delta * v,                   # 7
        d_delta * v,                 # 8
        d_yr_v1,                     # 9
        np.sign(delta) * delta * delta,  # 10
        sqd,                         # 11
        sqd * v,                     # 12
        th_dd,                       # 13
        delta * yr_v0,               # 14
        np.clip(a_lat_proxy, -10, 10) * np.sign(yr_v0),  # 15
        d_delta * yr_v0,             # 16
        d_delta * d_delta * np.sign(d_delta),  # 17
    ])


FEAT_NAMES = ["1","delta","d_delta","v","yr_v0","yr_v1","a_lat_proxy","delta*v","d_delta*v","d_yr_v1","delta^2*sign","sqd","sqd*v","tanh(5dd)","delta*yr_v0","clip(alat)*sign(yr)","d_delta*yr_v0","dd^2*sign"]


def fit_one(plat, segs_full):
    X_list = []; y_list = []
    for df in segs_full:
        pred = predict_v1(df, plat)
        yr_v1 = pred["yaw_rate_pred_rads"].to_numpy()
        feats = features(df, yr_v1)
        resid = df["yaw_rate_meas_rads"].to_numpy() - yr_v1
        m = np.isfinite(resid) & np.all(np.isfinite(feats), axis=1)
        X_list.append(feats[m]); y_list.append(resid[m])
    X = np.concatenate(X_list); y = np.concatenate(y_list)
    lam = 1e-3
    XtX = X.T @ X
    Xty = X.T @ y
    A = XtX + lam * np.eye(X.shape[1]) * (np.trace(XtX) / X.shape[1])
    w = np.linalg.solve(A, Xty)
    yhat = X @ w
    rss = np.sum((y - yhat) ** 2)
    tss = np.sum(y * y)
    r2 = 1 - rss / tss
    print(f"  {plat}: N={len(y)}, R2={r2:.4f}, RMSE {np.sqrt(tss/len(y)):.5f}->{np.sqrt(rss/len(y)):.5f}")
    return {"weights": w.tolist(), "feature_names": FEAT_NAMES, "r2": float(r2)}


def main():
    out = {}
    for plat in PLATFORMS:
        print(f"\n--- {plat} ---")
        segs = []
        for sim_csv in sorted((data_full / plat).rglob("sim.csv")):
            df = pd.read_csv(sim_csv)
            if "yaw_rate_meas_rads" in df.columns:
                segs.append(df)
        out[plat] = fit_one(plat, segs)
    (ROOT / "models" / "residual_learner" / "coeffs.json").write_text(json.dumps(out, indent=2))
    print("Saved coeffs.json (residual_learner v2)")


if __name__ == "__main__":
    main()
