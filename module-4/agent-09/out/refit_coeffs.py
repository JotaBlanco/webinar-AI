"""Refit V1 coeffs (g, L_eff, K_us, tau, delta0) per platform on a sample
of segments. Use scipy.optimize.minimize and pooled sum of squares.
"""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "code"))

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from v1_baseline import PLATFORM_PARAMS_V1


def predict_for_seg(sim, p, delta0):
    delta = (sim["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def cost_for_platform(theta, segs, use_per_segment_delta0):
    g, L_eff, K_us, tau = theta[0], theta[1], theta[2], theta[3]
    delta0_global = theta[4] if not use_per_segment_delta0 else None
    p = {"g": g, "L_eff": L_eff, "K_us": K_us, "tau": tau}
    if L_eff <= 0.5 or tau <= 0.0 or K_us < 0.0 or g <= 0:
        return 1e9
    tot_sq = 0.0
    tot_n = 0
    for sim in segs:
        if use_per_segment_delta0:
            v = sim["v_mps"].to_numpy()
            yr_v0 = sim["yaw_rate_pred_rads"].to_numpy()
            mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
            d0 = float(sim.loc[mask, "delta_road_rad"].median()) if mask.sum() >= 50 else 0.0
        else:
            d0 = delta0_global
        yr = predict_for_seg(sim, p, d0)
        truth = sim["yaw_rate_meas_rads"].to_numpy()
        v = sim["v_mps"].to_numpy()
        mv = v > 2
        r = yr[mv] - truth[mv]
        tot_sq += float(np.sum(r**2))
        tot_n += int(mv.sum())
    return tot_sq / max(tot_n, 1)


def fit_platform(plat, use_per_segment_delta0, init):
    plat_root = ROOT / "data" / "sim" / "segments" / plat
    segs_paths = sorted(plat_root.glob("**/sim.csv"))
    # Sample up to 60 segments for speed
    rng = np.random.RandomState(0)
    if len(segs_paths) > 60:
        idx = rng.choice(len(segs_paths), 60, replace=False)
        segs_paths = [segs_paths[i] for i in idx]
    segs = []
    for p in segs_paths:
        try:
            segs.append(pd.read_csv(p))
        except Exception:
            pass
    print(f"  {plat}: fitting on {len(segs)} segments")

    def obj(theta):
        return cost_for_platform(theta, segs, use_per_segment_delta0)

    x0 = np.array(init)
    res = minimize(obj, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 400, "disp": False})
    print(f"  {plat}: cost {obj(x0):.3e} -> {res.fun:.3e}")
    return res.x


platforms = {
    "FORD_F_150_LIGHTNING_MK1": (False, [0.863, 3.26, 0.00350, 0.060, 0.00133]),
    "FORD_MUSTANG_MACH_E_MK1": (True, [0.891, 2.22, 0.00150, 0.069]),
    "HYUNDAI_IONIQ_5": (True, [0.938, 2.887, 0.00289, 0.062]),
}

results = {}
for plat, (use_per, init) in platforms.items():
    theta = fit_platform(plat, use_per, init)
    if use_per:
        g, L, K, tau = theta
        results[plat] = {"use_per_segment_delta0": True, "delta0_fallback": 0.0,
                         "g": float(g), "L_eff": float(L), "K_us": float(K), "tau": float(tau)}
    else:
        g, L, K, tau, d0 = theta
        results[plat] = {"use_per_segment_delta0": False, "delta0": float(d0),
                         "g": float(g), "L_eff": float(L), "K_us": float(K), "tau": float(tau)}
    print(f"  {plat}: {results[plat]}")

import json
out = ROOT / "out" / "fitted_coeffs.json"
out.write_text(json.dumps(results, indent=2))
print(f"\nWrote {out}")
