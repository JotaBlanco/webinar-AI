"""Fit understeer + first-order steering lag per platform.

Model:
   delta_filt[k] = (1-alpha) * delta_filt[k-1] + alpha * delta_meas[k]
       where alpha = dt / (tau + dt)  (one-pole low-pass)
   yr_pred = s * v * delta_filt / (L + K * v^2) + b0

We grid-search (K, tau) per platform; closed-form (s, b0) at each grid point.
We score per-sample yaw-rate RMSE on v>2 mask.

We score on segment-by-segment basis to correctly handle dt per segment.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')

WB = {
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
}

paths = sorted((ROOT / 'data/sim/segments').glob('FORD_*/**/sim.csv'))


def load_segments(platform):
    segs = []
    for p in paths:
        if p.resolve().parents[3].name != platform:
            continue
        df = pd.read_csv(p, usecols=['t_s', 'v_mps', 'delta_road_rad', 'yaw_rate_meas_rads'])
        segs.append((df['t_s'].values, df['v_mps'].values,
                     df['delta_road_rad'].values, df['yaw_rate_meas_rads'].values))
    return segs


def lowpass(delta, t, tau):
    if tau <= 1e-6:
        return delta.copy()
    out = np.empty_like(delta)
    out[0] = delta[0]
    dt = np.diff(t)
    for k in range(1, len(delta)):
        a = dt[k-1] / (tau + dt[k-1])
        out[k] = (1 - a) * out[k-1] + a * delta[k]
    return out


def evaluate(segs, L, K, tau):
    """Returns (s, b0, rmse_v2) via closed form regression across all v>2 samples."""
    feats = []
    targets = []
    for t, v, d, yr in segs:
        d_f = lowpass(d, t, tau)
        feat = v * d_f / (L + K * v * v)
        m = v > 2.0
        feats.append(feat[m])
        targets.append(yr[m])
    f = np.concatenate(feats)
    y = np.concatenate(targets)
    A = np.vstack([f, np.ones_like(f)]).T
    sol, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    s, b0 = sol
    pred = s * f + b0
    rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
    return s, b0, rmse


for plat, L in WB.items():
    print(f'\n=== {plat} ===')
    segs = load_segments(plat)
    print(f'  n_segments={len(segs)}')
    best = None
    for K in np.linspace(0.0, 0.012, 13):
        for tau in [0.0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.3]:
            s, b0, rmse = evaluate(segs, L, K, tau)
            if best is None or rmse < best[0]:
                best = (rmse, K, tau, s, b0)
    print(f'  best: K={best[1]:.5f} tau={best[2]:.3f} s={best[3]:.5f} b0={best[4]:.6e} rmse={best[0]:.6f}')
