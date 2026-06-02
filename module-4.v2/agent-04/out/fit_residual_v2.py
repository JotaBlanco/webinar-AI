"""V2 ridge: try with zero-mean residual target (no global bias term).

Hypothesis: the global bias of the correction is hurting CTE (integrated drift).
Strategy: drop the intercept feature, force residual mean to zero, see if
CTE on dev improves.
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
from fit_residual import build_features, collect_platform_data, fit_ridge


def fit_ridge_no_bias(X, y, lam=100.0):
    """Drop intercept column (col 0)."""
    X2 = X[:, 1:]
    mu = X2.mean(axis=0)
    sd = X2.std(axis=0)
    sd[sd < 1e-9] = 1.0
    Xs = (X2 - mu) / sd
    n_feat = Xs.shape[1]
    A = Xs.T @ Xs + lam * np.eye(n_feat)
    b = Xs.T @ y
    w = np.linalg.solve(A, b)
    # Pad with zero intercept for compatibility with predict module
    w_full = np.concatenate([[0.0], w])
    mu_full = np.concatenate([[0.0], mu])
    sd_full = np.concatenate([[1.0], sd])
    return {"w": w_full.tolist(), "mu": mu_full.tolist(), "sd": sd_full.tolist(), "lam": lam}


if __name__ == "__main__":
    coeffs = {}
    for plat in PLATFORMS_WITH_TRUTH:
        print(f"\n=== {plat} ===")
        X, y = collect_platform_data(plat, max_segs=80)
        for lam in [10.0, 100.0, 1000.0]:
            fit = fit_ridge_no_bias(X, y, lam=lam)
            w = np.array(fit["w"])
            mu = np.array(fit["mu"]); sd = np.array(fit["sd"])
            Xs = (X - mu) / sd
            pred = Xs @ w
            rmse_pre = np.sqrt((y * y).mean())
            rmse_post = np.sqrt(((y - pred) ** 2).mean())
            print(f"  lam={lam}: rmse_pre={rmse_pre:.6e} rmse_post={rmse_post:.6e} pred_mean={pred.mean():.6e}")
        coeffs[plat] = fit_ridge_no_bias(X, y, lam=100.0)
    out = ROOT / "out" / "ridge_coeffs_v2.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"\nwrote {out}")
