"""Fit V2 = V1 + per-platform bias correction + ridge residual learner head.

Reads sim/segments (which carry truth). For each platform (not Tesla, not Lightning's
sub-noise-floor), fit a ridge regression mapping a feature vector to the V1
yaw-rate residual (truth - V1).

Lightning: only constant bias (residual learner skipped per cohort §5 — Lightning is
at noise floor).

We persist coefficients to coeffs.json that predict.py will load at grading time.

Validation: 5-fold route-grouped CV per platform — split routes (not segments) into
5 folds, hold each fold out, fit on 4, score residual reduction on held-out fold.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-01")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402

DATA_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS_FIT = ["FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "FORD_F_150_LIGHTNING_MK1"]

# Ridge regularisation
RIDGE_LAMBDA = 30.0          # cohort §4 (agent-06 used λ=30)
V_FILTER_MPS = 2.0           # match score-model's filter

# Sub-sampling per route for fit speed (keep things in budget)
MAX_ROWS_PER_SEG = 1500


def list_segment_paths(platform: str) -> list[Path]:
    plat_root = DATA_ROOT / platform
    return sorted(plat_root.glob("*/**/sim.csv"))


def route_of(p: Path) -> str:
    # data/sim/segments/<platform>/<route>/<segment>/<idx>/sim.csv
    return p.parents[2].name


def feature_matrix(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    """Build feature vector for residual learner.

    Features: 1 (bias), delta_road, |delta_road|, v, delta_road*v, |delta_road|*v,
    delta_road**2 * v, steer_rate, yr_v1.
    """
    t = sim_df["t_s"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    if len(t) > 1:
        dd_dt = np.gradient(d, t)
    else:
        dd_dt = np.zeros_like(d)
    feats = np.column_stack([
        np.ones_like(d),
        d,
        np.abs(d),
        v,
        d * v,
        np.abs(d) * v,
        d * d * v,
        dd_dt,
        yr_v1,
    ])
    return feats


def collect_platform(platform: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Return (X, y_resid, mask_valid, routes_per_row). Routes list lets us do
    route-grouped CV folds.
    """
    paths = list_segment_paths(platform)
    Xs, ys, routes = [], [], []
    rng = np.random.default_rng(42)
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        v = df["v_mps"].to_numpy(dtype=float)
        if len(df) < 3 or (v > V_FILTER_MPS).sum() < 50:
            continue
        # V1 prediction expects sim_df with allowlist columns; we'll pass the full DF
        # since V1 only reads delta_road_rad, v_mps, t_s, yaw_rate_pred_rads.
        pred = predict_v1(df, platform)
        yr_v1 = pred["yaw_rate_pred_rads"].to_numpy(dtype=float)
        yr_truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        resid = yr_truth - yr_v1
        mask = v > V_FILTER_MPS
        X_seg = feature_matrix(df, yr_v1)[mask]
        y_seg = resid[mask]
        if len(y_seg) > MAX_ROWS_PER_SEG:
            idx = rng.choice(len(y_seg), size=MAX_ROWS_PER_SEG, replace=False)
            X_seg = X_seg[idx]
            y_seg = y_seg[idx]
        if len(y_seg) == 0:
            continue
        Xs.append(X_seg)
        ys.append(y_seg)
        routes.extend([route_of(p)] * len(y_seg))
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    routes_arr = np.array(routes)
    return X, y, routes_arr


def ridge_fit(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    """Ridge solution. Bias term (column 0) is NOT regularised — use I with 0 on [0,0]."""
    n, k = X.shape
    A = X.T @ X + lam * np.eye(k)
    A[0, 0] -= lam  # don't shrink the constant
    b = X.T @ y
    return np.linalg.solve(A, b)


def cv_score(X: np.ndarray, y: np.ndarray, routes: np.ndarray, lam: float, n_folds: int = 5):
    """Route-grouped k-fold CV. Returns mean RMSE on held-out, plus
    'reduction vs zero' (i.e. baseline V1 residual RMSE — what we'd get predicting 0)."""
    uniq_routes = np.array(sorted(set(routes)))
    rng = np.random.default_rng(7)
    rng.shuffle(uniq_routes)
    folds = np.array_split(uniq_routes, n_folds)
    rmses_pred = []
    rmses_base = []
    for k in range(n_folds):
        hold_routes = set(folds[k])
        mask_test = np.array([r in hold_routes for r in routes])
        mask_train = ~mask_test
        Xtr, ytr = X[mask_train], y[mask_train]
        Xte, yte = X[mask_test], y[mask_test]
        if len(ytr) == 0 or len(yte) == 0:
            continue
        beta = ridge_fit(Xtr, ytr, lam)
        yhat = Xte @ beta
        rmses_pred.append(math.sqrt(float(np.mean((yte - yhat) ** 2))))
        rmses_base.append(math.sqrt(float(np.mean(yte ** 2))))
    return float(np.mean(rmses_pred)), float(np.std(rmses_pred)), float(np.mean(rmses_base))


def main() -> None:
    coeffs = {"ridge_lambda": RIDGE_LAMBDA, "feature_names": [
        "const", "delta_road", "abs_delta_road", "v", "delta*v", "abs_delta*v",
        "delta^2*v", "d_delta_dt", "yr_v1",
    ], "platforms": {}}
    for plat in PLATFORMS_FIT:
        print(f"\n=== {plat} ===")
        X, y, routes = collect_platform(plat)
        print(f"  rows={len(y):,}, routes={len(set(routes))}")
        # Bias-only baseline: predict y_mean. The cohort §2 move is just per-platform
        # constant additive bias; ridge with our 1st column captures it as beta[0].
        bias_only = float(np.mean(y))
        base_rmse = math.sqrt(float(np.mean(y ** 2)))
        bias_only_rmse = math.sqrt(float(np.mean((y - bias_only) ** 2)))
        # Full ridge CV
        rmse_cv, std_cv, base_cv = cv_score(X, y, routes, RIDGE_LAMBDA, n_folds=5)
        # Fit final on all data
        beta = ridge_fit(X, y, RIDGE_LAMBDA)
        print(f"  bias_only={bias_only:+.6f}, residual std (V1) = {base_rmse:.6f}")
        print(f"  bias_only reduction: {base_rmse:.6f} -> {bias_only_rmse:.6f}")
        print(f"  ridge CV: {rmse_cv:.6f} ± {std_cv:.6f} (baseline {base_cv:.6f})")
        coeffs["platforms"][plat] = {
            "bias_only": bias_only,
            "beta": beta.tolist(),
            "cv_residual_rmse": rmse_cv,
            "cv_residual_rmse_std": std_cv,
            "cv_baseline_rmse": base_cv,
        }

    out = ROOT / "final-model" / "coeffs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
