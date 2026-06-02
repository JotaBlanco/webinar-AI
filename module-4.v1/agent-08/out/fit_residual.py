"""Fit a per-platform residual learner on top of V1.

Residual = yaw_rate_meas - V1_pred
Features (only from allowlist):
  yr_v1, v, v*yr_v1, delta_road, delta_road*v, delta_dot (numerical),
  yr_v1_dot, sgn(yr_v1)*v, a_long.

We split segments deterministically: 80% train / 20% dev (by segment hash).
Fit per platform with ridge regression (closed-form). Save coefficients per
platform to JSON.

Then score: yr_pred = V1_pred + clip(beta · features, -alpha*|yr_v1|-eps, +alpha*|yr_v1|+eps)
We also report the bare un-clipped variant.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-08")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import predict_v1  # noqa: E402

SIM_ONLY = ROOT / "data" / "sim-only" / "segments"
SIM_TRUTH = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def seg_hash(path: Path) -> int:
    h = hashlib.sha1(str(path).encode()).hexdigest()
    return int(h[:8], 16)


def build_features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    dr = sim_df["delta_road_rad"].to_numpy(dtype=float)
    al = sim_df["a_long_mps2"].to_numpy(dtype=float)
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 1e-3, dt)
    yr_v1_dot = np.gradient(yr_v1, t)
    dr_dot = np.gradient(dr, t)
    a_lat_proxy = v * yr_v1  # allowlist-only proxy
    # Curvature proxy
    curv = yr_v1 / np.maximum(v, 0.5)
    cols = [
        np.ones_like(v),
        yr_v1,
        v,
        v * v,
        v * yr_v1,
        dr,
        dr * v,
        dr_dot,
        yr_v1_dot,
        a_lat_proxy,
        a_lat_proxy * v,
        np.sign(yr_v1) * v,
        al,
        curv,
        np.tanh(yr_v1 * 5),
    ]
    X = np.column_stack(cols)
    return X


def iter_paths(platform: str):
    for sim_csv in (SIM_ONLY / platform).rglob("sim.csv"):
        yield sim_csv


def load_segment(sim_only_csv: Path):
    rel = sim_only_csv.relative_to(SIM_ONLY)
    truth_csv = SIM_TRUTH / rel
    if not truth_csv.exists():
        return None
    try:
        sim_df = pd.read_csv(sim_only_csv)
        truth_df = pd.read_csv(truth_csv, usecols=["yaw_rate_meas_rads"])
    except Exception:
        return None
    if len(sim_df) != len(truth_df):
        return None
    return sim_df, truth_df["yaw_rate_meas_rads"].to_numpy(dtype=float)


def fit_one_platform(platform: str, ridge_lambda: float = 1.0):
    Xs_tr, ys_tr = [], []
    Xs_dv, ys_dv = [], []
    n_tr = 0
    n_dv = 0
    for sim_csv in iter_paths(platform):
        loaded = load_segment(sim_csv)
        if loaded is None:
            continue
        sim_df, yr_truth = loaded
        try:
            yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy(dtype=float)
        except Exception:
            continue
        resid = yr_truth - yr_v1
        X = build_features(sim_df, yr_v1)
        mask = np.isfinite(resid) & np.isfinite(X).all(axis=1)
        if mask.sum() < 5:
            continue
        # Split by segment hash
        is_dev = (seg_hash(sim_csv) % 5) == 0
        if is_dev:
            Xs_dv.append(X[mask])
            ys_dv.append(resid[mask])
            n_dv += 1
        else:
            Xs_tr.append(X[mask])
            ys_tr.append(resid[mask])
            n_tr += 1
    if not Xs_tr:
        return None
    Xtr = np.vstack(Xs_tr)
    ytr = np.concatenate(ys_tr)
    Xdv = np.vstack(Xs_dv) if Xs_dv else Xtr[:1]
    ydv = np.concatenate(ys_dv) if ys_dv else ytr[:1]
    # Standardize for stable ridge
    mu = Xtr.mean(axis=0)
    sd = Xtr.std(axis=0)
    sd[sd < 1e-9] = 1.0
    # Don't scale the intercept column (col 0)
    mu[0] = 0.0
    sd[0] = 1.0
    Xtr_s = (Xtr - mu) / sd
    Xdv_s = (Xdv - mu) / sd
    # Ridge closed-form
    p = Xtr_s.shape[1]
    A = Xtr_s.T @ Xtr_s + ridge_lambda * np.eye(p)
    A[0, 0] -= ridge_lambda  # don't regularize intercept
    b = Xtr_s.T @ ytr
    beta = np.linalg.solve(A, b)
    tr_pred = Xtr_s @ beta
    dv_pred = Xdv_s @ beta
    tr_rmse_before = math.sqrt((ytr ** 2).mean())
    tr_rmse_after = math.sqrt(((ytr - tr_pred) ** 2).mean())
    dv_rmse_before = math.sqrt((ydv ** 2).mean())
    dv_rmse_after = math.sqrt(((ydv - dv_pred) ** 2).mean())
    return {
        "beta": beta.tolist(),
        "mu": mu.tolist(),
        "sd": sd.tolist(),
        "n_tr_segments": n_tr,
        "n_dv_segments": n_dv,
        "tr_rmse_before": tr_rmse_before,
        "tr_rmse_after": tr_rmse_after,
        "dv_rmse_before": dv_rmse_before,
        "dv_rmse_after": dv_rmse_after,
    }


if __name__ == "__main__":
    out = {}
    for plat in PLATFORMS:
        print(f"Fitting {plat}...", flush=True)
        r = fit_one_platform(plat)
        if r is None:
            print(f"  no data", flush=True)
            continue
        print(f"  n_tr_seg={r['n_tr_segments']} n_dv_seg={r['n_dv_segments']}")
        print(f"  resid RMSE  train: {r['tr_rmse_before']:.6f} -> {r['tr_rmse_after']:.6f}")
        print(f"  resid RMSE   dev : {r['dv_rmse_before']:.6f} -> {r['dv_rmse_after']:.6f}")
        out[plat] = r
    coeffs = {p: {"beta": r["beta"], "mu": r["mu"], "sd": r["sd"]} for p, r in out.items()}
    with open(ROOT / "out" / "residual_coeffs.json", "w") as f:
        json.dump(coeffs, f, indent=2)
    print("\nSaved coefficients ->", ROOT / "out" / "residual_coeffs.json")
