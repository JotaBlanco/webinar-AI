"""Fit per-platform understeer-gradient correction.

Model:
    yaw = (v * delta) / (L * (1 + K_us * v^2 / L)) * scale
        = v * delta / (L + K_us * v^2) * scale

We allow:
    - K_us (understeer gradient, s²/m)
    - scale (multiplicative gain on yaw)
    - delta_bias (additive radian offset on delta_road)
    - L_scale (multiplicative scale on wheelbase)

Fit per platform on a route-grouped split. Uses scipy least_squares.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "out"))
from score import find_segments  # noqa: E402

# nominal wheelbases
L_NOMINAL = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.0,  # rough — won't matter, we fit a scale
}

SAMPLE_FILTER_V_MPS = 2.0


def model(v, delta, L, K_us, scale, delta_bias):
    d = delta + delta_bias
    return scale * (v * d) / (L + K_us * v * v)


def pool_segments(platform):
    segs = find_segments(platform)
    Vs, Ds, Ys = [], [], []
    for p in segs:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        mask = df["v_mps"] > SAMPLE_FILTER_V_MPS
        Vs.append(df["v_mps"].to_numpy()[mask])
        Ds.append(df["delta_road_rad"].to_numpy()[mask])
        Ys.append(df["yaw_rate_meas_rads"].to_numpy()[mask])
    return np.concatenate(Vs), np.concatenate(Ds), np.concatenate(Ys)


def fit_platform(platform):
    v, d, y_truth = pool_segments(platform)
    L0 = L_NOMINAL[platform]

    def resid(theta):
        K_us, scale, delta_bias = theta
        pred = model(v, d, L0, K_us, scale, delta_bias)
        return pred - y_truth

    x0 = np.array([0.0, 1.0, 0.0])
    res = least_squares(resid, x0, method="lm", max_nfev=5000)
    K_us, scale, delta_bias = res.x
    L_scale = 1.0
    pred = model(v, d, L0, K_us, scale, delta_bias)
    rmse = float(np.sqrt(np.mean((pred - y_truth) ** 2)))
    bias = float(np.mean(pred - y_truth))
    # Baseline (V0)
    v0_pred = (v * d) / L0
    rmse0 = float(np.sqrt(np.mean((v0_pred - y_truth) ** 2)))
    return {
        "K_us": float(K_us),
        "scale": float(scale),
        "delta_bias": float(delta_bias),
        "L_scale": float(L_scale),
        "L0": L0,
        "rmse_fit": rmse,
        "bias_fit": bias,
        "rmse_v0": rmse0,
        "n_samples": int(len(v)),
    }


def main():
    coeffs = {}
    for platform in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        c = fit_platform(platform)
        coeffs[platform] = c
        print(f"{platform}: n={c['n_samples']:,}  V0 rmse={c['rmse_v0']:.5f} -> fit rmse={c['rmse_fit']:.5f}")
        print(f"   K_us={c['K_us']:.6g}  scale={c['scale']:.5f}  delta_bias={c['delta_bias']:+.5f}  L_scale={c['L_scale']:.5f}")
    out_path = ROOT / "out" / "coeffs.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
