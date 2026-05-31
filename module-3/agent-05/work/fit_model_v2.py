"""V2: add quadratic steering term g(δ) = g0 + g1·|δ|.

This is a 'polynomial steering scale' from approach-menu — unexplored on this data.
Risk: overfit. We validate on the dev set.

Model:
    delta_eff = (g0 + g1 * abs(delta)) * delta + delta_offset
    yr_ss     = v * delta_eff / (L + K_us * v^2)
    yr        = first-order lag with tau
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
    g0, g1, d0, K_us, tau = params
    g_eff = g0 + g1 * np.abs(delta)
    delta_eff = g_eff * delta + d0
    yr_ss = v * delta_eff / (L + K_us * v * v)
    n = len(t)
    if n == 0:
        return np.zeros(0)
    if tau <= 1e-6:
        return yr_ss.copy()
    dt = np.diff(t)
    alpha = np.where(dt > 0, dt / (tau + dt), 1.0)
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    for k in range(1, n):
        yr[k] = (1 - alpha[k - 1]) * yr[k - 1] + alpha[k - 1] * yr_ss[k]
    return yr


def loss(params, segments, L):
    g0, g1, d0, K_us, tau = params
    if (tau < 0 or K_us < -0.005 or K_us > 0.05 or abs(d0) > 0.02
        or g0 < 0.5 or g0 > 2.0 or abs(g1) > 5.0):
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
    segs = [load_segment_arrays(Path(p)) for p in plat_paths]
    segs = [s for s in segs if s is not None]
    print(f"  {platform}: {len(segs)} train segments")
    # Warm start from V1 fit
    x0 = [1.1, 0.0, 0.0, 0.003, 0.07]
    res = minimize(
        loss, x0, args=(segs, L),
        method="Nelder-Mead",
        options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 3000, "adaptive": True},
    )
    g0, g1, d0, K_us, tau = res.x.tolist()
    print(f"    fit: g0={g0:.4f}, g1={g1:.4f}, d0={d0:.5f}, K_us={K_us:.5f}, "
          f"tau={tau:.4f}, train_loss={res.fun:.6f}")
    return {"g0": g0, "g1": g1, "delta_offset": d0, "K_us": K_us, "tau": tau, "L": L}


def main():
    train, dev = split(dev_fraction=0.25, seed=42)
    coeffs = {}
    for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]:
        coeffs[plat] = fit_platform(plat, train)

    out_path = ROOT / "final-model" / "coeffs_v2.json"
    with out_path.open("w") as fh:
        json.dump(coeffs, fh, indent=2)
    print(json.dumps(coeffs, indent=2))


if __name__ == "__main__":
    main()
