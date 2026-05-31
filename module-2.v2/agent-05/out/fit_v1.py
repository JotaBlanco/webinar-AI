"""Fit a per-platform affine correction to V0 yaw to neutralise CTE drift.

Model V1:  yaw_pred = a_p * yaw_v0 + b_p * v + c_p  (per platform p)
        — but baselined: a_p, b_p, c_p, fit on yaw residuals against truth.

We minimise yaw_rate sum_sq (sample-pooled with v>2 filter) which is convex
in (a,b,c). Solve via closed-form least squares per platform.

We won't use this on Tesla (truth = V0, so residual = 0).
"""
from __future__ import annotations
import sys, os, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05")
os.chdir(ROOT)

PLATFORM_TRUTH = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
    "TESLA_MODEL_3":            "psi_dot_rads",
}

V_FILTER = 2.0

def list_segments(plat):
    base = ROOT / "data" / "sim" / "segments" / plat
    return sorted(base.glob("*/**/sim.csv"))

def fit_platform(plat):
    truth_col = PLATFORM_TRUTH[plat]
    paths = list_segments(plat)
    # Build (X, y) where X = [yaw_v0, v, delta_road, 1], y = yaw_truth
    Xs, ys = [], []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_pred_rads" in df.columns:
            yv0 = df["yaw_rate_pred_rads"].to_numpy(float)
        elif plat == "TESLA_MODEL_3":
            yv0 = df["psi_dot_rads"].to_numpy(float)
        else:
            continue
        v = df["v_mps"].to_numpy(float)
        mask = v > V_FILTER
        if not mask.any():
            continue
        yt = df[truth_col].to_numpy(float)
        delta = df["delta_road_rad"].to_numpy(float)
        X = np.column_stack([yv0[mask], v[mask], delta[mask], np.ones(mask.sum())])
        Xs.append(X)
        ys.append(yt[mask])
    if not Xs:
        return None
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    # Least squares
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {"a": float(coef[0]), "b_v": float(coef[1]), "c_delta": float(coef[2]), "d": float(coef[3]), "n_samples": int(len(y))}

if __name__ == "__main__":
    coeffs = {}
    for plat in PLATFORM_TRUTH:
        if plat == "TESLA_MODEL_3":
            # identity
            coeffs[plat] = {"a": 1.0, "b_v": 0.0, "c_delta": 0.0, "d": 0.0, "n_samples": 0}
            continue
        res = fit_platform(plat)
        print(f"{plat}: {res}")
        coeffs[plat] = res
    out = ROOT / "out" / "v1_coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out}")
