"""Refit V1 per-platform parameters on a sample of segments.

Strategy: load each segment's columns once as np arrays, then optimise
g, L_eff, K_us, tau, delta0/fallback per platform via Nelder-Mead.
Uses ~200 segments per platform for speed.
"""
from __future__ import annotations
import sys, glob, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]

# Use existing V1 starting point
V1 = {
    "FORD_F_150_LIGHTNING_MK1": dict(use_seg=False, delta0=0.00133, g=0.863, L=3.26, K_us=0.00350, tau=0.060),
    "FORD_MUSTANG_MACH_E_MK1": dict(use_seg=True, fallback=-0.0001, g=0.891, L=2.22, K_us=0.00150, tau=0.069),
    "HYUNDAI_IONIQ_5":         dict(use_seg=True, fallback=0.0,    g=0.938, L=2.887, K_us=0.00289, tau=0.062),
}

def load_segs(plat, limit=200):
    paths = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))
    if limit: paths = paths[:limit]
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        except Exception:
            continue
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        dr = df["delta_road_rad"].to_numpy()
        ym = df["yaw_rate_meas_rads"].to_numpy()
        yv0 = df["yaw_rate_pred_rads"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        segs.append((t, dt, v, dr, ym, yv0))
    return segs

def per_seg_delta0(dr, v, yv0, fallback, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    mask = (np.abs(yv0) < yr_thresh) & (v > v_thresh)
    if mask.sum() < min_rows:
        return fallback
    return float(np.median(dr[mask]))

def predict_yr(t, dt, v, dr, delta0, g, L, K, tau):
    delta = (dr - delta0) * g
    yr_ss = v * delta / (L + K * v * v)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr

def score_yaw_rmse(segs, use_seg, g, L, K, tau, d0_or_fb, v_thresh=2.0):
    sum_sq = 0.0; n = 0
    for (t, dt, v, dr, ym, yv0) in segs:
        if use_seg:
            d0 = per_seg_delta0(dr, v, yv0, fallback=d0_or_fb)
        else:
            d0 = d0_or_fb
        yr = predict_yr(t, dt, v, dr, d0, g, L, K, tau)
        mask = v > v_thresh
        r = (yr - ym)[mask]
        sum_sq += float((r*r).sum()); n += int(mask.sum())
    return np.sqrt(sum_sq/n) if n else float('nan')

def refit(plat, limit=200):
    base = V1[plat]
    print(f"\n=== {plat} (limit={limit}) ===", flush=True)
    t0 = time.time()
    segs = load_segs(plat, limit=limit)
    print(f"  loaded {len(segs)} segs in {time.time()-t0:.1f}s", flush=True)
    use_seg = base['use_seg']
    g0, L0, K0, tau0 = base['g'], base['L'], base['K_us'], base['tau']
    d0_init = base.get('delta0', base.get('fallback', 0.0))
    def cost(x):
        g, L, K, tau, d0 = x
        if K < 0 or L < 1 or tau < 1e-3 or tau > 0.5 or g < 0.5 or g > 1.5:
            return 1e6
        return score_yaw_rmse(segs, use_seg, g, L, K, tau, d0)
    x0 = [g0, L0, K0, tau0, d0_init]
    c0 = cost(x0)
    print(f"  init cost: {c0:.6f}", flush=True)
    res = minimize(cost, x0, method='Nelder-Mead',
                   options={'xatol':1e-5,'fatol':1e-7,'maxiter':400, 'disp':False})
    print(f"  fit cost:  {res.fun:.6f} in {time.time()-t0:.1f}s ({res.nit} iters)", flush=True)
    print(f"  g={res.x[0]:.5f} L={res.x[1]:.4f} K_us={res.x[2]:.6f} tau={res.x[3]:.5f} d0/fb={res.x[4]:.6f}", flush=True)
    return dict(
        use_seg=use_seg,
        g=float(res.x[0]),
        L_eff=float(res.x[1]),
        K_us=float(res.x[2]),
        tau=float(res.x[3]),
        delta0=float(res.x[4]) if not use_seg else None,
        delta0_fallback=float(res.x[4]) if use_seg else None,
        init_yaw_rmse=float(c0),
        fit_yaw_rmse=float(res.fun),
    )

if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        out[plat] = refit(plat, limit=200)
    with open(ROOT / "out" / "v2_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote", ROOT / "out" / "v2_coeffs.json")
