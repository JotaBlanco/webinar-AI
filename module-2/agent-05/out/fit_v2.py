"""V2 fit: understeer + steering-rate lead term + (optional) Mach-E delta cubic.

Per-platform fit of:
    delta_eff = delta_road + tau * delta_dot + delta_bias + alpha3 * delta_road^3
    yaw = scale * v * delta_eff / (L + K_us * v^2)

We pool all train samples per platform, fit via least_squares.
We need delta_dot per segment, computed with np.gradient.
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

L_NOMINAL = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.0,
}

SAMPLE_FILTER_V_MPS = 2.0


def pool_segments(platform):
    segs = find_segments(platform)
    Vs, Ds, Dd, Ys = [], [], [], []
    for p in segs:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        if len(t) < 3:
            continue
        ddot = np.gradient(d, t)
        m = df["v_mps"].to_numpy(float) > SAMPLE_FILTER_V_MPS
        Vs.append(df["v_mps"].to_numpy(float)[m])
        Ds.append(d[m])
        Dd.append(ddot[m])
        Ys.append(df["yaw_rate_meas_rads"].to_numpy(float)[m])
    return (np.concatenate(Vs), np.concatenate(Ds),
            np.concatenate(Dd), np.concatenate(Ys))


def model(v, d, ddot, L, K_us, scale, delta_bias, tau, alpha3):
    d_eff = d + tau * ddot + delta_bias + alpha3 * (d ** 3)
    return scale * v * d_eff / (L + K_us * v * v)


def fit_platform(platform, with_cubic=True):
    v, d, ddot, y = pool_segments(platform)
    L = L_NOMINAL[platform]

    if with_cubic:
        x0 = np.array([0.003, 1.0, 0.0, 0.05, 0.0])
        def resid(t): return model(v, d, ddot, L, *t) - y
    else:
        x0 = np.array([0.003, 1.0, 0.0, 0.05])
        def resid(t):
            K, s, b, tau = t
            return model(v, d, ddot, L, K, s, b, tau, 0.0) - y
    res = least_squares(resid, x0, method="lm", max_nfev=10000)
    if with_cubic:
        K_us, scale, delta_bias, tau, alpha3 = res.x
    else:
        K_us, scale, delta_bias, tau = res.x
        alpha3 = 0.0
    pred = model(v, d, ddot, L, K_us, scale, delta_bias, tau, alpha3)
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    return {
        "K_us": float(K_us),
        "scale": float(scale),
        "delta_bias": float(delta_bias),
        "tau": float(tau),
        "alpha3": float(alpha3),
        "L0": L,
        "rmse_fit": rmse,
        "n_samples": int(len(v)),
    }


def main():
    coeffs = {}
    for platform in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        c = fit_platform(platform)
        coeffs[platform] = c
        print(f"{platform}: n={c['n_samples']:,}  fit rmse={c['rmse_fit']:.5f}")
        print(f"   K_us={c['K_us']:.4g} scale={c['scale']:.4f} bias={c['delta_bias']:+.4g} tau={c['tau']:+.4g} alpha3={c['alpha3']:+.4g}")
    # Tesla: copy from Mach-E as it's same brand family — best guess for unseen.
    # Actually use a generic safe default: K_us tuned to Mach-E, scale 1.0
    coeffs["TESLA_MODEL_3"] = {
        "K_us": coeffs["FORD_MUSTANG_MACH_E_MK1"]["K_us"],
        "scale": 1.0,
        "delta_bias": 0.0,
        "tau": coeffs["FORD_MUSTANG_MACH_E_MK1"]["tau"],
        "alpha3": 0.0,
        "L0": L_NOMINAL["TESLA_MODEL_3"],
    }
    out_path = ROOT / "out" / "coeffs_v2.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
