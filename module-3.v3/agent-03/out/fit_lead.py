"""Fit V1 + lead-compensator: yr = V1(yr_ss + K_d * d_delta/dt) lagged.

We modify V1's steady-state input to include a feedforward of d_delta:
  delta_eff = delta + K_d * d(delta)/dt
  yr_ss = v * delta_eff / (L_eff + K_us*v^2)
  then first-order lag with tau.

We refit (g, L_eff, K_us, tau, K_d, delta0) jointly. This is structurally
different from V1: V1 has only a low-pass smoothing; this adds a high-pass
boost (lead) directly into the steady-state input. Together they form a
lead-lag compensator — that's the classical fix for "first-order lag is
band-aiding transient dynamics".
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


def predict_lead(df, g, L_eff, K_us, tau, K_d, delta0):
    t = df["t_s"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta_raw = df["delta_road_rad"].to_numpy()
    d_delta = np.gradient(delta_raw, t) if len(t) > 1 else np.zeros_like(delta_raw)
    delta_eff = (delta_raw - delta0) + K_d * d_delta
    delta_eff *= g
    yr_ss = v * delta_eff / (L_eff + K_us * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


CFG = {
    "FORD_F_150_LIGHTNING_MK1": dict(use_per_seg=False, x0=[0.863, 3.26, 0.00350, 0.060, 0.05, 0.00133]),
    "FORD_MUSTANG_MACH_E_MK1":  dict(use_per_seg=True,  x0=[0.891, 2.22, 0.00150, 0.069, 0.05, -0.0001]),
    "HYUNDAI_IONIQ_5":          dict(use_per_seg=True,  x0=[0.938, 2.887, 0.00289, 0.062, 0.05, 0.0]),
}


def fit_one(plat):
    cfg = CFG[plat]
    segs = []
    delta0_segs = []
    for sim_csv in sorted((data_full / plat).rglob("sim.csv")):
        df = pd.read_csv(sim_csv)
        if "yaw_rate_meas_rads" not in df.columns: continue
        segs.append(df)
        if cfg["use_per_seg"]:
            delta0_segs.append(per_segment_delta0(df, cfg["x0"][5]))
        else:
            delta0_segs.append(cfg["x0"][5])
    delta0_segs = np.array(delta0_segs)

    def loss(x):
        g, L_eff, K_us, tau, K_d, delta0_fallback = x
        if L_eff < 1.0 or L_eff > 6 or tau < 0.005 or tau > 0.5 or K_us < 0 or K_us > 0.02 or g < 0.3 or g > 2 or abs(K_d) > 0.5:
            return 1e9
        sumsq = 0.0
        n = 0
        for df, d0 in zip(segs, delta0_segs):
            if cfg["use_per_seg"]:
                d0_eff = d0 if not np.isnan(d0) else delta0_fallback
            else:
                d0_eff = delta0_fallback
            yr = predict_lead(df, g, L_eff, K_us, tau, K_d, d0_eff)
            r = df["yaw_rate_meas_rads"].to_numpy() - yr
            sumsq += float(np.sum(r*r))
            n += len(r)
        return sumsq / n

    x0 = cfg["x0"]
    print(f"  init RMSE={np.sqrt(loss(x0)):.5f}")
    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol":1e-5,"fatol":1e-10,"maxiter":150})
    print(f"  final RMSE={np.sqrt(res.fun):.5f} x={res.x}")
    g, L_eff, K_us, tau, K_d, delta0_fallback = res.x
    return {
        "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
        "tau": float(tau), "K_d": float(K_d),
        "delta0_fallback": float(delta0_fallback),
        "use_per_segment_delta0": cfg["use_per_seg"],
    }


def main():
    out = {}
    for plat in PLATFORMS:
        print(f"\n--- {plat} ---")
        out[plat] = fit_one(plat)
    out_path = ROOT / "models" / "lead_compensator"
    out_path.mkdir(exist_ok=True)
    (out_path / "coeffs.json").write_text(json.dumps(out, indent=2))
    print("Saved coeffs.json")


if __name__ == "__main__":
    main()
