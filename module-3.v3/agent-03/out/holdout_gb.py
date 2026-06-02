"""Route-grouped holdout check for residual_gb.

Split routes 80/20 per platform; train on 80, score on 20. Compares against V1.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_rmse_segment

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


rng = np.random.RandomState(7)

for plat in PLATFORMS:
    print(f"\n=== {plat} ===")
    base = data_full / plat
    # Route = top-level directory
    routes = sorted([d.name for d in base.iterdir() if d.is_dir()])
    rng.shuffle(routes)
    n_dev = max(1, len(routes) // 5)
    dev_routes = set(routes[:n_dev])
    train_routes = set(routes[n_dev:])
    print(f"  routes total={len(routes)} train={len(train_routes)} dev={len(dev_routes)}")
    train_X = []; train_y = []
    dev_segs = []
    for route in routes:
        for sim_csv in sorted((base / route).rglob("sim.csv")):
            df = pd.read_csv(sim_csv)
            if "yaw_rate_meas_rads" not in df.columns: continue
            yr_v1 = predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy()
            feats = features(df, yr_v1)
            resid = df["yaw_rate_meas_rads"].to_numpy() - yr_v1
            m = np.isfinite(resid) & np.all(np.isfinite(feats), axis=1)
            if route in train_routes:
                train_X.append(feats[m]); train_y.append(resid[m])
            else:
                dev_segs.append((df, yr_v1, feats, m))
    X = np.concatenate(train_X); y = np.concatenate(train_y)
    print(f"  train N={len(y)}")
    if len(y) > 300000:
        idx = rng.choice(len(y), 300000, replace=False)
        X, y = X[idx], y[idx]
    gb = HistGradientBoostingRegressor(max_iter=200, max_depth=5, learning_rate=0.05, min_samples_leaf=200, l2_regularization=1e-3, random_state=42)
    gb.fit(X, y)
    # Dev metrics
    yaw_v1_sumsq = 0.0
    yaw_gb_sumsq = 0.0
    nn = 0
    cte_v1 = 0.0; cte_gb = 0.0; bins_v1 = 0; bins_gb = 0
    for df, yr_v1, feats, m in dev_segs:
        corr = np.zeros(len(yr_v1))
        if m.any():
            corr[m] = gb.predict(feats[m])
        yr_gb = yr_v1 + corr
        truth = df["yaw_rate_meas_rads"].to_numpy()
        mm = m & np.isfinite(truth)
        r_v1 = truth[mm] - yr_v1[mm]
        r_gb = truth[mm] - yr_gb[mm]
        yaw_v1_sumsq += float(np.sum(r_v1*r_v1))
        yaw_gb_sumsq += float(np.sum(r_gb*r_gb))
        nn += int(mm.sum())
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        ss, nb, _ = cte_rmse_segment(t, v, truth, yr_v1); cte_v1 += ss; bins_v1 += nb
        ss, nb, _ = cte_rmse_segment(t, v, truth, yr_gb); cte_gb += ss; bins_gb += nb
    print(f"  DEV yaw: V1={math.sqrt(yaw_v1_sumsq/nn):.5f}  GB={math.sqrt(yaw_gb_sumsq/nn):.5f}")
    print(f"  DEV cte: V1={math.sqrt(cte_v1/bins_v1):.2f}  GB={math.sqrt(cte_gb/bins_gb):.2f}")
