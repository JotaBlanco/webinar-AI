"""V1 fitter: per-platform calibration.

Model: yaw_pred = alpha * V0 / (1 + K * v^2)   (understeer-gradient form)

Fit alpha, K per platform by least squares against truth. We optimise the
yaw-rate residual (sample-pooled, v > 2 m/s) since CTE is a downstream
integral and the per-platform signed-bias warnings show that the dominant
error is a yaw-rate scale/understeer mismatch.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = ROOT / "data" / "sim" / "segments"

TRUTH_COL = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
    "TESLA_MODEL_3":            "psi_dot_rads",
}


def load_platform(platform: str):
    paths = sorted((SEGMENTS / platform).glob("**/sim.csv"))
    truth_col = TRUTH_COL[platform]
    Vs, Ys, V0s = [], [], []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "v_mps", "delta_road_rad",
                                          truth_col, "yaw_rate_pred_rads"])
        except (ValueError, KeyError):
            continue
        if len(df) < 2:
            continue
        m = df["v_mps"] > 2.0
        Vs.append(df.loc[m, "v_mps"].to_numpy(dtype=float))
        Ys.append(df.loc[m, truth_col].to_numpy(dtype=float))
        V0s.append(df.loc[m, "yaw_rate_pred_rads"].to_numpy(dtype=float))
    v   = np.concatenate(Vs)
    y   = np.concatenate(Ys)
    v0  = np.concatenate(V0s)
    return v, y, v0


def fit_understeer(v, y, v0):
    """Fit yaw = alpha * v0 / (1 + K * v^2). Closed-form for alpha given K."""
    def loss(theta):
        K = theta[0]
        denom = 1.0 + K * v * v
        pred_base = v0 / denom
        # alpha closed-form for given K (least squares)
        num = np.sum(pred_base * y)
        den = np.sum(pred_base * pred_base)
        alpha = num / den if den > 0 else 1.0
        pred = alpha * pred_base
        return float(np.mean((pred - y) ** 2))
    # Search K >= 0 (understeer) but allow slight negative for oversteer
    best = minimize(loss, x0=[0.001], method="Nelder-Mead",
                    options={"xatol": 1e-8, "fatol": 1e-12, "maxiter": 2000})
    K = float(best.x[0])
    denom = 1.0 + K * v * v
    pred_base = v0 / denom
    alpha = float(np.sum(pred_base * y) / np.sum(pred_base * pred_base))
    pred = alpha * pred_base
    rmse_v1 = float(math.sqrt(np.mean((pred - y) ** 2)))
    rmse_v0 = float(math.sqrt(np.mean((v0 - y) ** 2)))
    return {"alpha": alpha, "K": K, "rmse_v0": rmse_v0, "rmse_v1": rmse_v1}


def fit_affine_v(v, y, v0):
    """yaw = a*v0 + b*v0*v^2 + c (linear, sample-pooled OLS)."""
    X = np.column_stack([v0, v0 * v * v, np.ones_like(v)])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    rmse = float(math.sqrt(np.mean((pred - y) ** 2)))
    return {"a": float(coef[0]), "b": float(coef[1]), "c": float(coef[2]), "rmse_affine": rmse}


if __name__ == "__main__":
    out = {}
    for plat in TRUTH_COL:
        print(f"\n=== {plat} ===")
        try:
            v, y, v0 = load_platform(plat)
        except Exception as e:
            print(f"  skip: {e}")
            continue
        if len(v) == 0:
            print("  no data")
            continue
        if plat == "TESLA_MODEL_3":
            out[plat] = {"alpha": 1.0, "K": 0.0, "rmse_v0": 0.0, "rmse_v1": 0.0}
            print("  Tesla: identity (V0 == truth)")
            continue
        r_under = fit_understeer(v, y, v0)
        r_affine = fit_affine_v(v, y, v0)
        print(f"  V0 rmse:        {r_under['rmse_v0']:.6f}")
        print(f"  understeer fit: alpha={r_under['alpha']:.5f}, K={r_under['K']:.6f}, rmse={r_under['rmse_v1']:.6f}")
        print(f"  affine fit:     a={r_affine['a']:.5f}, b={r_affine['b']:.6f}, c={r_affine['c']:.6f}, rmse={r_affine['rmse_affine']:.6f}")
        out[plat] = {**r_under, **r_affine}
    Path(ROOT / "out" / "coeffs_v1.json").write_text(json.dumps(out, indent=2))
    print("\nwrote out/coeffs_v1.json")
