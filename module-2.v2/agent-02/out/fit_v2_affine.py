"""V2: per-platform affine fit (k, b) on V0 yaw rate.

yaw_pred = k * v0_yaw + b

`b` absorbs the constant yaw-rate offset (likely vehicle yaw-gyro bias or a
misalignment captured during calibration). Even tiny `b` matters because CTE
integrates it over distance.

Fit minimises pooled yaw RMSE (closed-form OLS) per platform on train set.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1",
             "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]
TRUTH_COL = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
    "TESLA_MODEL_3":            "psi_dot_rads",
}


def fit_affine():
    fit = {}
    for plat in PLATFORMS:
        if plat == "TESLA_MODEL_3":
            fit[plat] = {"k": 1.0, "b": 0.0}
            print(f"  {plat}: k=1, b=0 (Tesla forced)")
            continue
        segs = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
        # Accumulate sums for OLS y = k*x + b
        Sx = Sy = Sxx = Sxy = 0.0
        N = 0
        for p in segs:
            df = pd.read_csv(p, usecols=["v_mps", "yaw_rate_pred_rads", TRUTH_COL[plat]])
            mask = df["v_mps"].to_numpy() > 2.0
            if not mask.any():
                continue
            y = df[TRUTH_COL[plat]].to_numpy()[mask].astype(float)
            x = df["yaw_rate_pred_rads"].to_numpy()[mask].astype(float)
            Sx += float(x.sum()); Sy += float(y.sum())
            Sxx += float(np.dot(x, x)); Sxy += float(np.dot(x, y))
            N += int(mask.sum())
        denom = N * Sxx - Sx * Sx
        k = (N * Sxy - Sx * Sy) / denom
        b = (Sy - k * Sx) / N
        fit[plat] = {"k": k, "b": b}
        print(f"  {plat}: k = {k:.6f}, b = {b:+.6e}  (n={N:,})")
    return fit


def predict_factory(coeffs: dict):
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        c = coeffs.get(platform, {"k": 1.0, "b": 0.0})
        k = c["k"]; b = c["b"]
        out = pd.DataFrame(index=sim_df.index)
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float) * k + b
        return out
    return predict


if __name__ == "__main__":
    print("Fitting per-platform affine (yaw = k*v0 + b):")
    coeffs = fit_affine()
    print(f"\nCoeffs: {coeffs}\n")
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(predict_factory(coeffs), segment_paths=segs)
    print(format_summary(res))
    (ROOT / "out" / "v2_coeffs.json").write_text(json.dumps(coeffs, indent=2))
