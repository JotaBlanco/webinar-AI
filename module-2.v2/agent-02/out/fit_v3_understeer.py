"""V3: understeer-aware affine + nonlinear features.

Hypotheses to try:
  (a) yaw = k * v0 / (1 + K_us * v^2) + b   — classic understeer coeff
  (b) yaw = (k0 + k1 * v0^2 * sign(v0)) * v0 + b — cubic in yaw to capture saturation
  (c) yaw = k * v0 + b + c * delta_road_rad   — steering bias term

We compare with V2 affine as control. Fit per platform; select the lowest
yaw-RMSE per-platform variant.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

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


def collect(plat: str):
    segs = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
    xs, vs, ys = [], [], []
    for p in segs:
        df = pd.read_csv(p, usecols=["v_mps", "yaw_rate_pred_rads", TRUTH_COL[plat]])
        mask = df["v_mps"].to_numpy() > 2.0
        if not mask.any():
            continue
        xs.append(df["yaw_rate_pred_rads"].to_numpy()[mask].astype(float))
        vs.append(df["v_mps"].to_numpy()[mask].astype(float))
        ys.append(df[TRUTH_COL[plat]].to_numpy()[mask].astype(float))
    return np.concatenate(xs), np.concatenate(vs), np.concatenate(ys)


def fit_understeer(x, v, y):
    # y = (k * x) / (1 + K_us * v^2) + b
    def res(p):
        k, K_us, b = p
        return (k * x) / (1.0 + K_us * v * v) + b - y
    p0 = [1.0, 0.0, 0.0]
    out = least_squares(res, p0, method="trf")
    return out.x  # k, K_us, b


def predict_factory(coeffs: dict):
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        c = coeffs.get(platform, {"k": 1.0, "K_us": 0.0, "b": 0.0})
        k = c["k"]; K_us = c["K_us"]; b = c["b"]
        v = sim_df["v_mps"].to_numpy(dtype=float)
        x = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        yp = (k * x) / (1.0 + K_us * v * v) + b
        out = pd.DataFrame(index=sim_df.index)
        out["yaw_rate_pred_rads"] = yp
        return out
    return predict


if __name__ == "__main__":
    coeffs = {}
    for plat in PLATFORMS:
        if plat == "TESLA_MODEL_3":
            coeffs[plat] = {"k": 1.0, "K_us": 0.0, "b": 0.0}
            print(f"  {plat}: forced k=1")
            continue
        x, v, y = collect(plat)
        k, K_us, b = fit_understeer(x, v, y)
        coeffs[plat] = {"k": float(k), "K_us": float(K_us), "b": float(b)}
        print(f"  {plat}: k={k:.5f}, K_us={K_us:+.5e}, b={b:+.5e}  (n={len(x):,})")

    print(f"\nCoeffs: {json.dumps(coeffs, indent=2)}\n")
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(predict_factory(coeffs), segment_paths=segs)
    print(format_summary(res))
    (ROOT / "out" / "v3_coeffs.json").write_text(json.dumps(coeffs, indent=2))
