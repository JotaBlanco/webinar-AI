"""Fit V1 understeer & delta-scale per platform, with optional yaw-rate lag term.

Model:
   psi_dot = v * (s_d * delta + tau_d * d(delta)/dt) / (L + K_us * v^2) + b

Where:
   s_d:   steering-angle scale (catches steering-ratio / signed-convention error)
   tau_d: steering-rate lead in seconds
   K_us:  understeer gradient (s^2/m, can be positive or negative)
   b:     constant yaw bias offset (rad/s)
   L:     wheelbase per platform (fixed)

We fit jointly to minimise yaw_rmse, weighted equally per sample.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-10")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import PLATFORM_SCHEMA  # noqa: E402

# Wheelbases (from code/parameters.py — declared here to avoid relative import paths).
L_BY_PLATFORM = {
    "TESLA_MODEL_3": 2.875,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5": 3.00,  # rough; Hyundai not in parameters.py - good prior
}

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def gather_arrays(platform: str, max_segments: int = 60, max_rows_per: int = 4000):
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in seg_root.glob("**/sim.csv") if p.is_file())
    if max_segments and len(paths) > max_segments:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(paths), size=max_segments, replace=False)
        paths = [paths[i] for i in sorted(idx)]
    schema = PLATFORM_SCHEMA[platform]
    tcol = schema["truth_col"]
    deltas, vs, dd_dts, truths = [], [], [], []
    for p in paths:
        df = pd.read_csv(p)
        t = df["t_s"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        if tcol not in df.columns:
            continue
        y = df[tcol].to_numpy(float)
        if len(t) < 10 or np.any(np.diff(t) <= 0):
            continue
        ddot = np.gradient(d, t)
        m = v > 2.0
        d, v, ddot, y = d[m], v[m], ddot[m], y[m]
        if len(d) == 0:
            continue
        if max_rows_per and len(d) > max_rows_per:
            # downsample by stride for diversity
            stride = len(d) // max_rows_per + 1
            d, v, ddot, y = d[::stride], v[::stride], ddot[::stride], y[::stride]
        deltas.append(d); vs.append(v); dd_dts.append(ddot); truths.append(y)
    return (
        np.concatenate(deltas), np.concatenate(vs),
        np.concatenate(dd_dts), np.concatenate(truths),
    )


def fit_platform(platform: str):
    L = L_BY_PLATFORM[platform]
    d, v, ddot, y = gather_arrays(platform)
    n = len(d)
    print(f"  {platform}: n={n}")

    def model(params):
        s_d, tau_d, K_us, b = params
        denom = L + K_us * v * v
        return v * (s_d * d + tau_d * ddot) / denom + b

    def loss(params):
        r = model(params) - y
        return float(np.mean(r * r))

    # Two fits: V1 (no rate term) and V2 (with rate term)
    # V1: s_d, K_us, b ; tau_d fixed=0
    def loss_v1(p3):
        return loss([p3[0], 0.0, p3[1], p3[2]])
    res_v1 = minimize(loss_v1, x0=[1.0, 0.0, 0.0], method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 1e-10, "maxiter": 5000})
    s_d1, K_us1, b1 = res_v1.x
    v1_coeffs = {"s_d": float(s_d1), "tau_d": 0.0, "K_us": float(K_us1), "b": float(b1), "L": L}
    print(f"    V1: s_d={s_d1:.4f} K_us={K_us1:.5f} b={b1:.5f}  rmse={np.sqrt(res_v1.fun):.5f}")

    # V2: full
    res_v2 = minimize(loss, x0=[s_d1, 0.0, K_us1, b1], method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 1e-10, "maxiter": 10000})
    s_d2, tau_d2, K_us2, b2 = res_v2.x
    v2_coeffs = {"s_d": float(s_d2), "tau_d": float(tau_d2), "K_us": float(K_us2), "b": float(b2), "L": L}
    print(f"    V2: s_d={s_d2:.4f} tau_d={tau_d2:.4f} K_us={K_us2:.5f} b={b2:.5f}  rmse={np.sqrt(res_v2.fun):.5f}")
    return v1_coeffs, v2_coeffs


def main():
    v1_all, v2_all = {}, {}
    for p in PLATFORMS:
        v1, v2 = fit_platform(p)
        v1_all[p] = v1
        v2_all[p] = v2
    # Tesla passes through V0 (truth == baseline).
    v1_all["TESLA_MODEL_3"] = {"passthrough": True}
    v2_all["TESLA_MODEL_3"] = {"passthrough": True}

    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "coeffs_v1.json").write_text(json.dumps(v1_all, indent=2))
    (out_dir / "coeffs_v2.json").write_text(json.dumps(v2_all, indent=2))
    print("wrote coeffs_v1.json and coeffs_v2.json")


if __name__ == "__main__":
    main()
