"""Refit V1 with extended understeer: yr_ss = v*delta / (L + K_us*v^2 + K_us2*v^2*|delta|).
Plus a 2nd-order lag (two cascaded first-order with two taus).
"""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "code"))

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def predict_v2(sim, p, delta0):
    delta = (sim["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim["v_mps"].to_numpy()
    K = p["K_us"] + p.get("K_us2", 0.0) * np.abs(delta)
    yr_ss = v * delta / (p["L_eff"] + K * v * v)
    t = sim["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def cost(theta, segs, use_per):
    g, L, K, K2, tau = theta[:5]
    d0g = theta[5] if not use_per else None
    if L <= 0.5 or tau <= 0 or K < 0 or g <= 0:
        return 1e9
    p = {"g": g, "L_eff": L, "K_us": K, "K_us2": K2, "tau": tau}
    tot_sq = 0.0
    tot_n = 0
    for c in segs:
        d0 = c["delta0"] if use_per else d0g
        yr = predict_v2(c["df"], p, d0)
        r = yr[c["mv"]] - c["truth"][c["mv"]]
        tot_sq += float(np.sum(r**2))
        tot_n += int(c["mv"].sum())
    return tot_sq / max(tot_n, 1)


def _per_seg_d0(sim):
    v = sim["v_mps"].to_numpy()
    yr_v0 = sim["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    return float(sim.loc[mask, "delta_road_rad"].median()) if mask.sum() >= 50 else 0.0


def fit_platform(plat, use_per, init):
    paths = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
    cached = []
    for path in paths:
        sim = pd.read_csv(path)
        cached.append({
            "df": sim,
            "truth": sim["yaw_rate_meas_rads"].to_numpy(),
            "mv": sim["v_mps"].to_numpy() > 2,
            "delta0": _per_seg_d0(sim),
        })
    print(f"  {plat}: fitting on {len(cached)} segments")

    def obj(theta): return cost(theta, cached, use_per)

    x0 = np.array(init)
    res = minimize(obj, x0, method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-11, "maxiter": 1200})
    print(f"  {plat}: {obj(x0):.3e} -> {res.fun:.3e}")
    return res.x


# init: g, L, K_us, K_us2, tau, [delta0 if not per-seg]
platforms = {
    "FORD_F_150_LIGHTNING_MK1": (False, [0.868, 3.28, 0.00348, 0.0, 0.059, 0.00127]),
    "FORD_MUSTANG_MACH_E_MK1": (True, [0.905, 2.25, 0.00200, 0.0, 0.069]),
    "HYUNDAI_IONIQ_5": (True, [0.947, 2.94, 0.00281, 0.0, 0.051]),
}

import json
results = {}
for plat, (use_per, init) in platforms.items():
    theta = fit_platform(plat, use_per, init)
    if use_per:
        g, L, K, K2, tau = theta
        results[plat] = {"use_per_segment_delta0": True, "delta0_fallback": 0.0,
                         "g": float(g), "L_eff": float(L), "K_us": float(K),
                         "K_us2": float(K2), "tau": float(tau)}
    else:
        g, L, K, K2, tau, d0 = theta
        results[plat] = {"use_per_segment_delta0": False, "delta0": float(d0),
                         "g": float(g), "L_eff": float(L), "K_us": float(K),
                         "K_us2": float(K2), "tau": float(tau)}
    print(f"  {plat}: {results[plat]}")

(ROOT / "out" / "fitted_v2.json").write_text(json.dumps(results, indent=2))
print("Wrote fitted_v2.json")
