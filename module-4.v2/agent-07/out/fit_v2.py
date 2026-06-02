"""Fit V2 = V1 shape with per-segment delta0 enabled for all 3 platforms,
plus jointly re-fit (g, L_eff, K_us, tau) per platform on a deterministic
subsample of the train segments. Yaw-rate MSE loss.
"""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())

def predict_core(df, p):
    delta0 = per_segment_delta0(df, fallback=p["delta0_fallback"])
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

def loss_for_platform(params, dfs):
    g, L_eff, K_us, tau, delta0_fb = params
    if L_eff <= 0.1 or tau <= 0.001 or K_us < 0:
        return 1e9
    p = {"g": g, "L_eff": L_eff, "K_us": K_us, "tau": tau, "delta0_fallback": delta0_fb}
    tot = 0.0; n = 0
    for df in dfs:
        pred = predict_core(df, p)
        m = df["v_mps"].to_numpy() > 2.0
        resid = pred[m] - df["yaw_rate_meas_rads"].to_numpy()[m]
        tot += float(np.sum(resid * resid))
        n += int(m.sum())
    return tot / n if n else 1e9

def load_dfs(plat, stride=8, cap=200):
    csvs = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))
    csvs = csvs[::stride][:cap]
    dfs = []
    for c in csvs:
        df = pd.read_csv(c, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        if len(df) >= 200:
            dfs.append(df)
    return dfs

V1 = {
    "FORD_F_150_LIGHTNING_MK1":   {"g":0.863,"L_eff":3.26, "K_us":0.00350,"tau":0.060,"delta0_fallback":0.00133},
    "FORD_MUSTANG_MACH_E_MK1":    {"g":0.891,"L_eff":2.22, "K_us":0.00150,"tau":0.069,"delta0_fallback":-0.0001},
    "HYUNDAI_IONIQ_5":            {"g":0.938,"L_eff":2.887,"K_us":0.00289,"tau":0.062,"delta0_fallback":0.0},
}

out = {}
for plat, p0 in V1.items():
    print(f"\n=== {plat} ===")
    dfs = load_dfs(plat)
    print(f"  loaded {len(dfs)} segments")
    x0 = np.array([p0["g"], p0["L_eff"], p0["K_us"], p0["tau"], p0["delta0_fallback"]])
    print(f"  V1 loss: {loss_for_platform(x0, dfs):.8f}")
    res = minimize(loss_for_platform, x0, args=(dfs,), method="Nelder-Mead",
                   options={"xatol":1e-5,"fatol":1e-9,"maxiter":600})
    print(f"  V2 loss: {res.fun:.8f}, params={res.x}")
    g,L,K,tau,d0 = res.x
    out[plat] = {"g":float(g),"L_eff":float(L),"K_us":float(K),"tau":float(tau),"delta0_fallback":float(d0)}

with open(ROOT / "out/v2_params.json", "w") as f:
    json.dump(out, f, indent=2)
print("\nSaved", ROOT / "out/v2_params.json")
print(json.dumps(out, indent=2))
