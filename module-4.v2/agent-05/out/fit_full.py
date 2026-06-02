"""Full per-platform refit: (g, L_eff, K_us, tau, delta0_const) jointly minimised against pooled yaw residual.

Uses the V1 functional form but optimises 5 params per platform.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import json

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05")
PLATS = ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]


def load(plat, max_segs=80):
    seg_root = ROOT / "data" / "sim" / "segments" / plat
    paths = sorted(seg_root.glob("**/sim.csv"))
    paths = paths[::max(1,len(paths)//max_segs)][:max_segs]
    segs = []
    for sp in paths:
        df = pd.read_csv(sp, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads"])
        if len(df) < 500: continue
        segs.append({
            "t": df["t_s"].to_numpy(dtype=float),
            "d": df["delta_road_rad"].to_numpy(dtype=float),
            "v": df["v_mps"].to_numpy(dtype=float),
            "yr": df["yaw_rate_meas_rads"].to_numpy(dtype=float),
        })
    return segs


def sim(s, g, L, Kus, tau, d0):
    delta = (s["d"] - d0) * g
    v = s["v"]
    yr_ss = v * delta / (L + Kus * v * v)
    t = s["t"]
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def sim_2nd_order(s, g, L, Kus, w0, zeta, d0):
    """Damped 2nd-order: x'' + 2 ζ ω0 x' + ω0² x = ω0² yr_ss
    Discrete: yr[i] = yr[i-1] + dt * yr_dot[i-1]; yr_dot[i] = yr_dot[i-1] + dt*(ω0² (yr_ss-yr) - 2ζω0 yr_dot)
    """
    delta = (s["d"] - d0) * g
    v = s["v"]
    yr_ss = v * delta / (L + Kus * v * v)
    t = s["t"]; n = len(t)
    yr = np.empty(n); yrd = np.empty(n)
    yr[0] = yr_ss[0]; yrd[0] = 0.0
    for i in range(1, n):
        dt = t[i]-t[i-1]
        yr[i] = yr[i-1] + dt * yrd[i-1]
        yrd[i] = yrd[i-1] + dt * (w0*w0*(yr_ss[i-1]-yr[i-1]) - 2*zeta*w0*yrd[i-1])
    return yr


def fit_first_order(segs, x0):
    def loss(th):
        g, L, Kus, tau, d0 = th
        if L < 1.0 or tau < 0.005 or Kus < -0.005 or g < 0.3 or g > 1.5: return 1e9
        ss = 0.0; n = 0
        for s in segs:
            yr = sim(s, g, L, Kus, tau, d0)
            mask = s["v"] > 2.0
            r = yr[mask] - s["yr"][mask]
            ss += float(np.sum(r*r)); n += int(mask.sum())
        return ss / max(n,1)
    r = minimize(loss, x0, method="Nelder-Mead",
                 options={"xatol":1e-6,"fatol":1e-11,"maxiter":600})
    return r.x, r.fun


def fit_second_order(segs, x0):
    def loss(th):
        g, L, Kus, w0, zeta, d0 = th
        if L < 1.0 or w0 < 1.0 or w0 > 100 or zeta < 0.1 or zeta > 3 or Kus < -0.005 or g < 0.3 or g > 1.5: return 1e9
        ss = 0.0; n = 0
        for s in segs:
            yr = sim_2nd_order(s, g, L, Kus, w0, zeta, d0)
            mask = s["v"] > 2.0
            r = yr[mask] - s["yr"][mask]
            ss += float(np.sum(r*r)); n += int(mask.sum())
        return ss / max(n,1)
    r = minimize(loss, x0, method="Nelder-Mead",
                 options={"xatol":1e-6,"fatol":1e-11,"maxiter":800})
    return r.x, r.fun


INIT_1 = {
    "FORD_F_150_LIGHTNING_MK1": [0.865, 3.27, 0.00339, 0.0585, 0.00144],
    "FORD_MUSTANG_MACH_E_MK1":  [0.831, 2.089, 0.00177, 0.0645, -0.00006],
    "HYUNDAI_IONIQ_5":          [0.958, 2.959, 0.00284, 0.0537, -0.00049],
}

results = {}
for plat in PLATS:
    print(f"\n=== {plat} ===")
    segs = load(plat)
    print(f"  loaded {len(segs)} segments")

    x1, l1 = fit_first_order(segs, INIT_1[plat])
    print(f"  1st-order: g={x1[0]:.4f} L={x1[1]:.4f} Kus={x1[2]:.5f} tau={x1[3]:.4f} d0={x1[4]:+.5f}  loss={l1:.4e}")

    # 2nd-order init: w0 = 1/tau, zeta=1 (critical)
    init2 = [x1[0], x1[1], x1[2], 1.0/max(x1[3],0.05), 1.0, x1[4]]
    x2, l2 = fit_second_order(segs, init2)
    print(f"  2nd-order: g={x2[0]:.4f} L={x2[1]:.4f} Kus={x2[2]:.5f} w0={x2[3]:.3f} zeta={x2[4]:.3f} d0={x2[4]:+.5f}  loss={l2:.4e}")

    results[plat] = {
        "first_order": {"g":x1[0],"L_eff":x1[1],"K_us":x1[2],"tau":x1[3],"delta0":x1[4],"loss":l1},
        "second_order": {"g":x2[0],"L_eff":x2[1],"K_us":x2[2],"w0":x2[3],"zeta":x2[4],"delta0":x2[5],"loss":l2},
    }

(ROOT / "out" / "fit_full.json").write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
