"""V3 — richer feature set: add v^2, delta^2, delta^3, (ay_proxy)^2.

Per-platform fit, route-grouped CV.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-02")
RES_DIR = ROOT / "out" / "residuals"
COEF_DIR = ROOT / "out" / "coefs_v3"
COEF_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]


def features(df):
    v = df["v"].to_numpy()
    delta = df["delta"].to_numpy()
    dd = np.clip(df["ddelta_dt"].to_numpy(), -5.0, 5.0)
    ay = df["ay_proxy"].to_numpy()
    sgn = np.where(np.abs(delta) > 0.01, np.sign(delta), 0.0)
    X = np.column_stack([
        np.ones_like(v),
        v, v*v,
        delta, delta*v, delta*delta, delta*delta*v,
        dd, dd*v,
        ay, ay*np.abs(ay),
        sgn, np.abs(delta)*v,
    ])
    feat_names = ["bias","v","v2","delta","delta_v","delta2","delta2_v",
                  "dd","dd_v","ay","ay_absay","sgn_delta","abs_delta_v"]
    return X, feat_names


def ridge_fit(X, y, lam):
    A = X.T @ X + lam * np.eye(X.shape[1])
    return np.linalg.solve(A, X.T @ y)


def kfold(df, k=5, lam=10.0):
    routes = df["route"].unique()
    rng = np.random.RandomState(42)
    rng.shuffle(routes)
    folds = np.array_split(routes, k)
    rb, ra = [], []
    for val_routes in folds:
        val_mask = df["route"].isin(val_routes)
        train = df[~val_mask]
        val = df[val_mask]
        if len(val) == 0:
            continue
        Xtr,_ = features(train); ytr = train["resid"].to_numpy()
        Xvl,_ = features(val); yvl = val["resid"].to_numpy()
        w = ridge_fit(Xtr, ytr, lam)
        yhat = Xvl @ w
        rb.append(float(np.sqrt(np.mean(yvl**2))))
        ra.append(float(np.sqrt(np.mean((yvl - yhat)**2))))
    return rb, ra


def main():
    summary = {}
    for plat in PLATFORMS:
        path = RES_DIR / f"{plat}.parquet"
        df = pd.read_parquet(path)
        best_lam, best = None, np.inf
        cv = {}
        for lam in [1.0, 10.0, 100.0, 1000.0, 1e4, 1e5]:
            rb, ra = kfold(df, k=5, lam=lam)
            cv[str(lam)] = {"before": float(np.mean(rb)), "after": float(np.mean(ra))}
            if np.mean(ra) < best:
                best, best_lam = np.mean(ra), lam
        X, feat_names = features(df)
        y = df["resid"].to_numpy()
        w = ridge_fit(X, y, best_lam)
        coefs = dict(zip(feat_names, w.tolist()))
        out = {
            "platform": plat,
            "n_rows": len(df),
            "best_lambda": best_lam,
            "cv_summary": cv,
            "coefs": coefs,
            "feature_names": feat_names,
        }
        (COEF_DIR / f"{plat}.json").write_text(json.dumps(out, indent=2))
        print(f"[{plat}] best_lam={best_lam}, CV: {cv}")
        summary[plat] = out
    (COEF_DIR / "_summary.json").write_text(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
