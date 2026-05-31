"""Fit per-platform yaw-rate model.

Model variants:
  V0:   yr = (v/L) * tan(delta)
  V1:   yr = v * delta / (L + K_us * v^2)        — linear understeer
  V2:   yr = v * (a*delta + b) / (L + K_us * v^2) — steer scale + bias

We fit (K_us, a, b) per platform on the merged sim segments.
For HYUNDAI_IONIQ_5 we don't have an L; use a sensible default and let K absorb.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03")

# Wheelbases (m) — from code/parameters.py
L_BY_PLATFORM = {
    "TESLA_MODEL_3":             2.875,
    "FORD_MUSTANG_MACH_E_MK1":   2.984,
    "FORD_F_150_LIGHTNING_MK1":  3.70,
    "HYUNDAI_IONIQ_5":           3.00,  # IONIQ 5 official wheelbase ~3.0 m
}


def gather_paths():
    root = REPO / "data" / "sim" / "segments"
    paths = sorted(root.glob("*/**/sim.csv"))
    by_plat: dict[str, list[Path]] = {}
    for p in paths:
        with p.open() as f:
            header = f.readline().rstrip("\n").split(",")
        if "yaw_rate_meas_rads" not in header:
            continue
        platform = p.resolve().parents[3].name
        by_plat.setdefault(platform, []).append(p)
    return by_plat


def load_concat(paths, v_min=2.0, max_segs=None):
    if max_segs is not None:
        paths = paths[:max_segs]
    dfs = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "v_mps", "delta_road_rad", "yaw_rate_meas_rads"])
        except Exception:
            continue
        df = df[df["v_mps"] > v_min]
        if len(df) < 10:
            continue
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


def fit_platform(platform, paths, L):
    df = load_concat(paths, v_min=2.0)
    v = df["v_mps"].to_numpy()
    d = df["delta_road_rad"].to_numpy()
    y = df["yaw_rate_meas_rads"].to_numpy()

    # V0: tan(delta)
    yr_v0 = (v / L) * np.tan(d)
    rmse_v0 = float(np.sqrt(np.mean((yr_v0 - y) ** 2)))

    # V1: linear understeer. y_pred = v * d / (L + K * v^2)
    # Linearise: y * (L + K v^2) = v*d -> y*L + K*y*v^2 = v*d
    # K = (v*d - y*L) / (y*v^2). Use ordinary least-squares regression instead:
    # Find K minimising sum((v*d/(L+K*v^2) - y)^2)
    def loss_v1(theta):
        K = theta[0]
        denom = L + K * v * v
        yr = v * d / denom
        return float(np.mean((yr - y) ** 2))

    # Bracket: K ~ 0..0.1
    res1 = minimize(loss_v1, x0=[0.005], method="Nelder-Mead",
                    options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 2000})
    K1 = float(res1.x[0])
    rmse_v1 = math.sqrt(loss_v1(res1.x))

    # V2: steer scale + bias. y_pred = v * (a*d + b) / (L + K*v^2)
    def loss_v2(theta):
        K, a, b = theta
        denom = L + K * v * v
        yr = v * (a * d + b) / denom
        return float(np.mean((yr - y) ** 2))

    res2 = minimize(loss_v2, x0=[K1, 1.0, 0.0], method="Nelder-Mead",
                    options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 5000})
    K2, a2, b2 = (float(x) for x in res2.x)
    rmse_v2 = math.sqrt(loss_v2(res2.x))

    return {
        "platform": platform,
        "L": L,
        "n_samples": int(len(df)),
        "rmse_v0": rmse_v0,
        "rmse_v1": rmse_v1,
        "K_v1": K1,
        "rmse_v2": rmse_v2,
        "K_v2": K2,
        "a_v2": a2,
        "b_v2": b2,
    }


def main():
    by_plat = gather_paths()
    out = {}
    for platform, paths in sorted(by_plat.items()):
        L = L_BY_PLATFORM.get(platform, 2.9)
        print(f"Fitting {platform}: {len(paths)} segments, L={L} ...", flush=True)
        res = fit_platform(platform, paths, L)
        out[platform] = res
        print(f"  v0 rmse={res['rmse_v0']:.5f}  v1 rmse={res['rmse_v1']:.5f} (K={res['K_v1']:.5f})  "
              f"v2 rmse={res['rmse_v2']:.5f} (K={res['K_v2']:.5f}, a={res['a_v2']:.4f}, b={res['b_v2']:+.5f})")

    (REPO / "out" / "coeffs.json").write_text(json.dumps(out, indent=2))
    print("\nWrote out/coeffs.json")


if __name__ == "__main__":
    main()
