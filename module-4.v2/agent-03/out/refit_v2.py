"""Refit V1 per-platform with TIGHT bounds and a CTE-aware loss.

Penalises signed CTE drift (the thing that murders CTE-RMSE on Mach-E and Hyundai).
Uses Nelder-Mead with penalty for parameters straying too far from V1.
"""
from __future__ import annotations
import sys, glob, json, time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa

V1 = {
    "FORD_F_150_LIGHTNING_MK1": dict(use_seg=False, delta0=0.00133, g=0.863, L=3.26, K_us=0.00350, tau=0.060),
    "FORD_MUSTANG_MACH_E_MK1": dict(use_seg=True, fallback=-0.0001, g=0.891, L=2.22, K_us=0.00150, tau=0.069),
    "HYUNDAI_IONIQ_5":         dict(use_seg=True, fallback=0.0,    g=0.938, L=2.887, K_us=0.00289, tau=0.062),
}

def load_segs(plat, limit=300):
    paths = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))[:limit]
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

def predict_yr(dt, v, dr, delta0, g, L, K, tau):
    delta = (dr - delta0) * g
    yr_ss = v * delta / (L + K * v * v)
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr

def loss(segs, use_seg, g, L, K, tau, d0_or_fb, v_thresh=2.0, cte_weight=0.0001):
    """Yaw RMSE^2 + cte_weight * mean(signed_cte_drift^2)."""
    sum_sq = 0.0; n = 0
    cte_sq_sum = 0.0; cte_n = 0
    for (t, dt, v, dr, ym, yv0) in segs:
        if use_seg:
            d0 = per_seg_delta0(dr, v, yv0, fallback=d0_or_fb)
        else:
            d0 = d0_or_fb
        yr = predict_yr(dt, v, dr, d0, g, L, K, tau)
        mask = v > v_thresh
        r = (yr - ym)[mask]
        sum_sq += float((r*r).sum()); n += int(mask.sum())
        # CTE diagnostic
        diag = cte_diagnostics_segment(t, v, ym, yr)
        if diag["n_bins"] > 0:
            mean_signed = diag["sum_signed_m"] / diag["n_bins"]
            cte_sq_sum += mean_signed * mean_signed
            cte_n += 1
    yaw_rmse2 = sum_sq / n
    cte_drift_ms = cte_sq_sum / cte_n if cte_n else 0.0
    return yaw_rmse2 + cte_weight * cte_drift_ms, np.sqrt(yaw_rmse2), np.sqrt(cte_drift_ms)

def refit(plat, limit=300, cte_weight=1e-5):
    base = V1[plat]
    print(f"\n=== {plat} (limit={limit}, cte_weight={cte_weight}) ===", flush=True)
    t0 = time.time()
    segs = load_segs(plat, limit=limit)
    print(f"  loaded {len(segs)} segs in {time.time()-t0:.1f}s", flush=True)
    use_seg = base['use_seg']
    g0, L0, K0, tau0 = base['g'], base['L'], base['K_us'], base['tau']
    d0_init = base.get('delta0', base.get('fallback', 0.0))
    # Tight box bounds: stay within ±30% of V1 init for L, K_us; ±20% for g; ±50% for tau
    bounds_lo = [g0*0.85, L0*0.85, K0*0.5, max(0.01, tau0*0.5), d0_init - 0.005]
    bounds_hi = [g0*1.15, L0*1.15, K0*2.0, tau0*2.0, d0_init + 0.005]
    def cost(x):
        for i in range(5):
            if x[i] < bounds_lo[i] or x[i] > bounds_hi[i]:
                return 1e6
        g, L, K, tau, d0 = x
        l, _, _ = loss(segs, use_seg, g, L, K, tau, d0, cte_weight=cte_weight)
        return l
    x0 = [g0, L0, K0, tau0, d0_init]
    c0 = cost(x0)
    print(f"  init cost: {c0:.8f}", flush=True)
    res = minimize(cost, x0, method='Nelder-Mead',
                   options={'xatol':1e-5,'fatol':1e-9,'maxiter':300, 'disp':False})
    final = res.x
    final_loss, yrmse, cte_drift = loss(segs, use_seg, *final, cte_weight=cte_weight)
    print(f"  fit cost:  {res.fun:.8f} in {time.time()-t0:.1f}s ({res.nit} iters)", flush=True)
    print(f"  yaw RMSE:  {yrmse:.6f}  signed-CTE-drift RMS: {cte_drift:.4f}", flush=True)
    print(f"  g={final[0]:.5f} L={final[1]:.4f} K_us={final[2]:.6f} tau={final[3]:.5f} d0/fb={final[4]:.6f}", flush=True)
    return dict(
        use_per_segment_delta0=use_seg,
        g=float(final[0]),
        L_eff=float(final[1]),
        K_us=float(final[2]),
        tau=float(final[3]),
        delta0=(float(final[4]) if not use_seg else None),
        delta0_fallback=(float(final[4]) if use_seg else None),
        v0_yaw_rmse=float(c0),
        fit_yaw_rmse=float(yrmse),
    )

if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        out[plat] = refit(plat, limit=300, cte_weight=1e-5)
    with open(ROOT / "out" / "v2_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nWrote", ROOT / "out" / "v2_coeffs.json")
