"""Route-grouped 80/20 split: fit on 80% of route folders, eval on held-out 20%.

This catches the agent-07 overfit failure mode (asymmetric-bias subset fit
flipped Lightning sign). If dev/train gap > 10% on either KPI, we have a problem.
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-09")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"code"))
sys.path.insert(0, str(ROOT/"_shared")); sys.path.insert(0, str(ROOT/"out"))

from v1_baseline import predict_v1
from harness import list_segments, ALLOWED_COLS, PLATFORMS_FIT
from fit_residual import build_features, FEATURE_NAMES
from traj_metrics import cte_rmse_segment


def split_routes(pairs, seed=42, frac=0.8):
    # Group by route (first hash dir under platform).
    by_route = {}
    for sp_only, sp_full in pairs:
        # path: data/sim-only/segments/<plat>/<route>/<sub>/<idx>/sim.csv
        route = sp_only.parts[-4]
        by_route.setdefault(route, []).append((sp_only, sp_full))
    routes = sorted(by_route.keys())
    rng = np.random.default_rng(seed)
    rng.shuffle(routes)
    n_train = int(len(routes) * frac)
    train_routes = set(routes[:n_train])
    dev_routes = set(routes[n_train:])
    train = [p for r in train_routes for p in by_route[r]]
    dev = [p for r in dev_routes for p in by_route[r]]
    return train, dev


def fit_subset(pairs, platform, lam=1e-3):
    Fs, ys = [], []
    for sp_only, sp_full in pairs:
        sim_df = pd.read_csv(sp_only)
        if not all(c in sim_df.columns for c in ALLOWED_COLS):
            continue
        sim_df = sim_df[ALLOWED_COLS].copy()
        full = pd.read_csv(sp_full)
        if "yaw_rate_meas_rads" not in full.columns:
            continue
        yr_truth = full["yaw_rate_meas_rads"].to_numpy()
        out = predict_v1(sim_df, platform)
        yr_v1 = out["yaw_rate_pred_rads"].to_numpy()
        if len(yr_truth) != len(yr_v1):
            continue
        resid = yr_truth - yr_v1
        F = build_features(sim_df, yr_v1)
        good = np.isfinite(F).all(axis=1) & np.isfinite(resid)
        Fs.append(F[good]); ys.append(resid[good])
    F = np.vstack(Fs); y = np.concatenate(ys)
    good = np.isfinite(F).all(axis=1) & np.isfinite(y)
    F = F[good]; y = y[good]
    mu = F.mean(axis=0); sigma = F.std(axis=0); sigma[sigma < 1e-12] = 1.0
    mu[0] = 0.0; sigma[0] = 1.0
    Fz = (F - mu) / sigma
    n_feat = Fz.shape[1]
    A = Fz.T @ Fz + lam * len(y) * np.eye(n_feat)
    rhs = Fz.T @ y
    w, *_ = np.linalg.lstsq(A, rhs, rcond=None)
    return mu, sigma, w


def score_on_subset(pairs, platform, mu, sigma, w):
    yaw_sse = 0.0; yaw_n = 0; cte_sse = 0.0; cte_n = 0
    for sp_only, sp_full in pairs:
        sim_df = pd.read_csv(sp_only)
        if not all(c in sim_df.columns for c in ALLOWED_COLS): continue
        sim_df = sim_df[ALLOWED_COLS].copy()
        full = pd.read_csv(sp_full)
        if "yaw_rate_meas_rads" not in full.columns: continue
        yr_truth = full["yaw_rate_meas_rads"].to_numpy()
        out = predict_v1(sim_df, platform)
        yr_v1 = out["yaw_rate_pred_rads"].to_numpy()
        if len(yr_truth) != len(yr_v1): continue
        F = build_features(sim_df, yr_v1)
        F = np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0)
        Fz = (F - mu) / sigma
        resid_pred = Fz @ w
        yr_pred = yr_v1 + resid_pred
        res = yr_pred - yr_truth
        yaw_sse += float(np.sum(res*res)); yaw_n += len(res)
        t = sim_df["t_s"].to_numpy(); v = sim_df["v_mps"].to_numpy()
        ss, nb, _ = cte_rmse_segment(t, v, yr_truth, yr_pred)
        cte_sse += ss; cte_n += nb
    return {
        "yaw_rmse": math.sqrt(yaw_sse / max(1, yaw_n)),
        "cte_rmse": math.sqrt(cte_sse / max(1, cte_n)),
        "yaw_n": yaw_n, "cte_n": cte_n,
    }


if __name__ == "__main__":
    summary = {}
    for plat in PLATFORMS_FIT:
        pairs = list_segments(plat)
        train, dev = split_routes(pairs, seed=42)
        mu, sigma, w = fit_subset(train, plat)
        s_train = score_on_subset(train, plat, mu, sigma, w)
        s_dev = score_on_subset(dev, plat, mu, sigma, w)
        gap_yaw = (s_dev["yaw_rmse"] - s_train["yaw_rmse"]) / max(s_train["yaw_rmse"], 1e-9)
        gap_cte = (s_dev["cte_rmse"] - s_train["cte_rmse"]) / max(s_train["cte_rmse"], 1e-9)
        summary[plat] = {
            "n_train": len(train), "n_dev": len(dev),
            "train": s_train, "dev": s_dev,
            "gap_yaw_pct": 100*gap_yaw, "gap_cte_pct": 100*gap_cte,
        }
    print(json.dumps(summary, indent=2))
