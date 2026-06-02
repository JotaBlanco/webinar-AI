"""Refit V1's (g, L_eff, K_us, tau, delta0) per platform on yaw RMSE.

Uses scipy.optimize.minimize over a wrapper that runs predict_v1-equivalent
math with per-segment delta0 (for platforms with that flag) or global.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
data_full = ROOT / "data" / "sim" / "segments"


def per_segment_delta0(df, fallback, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(df.loc[mask, "delta_road_rad"].median())


def predict_parametric(df, g, L_eff, K_us, tau, delta0_global, use_per_seg, delta0_fallback):
    if use_per_seg:
        delta0 = per_segment_delta0(df, delta0_fallback)
    else:
        delta0 = delta0_global
    delta = (df["delta_road_rad"].to_numpy() - delta0) * g
    v = df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


PLAT_CFG = {
    "FORD_F_150_LIGHTNING_MK1": dict(use_per_seg=False, x0=[0.863, 3.26, 0.0035, 0.060, 0.00133, 0.0]),
    "FORD_MUSTANG_MACH_E_MK1": dict(use_per_seg=True, x0=[0.891, 2.22, 0.0015, 0.069, 0.0, -0.0001]),
    "HYUNDAI_IONIQ_5": dict(use_per_seg=True, x0=[0.938, 2.887, 0.00289, 0.062, 0.0, 0.0]),
}


def loss_for_plat(plat):
    cfg = PLAT_CFG[plat]
    use_per_seg = cfg["use_per_seg"]
    # Cache segments
    segs = []
    for sim_csv in sorted((data_full / plat).rglob("sim.csv")):
        df = pd.read_csv(sim_csv)
        if "yaw_rate_meas_rads" not in df.columns: continue
        segs.append(df)

    def loss(x):
        g, L_eff, K_us, tau, delta0_global, delta0_fallback = x
        if L_eff < 0.5 or tau < 0.001 or K_us < 0:
            return 1e9
        sumsq = 0.0
        n = 0
        for df in segs:
            yr = predict_parametric(df, g, L_eff, K_us, tau, delta0_global, use_per_seg, delta0_fallback)
            r = df["yaw_rate_meas_rads"].to_numpy() - yr
            sumsq += float(np.sum(r * r))
            n += len(r)
        return sumsq / n
    return loss, cfg["x0"]


def main():
    out = {}
    for plat in PLATFORMS:
        print(f"\n--- {plat} ---")
        loss, x0 = loss_for_plat(plat)
        l0 = loss(x0)
        print(f"  initial MSE={l0:.6e} (RMSE={np.sqrt(l0):.5f})")
        res = minimize(loss, x0, method="Nelder-Mead", options={"xatol":1e-5, "fatol":1e-9, "maxiter":300})
        print(f"  final   MSE={res.fun:.6e} (RMSE={np.sqrt(res.fun):.5f}) iters={res.nit}")
        print(f"  x={res.x}")
        g, L_eff, K_us, tau, delta0_global, delta0_fallback = res.x
        out[plat] = {
            "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
            "tau": float(tau), "delta0_global": float(delta0_global),
            "delta0_fallback": float(delta0_fallback),
            "use_per_segment_delta0": PLAT_CFG[plat]["use_per_seg"],
        }
    (ROOT / "models" / "v1_refit" / "coeffs.json").write_text(json.dumps(out, indent=2))
    print("\nSaved", ROOT / "models" / "v1_refit" / "coeffs.json")


if __name__ == "__main__":
    main()
