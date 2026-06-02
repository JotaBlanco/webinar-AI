"""Try yr_ss + c * d(delta)/dt * v feedforward term."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import json

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05")

V1 = {
    "FORD_F_150_LIGHTNING_MK1": [0.863, 3.26, 0.00350, 0.060],
    "FORD_MUSTANG_MACH_E_MK1":  [0.891, 2.22, 0.00150, 0.069],
    "HYUNDAI_IONIQ_5":          [0.938, 2.887, 0.00289, 0.062],
}

def load(plat, max_segs=80):
    seg_root = ROOT / "data" / "sim" / "segments" / plat
    paths = sorted(seg_root.glob("**/sim.csv"))
    paths = paths[::max(1,len(paths)//max_segs)][:max_segs]
    segs = []
    for sp in paths:
        df = pd.read_csv(sp, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        if len(df) < 500: continue
        v = df["v_mps"].to_numpy(); yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
        d0 = float(np.median(d[mask])) if mask.sum() >= 50 else 0.0
        t = df["t_s"].to_numpy()
        d_dot = np.gradient(d, t)
        segs.append({
            "t": t, "d": d, "v": v,
            "yr": df["yaw_rate_meas_rads"].to_numpy(),
            "d0": d0, "d_dot": d_dot,
        })
    return segs


def sim_jerk(s, g, L, Kus, tau, c_dot):
    delta = (s["d"] - s["d0"]) * g
    v = s["v"]
    yr_ss = v * delta / (L + Kus * v * v) + c_dot * s["d_dot"] * v
    t = s["t"]; dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


for plat in ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]:
    segs = load(plat)
    g0, L0, Kus0, tau0 = V1[plat]
    # Just fit c_dot keeping others fixed.
    def loss(c):
        ss=0;n=0
        for s in segs:
            yr = sim_jerk(s, g0, L0, Kus0, tau0, c[0])
            mask = s["v"] > 2.0
            r = yr[mask]-s["yr"][mask]
            ss += float(np.sum(r*r)); n += int(mask.sum())
        return ss/max(n,1)
    base = loss([0.0])
    r = minimize(loss, [0.0], method="Nelder-Mead", options={"xatol":1e-7,"fatol":1e-12})
    print(f"{plat}: c_dot={r.x[0]:.6f}  loss {base:.4e} -> {r.fun:.4e}  ({100*(base-r.fun)/base:+.2f}%)")
