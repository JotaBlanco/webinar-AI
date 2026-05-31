"""Fit per-platform lateral model: steady-state understeer + first-order lag.

Model:
    yr_ss[k] = v[k] * (g * delta_road[k] + delta_offset) / (L + K_us * v[k]^2)
    yr[k]    = (1 - alpha[k]) * yr[k-1] + alpha[k] * yr_ss[k]   where alpha[k] = dt[k] / (tau + dt[k])

Parameters fit per platform: g, delta_offset, K_us, tau. L from openpilot prior.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))

os.chdir(ROOT)

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from split import split
from score import score

# Wheelbase priors from code/parameters.py (read-only refs)
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


def load_segment_arrays(path: Path):
    df = pd.read_csv(path)
    cols_needed = ["t_s", "v_mps", "delta_road_rad", "yaw_rate_meas_rads"]
    for c in cols_needed:
        if c not in df.columns:
            return None
    df = df.dropna(subset=cols_needed).reset_index(drop=True)
    if len(df) < 5:
        return None
    t = df["t_s"].to_numpy(dtype=float)
    v = df["v_mps"].to_numpy(dtype=float)
    delta = df["delta_road_rad"].to_numpy(dtype=float)
    yr_truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
    if np.any(np.diff(t) <= 0):
        return None
    return t, v, delta, yr_truth


def predict_one(t, v, delta, params, L):
    g, delta_offset, K_us, tau = params
    yr_ss = v * (g * delta + delta_offset) / (L + K_us * v * v)
    n = len(t)
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    dt = np.diff(t)
    if tau <= 1e-6:
        yr[:] = yr_ss
        return yr
    alpha = dt / (tau + dt)  # per-step low-pass coefficient
    for k in range(1, n):
        yr[k] = (1 - alpha[k - 1]) * yr[k - 1] + alpha[k - 1] * yr_ss[k]
    return yr


def loss(params, segments, L):
    g, delta_offset, K_us, tau = params
    # Light bounds via penalty
    if tau < 0 or K_us < -0.005 or K_us > 0.05 or abs(delta_offset) > 0.02 or g < 0.5 or g > 2.0:
        return 1e6
    total_sq = 0.0
    total_n = 0
    for (t, v, delta, yr_truth) in segments:
        yr_pred = predict_one(t, v, delta, params, L)
        mask = v > 2.0
        resid = (yr_pred - yr_truth)[mask]
        total_sq += float(np.sum(resid * resid))
        total_n += int(mask.sum())
    return np.sqrt(total_sq / max(total_n, 1))


def fit_platform(platform: str, train_paths: list[Path]):
    L = L_BY_PLATFORM[platform]
    plat_paths = [p for p in train_paths if Path(p).parts[-5] == platform]
    segs = []
    for p in plat_paths:
        arr = load_segment_arrays(Path(p))
        if arr is not None:
            segs.append(arr)
    print(f"  {platform}: {len(segs)} train segments")

    # Initial guess from approach-menu defaults
    x0 = [1.0, 0.0, 0.002, 0.06]
    res = minimize(
        loss,
        x0,
        args=(segs, L),
        method="Nelder-Mead",
        options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 2000, "adaptive": True},
    )
    g, d0, K_us, tau = res.x.tolist()
    print(f"    fit: g={g:.4f}, d0={d0:.5f}, K_us={K_us:.5f}, tau={tau:.4f}, loss={res.fun:.6f}")
    return {"g": g, "delta_offset": d0, "K_us": K_us, "tau": tau, "L": L}


def main():
    train, dev = split(dev_fraction=0.25, seed=42)
    coeffs = {}
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]:
        coeffs[plat] = fit_platform(plat, train)

    out_path = ROOT / "final-model" / "coeffs.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        json.dump(coeffs, fh, indent=2)
    print(f"\nWrote {out_path}")
    print(json.dumps(coeffs, indent=2))


if __name__ == "__main__":
    main()
