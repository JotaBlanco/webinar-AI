"""2nd-order lag fit with per-segment δ0 baked in (oracle, for upper-bound check)."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import json

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05")

def load(plat, max_segs=80):
    seg_root = ROOT / "data" / "sim" / "segments" / plat
    paths = sorted(seg_root.glob("**/sim.csv"))
    paths = paths[::max(1,len(paths)//max_segs)][:max_segs]
    segs = []
    for sp in paths:
        df = pd.read_csv(sp, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        if len(df) < 500: continue
        # Per-segment δ0 estimator (V1 style)
        v = df["v_mps"].to_numpy(); yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
        d0 = float(np.median(d[mask])) if mask.sum() >= 50 else 0.0
        segs.append({
            "t": df["t_s"].to_numpy(),
            "d": df["delta_road_rad"].to_numpy(),
            "v": df["v_mps"].to_numpy(),
            "yr": df["yaw_rate_meas_rads"].to_numpy(),
            "d0": d0,
        })
    return segs


def sim_1st(s, g, L, Kus, tau):
    delta = (s["d"] - s["d0"]) * g
    v = s["v"]
    yr_ss = v * delta / (L + Kus * v * v)
    t = s["t"]; dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def sim_2nd(s, g, L, Kus, w0, zeta):
    delta = (s["d"] - s["d0"]) * g
    v = s["v"]
    yr_ss = v * delta / (L + Kus * v * v)
    t = s["t"]; n = len(t)
    yr = np.empty(n); yrd = np.empty(n)
    yr[0] = yr_ss[0]; yrd[0] = 0.0
    for i in range(1, n):
        dt = t[i]-t[i-1]
        yrd[i] = yrd[i-1] + dt * (w0*w0*(yr_ss[i-1]-yr[i-1]) - 2*zeta*w0*yrd[i-1])
        yr[i] = yr[i-1] + dt * yrd[i-1]
    return yr


def fit(segs, sim_fn, x0, bounds_chk):
    def loss(th):
        if not bounds_chk(th): return 1e9
        ss = 0.0; n = 0
        for s in segs:
            yr = sim_fn(s, *th)
            mask = s["v"] > 2.0
            r = yr[mask] - s["yr"][mask]
            ss += float(np.sum(r*r)); n += int(mask.sum())
        return ss / max(n,1)
    r = minimize(loss, x0, method="Nelder-Mead", options={"xatol":1e-6,"fatol":1e-11,"maxiter":800})
    return r.x, r.fun


INIT_1 = {
    "FORD_F_150_LIGHTNING_MK1": [0.865, 3.27, 0.00339, 0.0585],
    "FORD_MUSTANG_MACH_E_MK1":  [0.831, 2.089, 0.00177, 0.0645],
    "HYUNDAI_IONIQ_5":          [0.958, 2.959, 0.00284, 0.0537],
}

results = {}
for plat in ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]:
    segs = load(plat)
    print(f"\n=== {plat}  n={len(segs)} ===")
    x1, l1 = fit(segs, sim_1st, INIT_1[plat],
                 lambda th: th[1] > 1.0 and th[3] > 0.005 and th[2] > -0.01 and 0.3 < th[0] < 1.5)
    print(f"  1st: g={x1[0]:.4f} L={x1[1]:.4f} Kus={x1[2]:.5f} tau={x1[3]:.4f}  loss={l1:.4e}")

    init2 = [x1[0], x1[1], x1[2], 1.0/max(x1[3],0.05), 1.0]
    x2, l2 = fit(segs, sim_2nd, init2,
                 lambda th: th[1] > 1.0 and 1 < th[3] < 200 and 0.05 < th[4] < 5 and 0.3 < th[0] < 1.5)
    print(f"  2nd: g={x2[0]:.4f} L={x2[1]:.4f} Kus={x2[2]:.5f} w0={x2[3]:.3f} zeta={x2[4]:.3f}  loss={l2:.4e}  diff={100*(l1-l2)/l1:+.2f}%")

    results[plat] = {
        "first_order": {"g":float(x1[0]),"L_eff":float(x1[1]),"K_us":float(x1[2]),"tau":float(x1[3]),"loss":float(l1)},
        "second_order": {"g":float(x2[0]),"L_eff":float(x2[1]),"K_us":float(x2[2]),"w0":float(x2[3]),"zeta":float(x2[4]),"loss":float(l2)},
    }

(ROOT / "out" / "fit_with_d0.json").write_text(json.dumps(results, indent=2))
print()
print(json.dumps(results, indent=2))
