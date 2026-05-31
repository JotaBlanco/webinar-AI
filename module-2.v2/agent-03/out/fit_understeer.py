"""Fit understeer coefficient per platform.

Model: yaw_rate = v * delta / (L * (1 + K * v^2))
Equivalent: yaw_rate = (v/L)*delta / (1 + K * v^2)
For small delta, tan(delta) ~= delta. We'll use tan(delta) to keep parity with V0
nonlinearity at large angles.

Loss: pooled yaw RMSE on samples with v>2 m/s.
"""
from __future__ import annotations
import math
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar, minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-03")
import os
os.chdir(ROOT)

L_BY_PLATFORM = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          3.0,  # standard, will check
    "TESLA_MODEL_3":            2.875,
}

def collect_samples(platform):
    """Concat (v, delta_road, yr_truth) across all sim segments for platform."""
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(base.glob("**/sim.csv"))
    vs, ds, ys = [], [], []
    for p in paths:
        df = pd.read_csv(p, usecols=["v_mps","delta_road_rad","yaw_rate_meas_rads"])
        m = df["v_mps"] > 2.0
        vs.append(df.loc[m,"v_mps"].to_numpy())
        ds.append(df.loc[m,"delta_road_rad"].to_numpy())
        ys.append(df.loc[m,"yaw_rate_meas_rads"].to_numpy())
    return np.concatenate(vs), np.concatenate(ds), np.concatenate(ys), len(paths)

def fit_K(v, delta, yr_truth, L):
    # Search log10(K)
    def loss(logK):
        K = 10.0**logK
        pred = (v * np.tan(delta)) / (L * (1.0 + K * v*v))
        return float(np.mean((pred - yr_truth)**2))
    res = minimize_scalar(loss, bounds=(-6.0, 0.0), method="bounded",
                          options={"xatol":1e-4})
    K = 10.0**res.x
    pred = (v * np.tan(delta)) / (L * (1.0 + K * v*v))
    rmse = math.sqrt(float(np.mean((pred - yr_truth)**2)))
    bias = float(np.mean(pred - yr_truth))
    # V0 baseline
    pred0 = (v * np.tan(delta)) / L
    rmse0 = math.sqrt(float(np.mean((pred0 - yr_truth)**2)))
    bias0 = float(np.mean(pred0 - yr_truth))
    return K, rmse, bias, rmse0, bias0

def fit_K_and_steer_offset(v, delta, yr_truth, L):
    """Add small zero-offset on delta_road (radians)."""
    def loss(params):
        logK, doff = params
        K = 10.0**logK
        d = delta - doff
        pred = (v * np.tan(d)) / (L * (1.0 + K * v*v))
        return float(np.mean((pred - yr_truth)**2))
    res = minimize(loss, x0=[-3.0, 0.0], method="Nelder-Mead",
                   options={"xatol":1e-5, "fatol":1e-10, "maxiter":2000})
    logK, doff = res.x
    K = 10.0**logK
    d = delta - doff
    pred = (v * np.tan(d)) / (L * (1.0 + K * v*v))
    rmse = math.sqrt(float(np.mean((pred - yr_truth)**2)))
    bias = float(np.mean(pred - yr_truth))
    return K, doff, rmse, bias

def main():
    print(f"{'platform':30s} {'L':>6s} {'K':>10s} {'doff':>10s} {'yaw_rmse':>10s} {'bias':>10s} | {'rmse_v0':>10s} {'bias_v0':>10s}")
    coeffs = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        v, d, y, n = collect_samples(plat)
        L = L_BY_PLATFORM[plat]
        K, rmse, bias, rmse0, bias0 = fit_K(v, d, y, L)
        K2, doff2, rmse2, bias2 = fit_K_and_steer_offset(v, d, y, L)
        print(f"{plat:30s} {L:6.3f} K_only: {K:.5f} rmse={rmse:.5f} bias={bias:+.5f} | v0_rmse={rmse0:.5f} v0_bias={bias0:+.5f}  [n_seg={n}, n_samp={len(v)}]")
        print(f"{'  +offset':30s} {L:6.3f} K={K2:.5f} doff={doff2:+.5f}rad ({math.degrees(doff2):+.3f}deg) rmse={rmse2:.5f} bias={bias2:+.5f}")
        coeffs[plat] = {"L": L, "K": K2, "delta_offset_rad": doff2,
                        "K_no_offset": K, "rmse_fit": rmse2, "rmse_v0": rmse0}
    import json
    Path("out").mkdir(exist_ok=True)
    with open("out/coeffs.json","w") as f:
        json.dump(coeffs, f, indent=2)
    print("\nSaved out/coeffs.json")

if __name__ == "__main__":
    main()
