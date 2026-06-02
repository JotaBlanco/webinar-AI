"""Fit per-platform ridge residual learner on V1 residuals.

Features (input-only, allowlist-respecting):
  - 1               -> additive bias
  - v               -> speed-scaled bias
  - delta           -> steering-angle linear coupling
  - delta*v
  - ddelta_dt       -> steering rate
  - ddelta_dt*v
  - ay_proxy = v * yr_v1
  - sign(delta) -> asymmetry hint (gated by |delta|>0.01)

Uses route-grouped K-fold CV to compute baseline V1 RMSE vs fit RMSE per platform.

Saves coefs to out/coefs/<platform>.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-02")
RES_DIR = ROOT / "out" / "residuals"
COEF_DIR = ROOT / "out" / "coefs"
COEF_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]


def features(df):
    v = df["v"].to_numpy()
    delta = df["delta"].to_numpy()
    dd = df["ddelta_dt"].to_numpy()
    ay = df["ay_proxy"].to_numpy()
    # clip ddelta_dt to suppress sensor outliers
    dd = np.clip(dd, -5.0, 5.0)
    sgn_delta = np.where(np.abs(delta) > 0.01, np.sign(delta), 0.0)
    X = np.column_stack([
        np.ones_like(v),
        v,
        delta,
        delta * v,
        dd,
        dd * v,
        ay,
        sgn_delta,
        np.abs(delta) * v,  # magnitude-scaled understeer correction
    ])
    feat_names = ["bias", "v", "delta", "delta_v", "dd", "dd_v", "ay_proxy",
                  "sgn_delta", "abs_delta_v"]
    return X, feat_names


def ridge_fit(X, y, lam):
    A = X.T @ X + lam * np.eye(X.shape[1])
    b = X.T @ y
    return np.linalg.solve(A, b)


def kfold_route_cv(df, k=5, lam=10.0):
    routes = df["route"].unique()
    rng = np.random.RandomState(42)
    rng.shuffle(routes)
    folds = np.array_split(routes, k)
    rmses_before = []
    rmses_after = []
    for i, val_routes in enumerate(folds):
        val_mask = df["route"].isin(val_routes)
        train = df[~val_mask]
        val = df[val_mask]
        if len(val) == 0 or len(train) == 0:
            continue
        Xtr, _ = features(train)
        ytr = train["resid"].to_numpy()
        Xvl, _ = features(val)
        yvl = val["resid"].to_numpy()
        w = ridge_fit(Xtr, ytr, lam)
        yhat = Xvl @ w
        # before correction = V1 residual = yvl itself (since V1 is reference)
        rmse_before = float(np.sqrt(np.mean(yvl ** 2)))
        rmse_after = float(np.sqrt(np.mean((yvl - yhat) ** 2)))
        rmses_before.append(rmse_before)
        rmses_after.append(rmse_after)
    return rmses_before, rmses_after


def main():
    summary = {}
    for plat in PLATFORMS:
        path = RES_DIR / f"{plat}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        n = len(df)

        # First, signed bias
        bias = float(df["resid"].mean())
        std = float(df["resid"].std())

        # K-fold CV at multiple lambdas
        best_lam, best_rmse_after = None, np.inf
        cv_summary = {}
        for lam in [1.0, 10.0, 100.0, 1000.0, 1e4]:
            rb, ra = kfold_route_cv(df, k=5, lam=lam)
            mean_a = float(np.mean(ra))
            cv_summary[str(lam)] = {"rmse_before": float(np.mean(rb)),
                                    "rmse_after": mean_a}
            if mean_a < best_rmse_after:
                best_rmse_after = mean_a
                best_lam = lam

        # Refit on full data
        X, feat_names = features(df)
        y = df["resid"].to_numpy()
        w = ridge_fit(X, y, best_lam)
        yhat = X @ w
        rmse_full_before = float(np.sqrt(np.mean(y ** 2)))
        rmse_full_after = float(np.sqrt(np.mean((y - yhat) ** 2)))

        coefs = dict(zip(feat_names, w.tolist()))
        out = {
            "platform": plat,
            "n_rows": n,
            "signed_bias": bias,
            "std": std,
            "best_lambda": best_lam,
            "cv_summary": cv_summary,
            "full_rmse_before": rmse_full_before,
            "full_rmse_after": rmse_full_after,
            "coefs": coefs,
            "feature_names": feat_names,
        }
        (COEF_DIR / f"{plat}.json").write_text(json.dumps(out, indent=2))
        summary[plat] = {
            "rmse_before": rmse_full_before,
            "rmse_after": rmse_full_after,
            "best_lam": best_lam,
            "bias": bias,
            "coefs": coefs,
        }
        print(f"[{plat}] bias={bias:+.5f}, rmse_before={rmse_full_before:.5f}, "
              f"rmse_after={rmse_full_after:.5f}, best_lam={best_lam}")
        print(f"  CV: {cv_summary}")
        print(f"  Coefs: {coefs}")

    (COEF_DIR / "_summary.json").write_text(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
