"""Fit per-platform V1 model:

    yaw_pred = v * delta / (L + K_us * v^2) + bias

minimising yaw_rate RMSE per platform. Use sim/segments for training. Tesla is
skipped (V0 IS its truth).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-06")
DATA = ROOT / "data" / "sim" / "segments"

PLATFORMS = [
    "FORD_F_150_LIGHTNING_MK1",
    "FORD_MUSTANG_MACH_E_MK1",
    "HYUNDAI_IONIQ_5",
]

# Wheelbase priors (Hyundai unknown — use 3.0 as start)
L_PRIOR = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "HYUNDAI_IONIQ_5": 3.0,
}


def gather(platform: str) -> dict:
    """Concatenate all rows for a platform; subsample to keep mem manageable."""
    paths = sorted((DATA / platform).glob("*/*/*/sim.csv"))
    deltas, vs, yr_meas, ddt = [], [], [], []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s", "delta_road_rad", "v_mps", "yaw_rate_meas_rads"])
        except Exception:
            continue
        t = df["t_s"].to_numpy()
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        d = df["delta_road_rad"].to_numpy()
        v = df["v_mps"].to_numpy()
        yr = df["yaw_rate_meas_rads"].to_numpy()
        # derivative of delta_road
        dd = np.gradient(d, t)
        mask = v > 2.0
        deltas.append(d[mask])
        vs.append(v[mask])
        yr_meas.append(yr[mask])
        ddt.append(dd[mask])
    return {
        "delta": np.concatenate(deltas),
        "v": np.concatenate(vs),
        "yr": np.concatenate(yr_meas),
        "ddt_delta": np.concatenate(ddt),
    }


def predict_v1(d, v, L, Kus, bias):
    return v * d / (L + Kus * v * v) + bias


def fit_v1(platform: str) -> dict:
    data = gather(platform)
    d = data["delta"]
    v = data["v"]
    y = data["yr"]
    L0 = L_PRIOR[platform]

    def loss(params):
        L, Kus, bias = params
        pred = predict_v1(d, v, L, Kus, bias)
        return float(np.mean((pred - y) ** 2))

    x0 = [L0, 0.0, 0.0]
    bounds = [(1.5, 5.5), (-0.05, 0.05), (-0.02, 0.02)]
    res = minimize(loss, x0, bounds=bounds, method="L-BFGS-B")
    rmse0 = float(np.sqrt(np.mean((predict_v1(d, v, L0, 0.0, 0.0) - y) ** 2)))
    rmse1 = float(np.sqrt(res.fun))
    return {
        "platform": platform,
        "L": float(res.x[0]),
        "Kus": float(res.x[1]),
        "bias": float(res.x[2]),
        "L_prior": L0,
        "rmse_prior": rmse0,
        "rmse_fit": rmse1,
        "n": int(len(d)),
        "converged": bool(res.success),
    }


if __name__ == "__main__":
    out = {}
    for plat in PLATFORMS:
        print(f"fitting {plat} ...")
        r = fit_v1(plat)
        print(r)
        out[plat] = r
    with open(ROOT / "out" / "coeffs_v1.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote coeffs_v1.json")
