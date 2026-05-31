"""V2 fitter: per-platform understeer + bias.

Model: yaw_pred = alpha * v0 / (1 + K * v^2) + beta

Closed form for (alpha, beta) given K via OLS; outer 1-D search over K.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

ROOT = Path(__file__).resolve().parents[1]
SEGMENTS = ROOT / "data" / "sim" / "segments"

TRUTH_COL = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
}


def load_platform(platform: str):
    paths = sorted((SEGMENTS / platform).glob("**/sim.csv"))
    tc = TRUTH_COL[platform]
    Vs, Ys, V0s = [], [], []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "v_mps", "delta_road_rad", tc, "yaw_rate_pred_rads"])
        except (ValueError, KeyError):
            continue
        if len(df) < 2:
            continue
        m = df["v_mps"] > 2.0
        Vs.append(df.loc[m, "v_mps"].to_numpy(dtype=float))
        Ys.append(df.loc[m, tc].to_numpy(dtype=float))
        V0s.append(df.loc[m, "yaw_rate_pred_rads"].to_numpy(dtype=float))
    return np.concatenate(Vs), np.concatenate(Ys), np.concatenate(V0s)


def fit(v, y, v0):
    def rmse_given_K(K):
        base = v0 / (1.0 + K * v * v)
        X = np.column_stack([base, np.ones_like(base)])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ coef
        return float(np.sqrt(np.mean((pred - y) ** 2))), float(coef[0]), float(coef[1])

    # 1-D minimisation over K
    def f(K):
        return rmse_given_K(K)[0]
    res = minimize_scalar(f, bracket=(-0.001, 0.001, 0.01), method="brent", options={"xtol": 1e-9})
    K_star = float(res.x)
    rmse, alpha, beta = rmse_given_K(K_star)
    rmse_v0 = float(np.sqrt(np.mean((v0 - y) ** 2)))
    return {"alpha": alpha, "K": K_star, "beta": beta, "rmse_v0": rmse_v0, "rmse_v2": rmse}


if __name__ == "__main__":
    out = {"TESLA_MODEL_3": {"alpha": 1.0, "K": 0.0, "beta": 0.0,
                              "rmse_v0": 0.0, "rmse_v2": 0.0}}
    for plat in TRUTH_COL:
        print(f"\n=== {plat} ===")
        v, y, v0 = load_platform(plat)
        r = fit(v, y, v0)
        print(f"  V0 rmse:       {r['rmse_v0']:.6f}")
        print(f"  V2 fit: alpha={r['alpha']:.5f}, K={r['K']:.6f}, beta={r['beta']:+.6f}, rmse={r['rmse_v2']:.6f}")
        out[plat] = r
    (ROOT / "out" / "coeffs_v2.json").write_text(json.dumps(out, indent=2))
    print("\nwrote out/coeffs_v2.json")
