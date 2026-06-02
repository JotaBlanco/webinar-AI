"""Fit a per-platform ridge regression on V1's yaw-rate residual.

Features from allowlist columns only:
  - delta_road_rad (steering)
  - v_mps, v^2
  - delta * v
  - delta * v^2  (proxy for understeer curvature)
  - yaw_rate_pred_rads (V1 output as feature)
  - yaw_rate_pred_rads * v
  - a_long_mps2
  - delta_dot (numerical derivative of delta_road_rad)

Target: truth - V1_pred (i.e. learn the missing structure on top of V1).
Predict yaw correction. Final yaw = V1 + correction - bias.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-04")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1
from score import find_segments, load_sim, ALLOW_COLS, PLATFORMS_WITH_TRUTH


def build_features(sim_df: pd.DataFrame, v1_yaw: np.ndarray) -> np.ndarray:
    """Construct feature matrix from allowlist-only columns + V1 pred."""
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    a_long = sim_df["a_long_mps2"].to_numpy()
    # delta_dot
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = 1e-3
    delta_dot = np.diff(delta, prepend=delta[0]) / dt
    # smooth
    win = 5
    if len(delta_dot) >= win:
        delta_dot = pd.Series(delta_dot).rolling(win, center=True, min_periods=1).mean().to_numpy()
    v2 = v * v
    feats = np.column_stack([
        np.ones_like(v),
        delta,
        v,
        v2,
        delta * v,
        delta * v2,
        v1_yaw,
        v1_yaw * v,
        a_long,
        delta_dot,
        delta_dot * v,
    ])
    return feats


def collect_platform_data(platform: str, max_segs: int = 100):
    paths = find_segments(platform, split="train")[:max_segs]
    Xs = []
    ys = []
    for p in paths:
        df = load_sim(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        sim_df = df[ALLOW_COLS].copy()
        v1_out = predict_v1(sim_df, platform)
        v1_yaw = v1_out["yaw_rate_pred_rads"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        feats = build_features(sim_df, v1_yaw)
        residual = truth - v1_yaw
        mask = v > 3.0
        Xs.append(feats[mask])
        ys.append(residual[mask])
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    return X, y


def fit_ridge(X: np.ndarray, y: np.ndarray, lam: float = 100.0):
    """Standardise features then closed-form ridge."""
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd < 1e-9] = 1.0
    # don't standardise bias column (col 0 is ones)
    mu[0] = 0.0
    sd[0] = 1.0
    Xs = (X - mu) / sd
    n_feat = Xs.shape[1]
    A = Xs.T @ Xs + lam * np.eye(n_feat)
    A[0, 0] -= lam  # don't penalise bias
    b = Xs.T @ y
    w = np.linalg.solve(A, b)
    return {"w": w.tolist(), "mu": mu.tolist(), "sd": sd.tolist(), "lam": lam}


if __name__ == "__main__":
    coeffs = {}
    for plat in PLATFORMS_WITH_TRUTH:
        print(f"\n=== {plat} ===")
        X, y = collect_platform_data(plat, max_segs=80)
        print(f"X={X.shape}, y={y.shape}, y_mean={y.mean():.6e}, y_std={y.std():.6e}")
        for lam in [10.0, 100.0, 1000.0]:
            fit = fit_ridge(X, y, lam=lam)
            w = np.array(fit["w"])
            pred = ((X - np.array(fit["mu"])) / np.array(fit["sd"])) @ w
            rmse_pre = np.sqrt((y * y).mean())
            rmse_post = np.sqrt(((y - pred) ** 2).mean())
            print(f"  lam={lam}: rmse_pre={rmse_pre:.6e} rmse_post={rmse_post:.6e}")
        # Use lam=100 by default
        coeffs[plat] = fit_ridge(X, y, lam=100.0)
    out = ROOT / "out" / "ridge_coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"\nwrote {out}")
