"""Fit only (g, delta0_fallback) per platform — smaller free-parameter set
so the optimisation can't trade off yaw RMSE against signed bias.
"""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]

def per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())

def predict_core(df, p, use_per_seg):
    if use_per_seg:
        delta0 = per_segment_delta0(df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0_fallback"]
    delta = (df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr

def joint_loss(g, delta0_fb, base, dfs, use_per_seg, alpha_bias=1.0):
    """Composite loss: yaw MSE + alpha * signed_bias^2 — discourages residual mean drift."""
    p = dict(base)
    p["g"] = g
    p["delta0_fallback"] = delta0_fb
    tot_sq = 0.0; tot_signed = 0.0; n = 0
    for df in dfs:
        pred = predict_core(df, p, use_per_seg)
        m = df["v_mps"].to_numpy() > 2.0
        resid = pred[m] - df["yaw_rate_meas_rads"].to_numpy()[m]
        tot_sq += float(np.sum(resid * resid))
        tot_signed += float(np.sum(resid))
        n += int(m.sum())
    mse = tot_sq / n
    mean = tot_signed / n
    return mse + alpha_bias * mean * mean

def load_dfs(plat, stride=5, cap=200):
    csvs = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))
    csvs = csvs[::stride][:cap]
    dfs = []
    for c in csvs:
        df = pd.read_csv(c, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        if len(df) >= 200:
            dfs.append(df)
    return dfs

V1 = {
    "FORD_F_150_LIGHTNING_MK1":   {"g":0.863,"L_eff":3.26, "K_us":0.00350,"tau":0.060,"delta0_fallback":0.00133, "per_seg": False},
    "FORD_MUSTANG_MACH_E_MK1":    {"g":0.891,"L_eff":2.22, "K_us":0.00150,"tau":0.069,"delta0_fallback":-0.0001, "per_seg": True},
    "HYUNDAI_IONIQ_5":            {"g":0.938,"L_eff":2.887,"K_us":0.00289,"tau":0.062,"delta0_fallback":0.0,    "per_seg": True},
}

out = {}
for plat, p0 in V1.items():
    print(f"\n=== {plat} (per_seg={p0['per_seg']}) ===")
    dfs = load_dfs(plat)
    print(f"  loaded {len(dfs)} segments")
    base = {k:v for k,v in p0.items() if k not in ("per_seg",)}
    use_per = p0["per_seg"]
    x0 = np.array([p0["g"], p0["delta0_fallback"]])
    def f(x): return joint_loss(x[0], x[1], base, dfs, use_per, alpha_bias=2.0)
    print(f"  V1 joint loss: {f(x0):.8e}")
    res = minimize(f, x0, method="Nelder-Mead",
                   options={"xatol":1e-6,"fatol":1e-10,"maxiter":300})
    print(f"  V3 joint loss: {res.fun:.8e}, g={res.x[0]:.5f} d0={res.x[1]:.6f}")
    base["g"] = float(res.x[0])
    base["delta0_fallback"] = float(res.x[1])
    out[plat] = base

with open(ROOT / "out/v3_params.json", "w") as f:
    json.dump(out, f, indent=2)
print("\n", json.dumps(out, indent=2))
