"""Try adding a first-order lag on delta (steering response time tau).

Effective delta is a low-pass of delta_road with time constant tau.
yaw_rate = v * tan(delta_eff - doff) / (L * (1 + K * v^2))

Causes more code complexity in predict so we only adopt if RMSE drops materially.
"""
from __future__ import annotations
import math
import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-03")
os.chdir(ROOT)

L_BY_PLATFORM = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          3.0,
}

def collect_segments(platform):
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(base.glob("**/sim.csv"))
    segs = []
    for p in paths:
        df = pd.read_csv(p, usecols=["t_s","v_mps","delta_road_rad","yaw_rate_meas_rads"])
        segs.append((df["t_s"].to_numpy(), df["v_mps"].to_numpy(),
                     df["delta_road_rad"].to_numpy(), df["yaw_rate_meas_rads"].to_numpy()))
    return segs

def apply_lag(delta, t, tau):
    """First-order lag: y[k+1] = y[k] + dt/tau * (delta[k] - y[k])."""
    if tau <= 1e-6:
        return delta.copy()
    out = np.empty_like(delta)
    out[0] = delta[0]
    dt = np.diff(t)
    a = dt / (tau + dt)  # implicit
    for k in range(len(dt)):
        out[k+1] = out[k] + a[k] * (delta[k+1] - out[k])
    return out

def total_loss(params, segs, L):
    logK, doff, tau = params
    K = 10.0**logK
    tau = max(tau, 0.0)
    sse, n = 0.0, 0
    for t,v,d,y in segs:
        d_lag = apply_lag(d, t, tau)
        pred = (v * np.tan(d_lag - doff)) / (L * (1.0 + K*v*v))
        m = v > 2.0
        r = pred[m] - y[m]
        sse += float(np.sum(r*r))
        n += int(m.sum())
    return sse / n

def fit(platform):
    segs = collect_segments(platform)
    L = L_BY_PLATFORM[platform]
    res = minimize(total_loss, x0=[-3.0, 0.0, 0.05],
                   args=(segs, L), method="Nelder-Mead",
                   options={"xatol":1e-5, "fatol":1e-10, "maxiter":1500})
    logK, doff, tau = res.x
    rmse = math.sqrt(res.fun)
    return logK, doff, tau, rmse, len(segs)

if __name__ == "__main__":
    for plat in ["FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5", "FORD_MUSTANG_MACH_E_MK1"]:
        logK, doff, tau, rmse, n = fit(plat)
        print(f"{plat}: K={10**logK:.5f} doff={doff:+.5f} tau={tau:.4f}s -> rmse={rmse:.5f} (n_seg={n})")
