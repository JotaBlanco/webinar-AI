"""Fit a small gradient-boosted regressor per platform for the V1 residual.

Features are allowlist-safe. Save to pickle.

We use HistGradientBoostingRegressor (fast, native).
"""
from __future__ import annotations

import importlib.util
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

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
    a_lat_proxy = v * yr_v0
    a_long = df["a_long_mps2"].to_numpy()
    return np.column_stack([delta, d_delta, v, yr_v0, yr_v1, a_lat_proxy, a_long])


FEAT_NAMES = ["delta", "d_delta", "v", "yr_v0", "yr_v1", "a_lat_proxy", "a_long"]


def main():
    out_dir = ROOT / "models" / "residual_gb"
    out_dir.mkdir(exist_ok=True)
    for plat in PLATFORMS:
        print(f"\n--- {plat} ---")
        X_list = []; y_list = []
        for sim_csv in sorted((data_full / plat).rglob("sim.csv")):
            df = pd.read_csv(sim_csv)
            if "yaw_rate_meas_rads" not in df.columns: continue
            yr_v1 = predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy()
            feats = features(df, yr_v1)
            resid = df["yaw_rate_meas_rads"].to_numpy() - yr_v1
            m = np.isfinite(resid) & np.all(np.isfinite(feats), axis=1)
            X_list.append(feats[m]); y_list.append(resid[m])
        X = np.concatenate(X_list); y = np.concatenate(y_list)
        # Sub-sample for speed if very large
        rng = np.random.RandomState(42)
        if len(y) > 400000:
            idx = rng.choice(len(y), 400000, replace=False)
            Xtrain, ytrain = X[idx], y[idx]
        else:
            Xtrain, ytrain = X, y
        gb = HistGradientBoostingRegressor(
            max_iter=200, max_depth=5, learning_rate=0.05,
            min_samples_leaf=200, l2_regularization=1e-3, random_state=42,
        )
        gb.fit(Xtrain, ytrain)
        yhat = gb.predict(X)
        rss = float(np.sum((y - yhat) ** 2))
        tss = float(np.sum(y * y))
        r2 = 1 - rss / tss
        print(f"  N={len(y)} R2={r2:.4f} RMSE {np.sqrt(tss/len(y)):.5f} -> {np.sqrt(rss/len(y)):.5f}")
        with (out_dir / f"{plat}.pkl").open("wb") as f:
            pickle.dump({"model": gb, "feat_names": FEAT_NAMES}, f)
    print("\nSaved per-platform GB models to", out_dir)


if __name__ == "__main__":
    main()
