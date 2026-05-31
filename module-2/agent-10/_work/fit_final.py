"""Refit V1 (linear bicycle + steering scale + tau lag + bias) on ALL segments,
write coeffs.json for shipping in final-model/.
"""
import sys, os, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')
os.chdir(ROOT)

WB = {'FORD_MUSTANG_MACH_E_MK1': 2.984, 'FORD_F_150_LIGHTNING_MK1': 3.70}


def lowpass(delta, t, tau):
    if tau <= 1e-6: return delta.copy()
    out = np.empty_like(delta); out[0] = delta[0]
    dt = np.diff(t); a = dt / (tau + dt)
    for k in range(1, len(delta)):
        out[k] = (1 - a[k-1]) * out[k-1] + a[k-1] * delta[k]
    return out


paths = sorted((ROOT / 'data/sim/segments').glob('FORD_*/**/sim.csv'))


def load_segments(platform):
    segs = []
    for p in paths:
        if p.resolve().parents[3].name != platform: continue
        df = pd.read_csv(p, usecols=['t_s', 'v_mps', 'delta_road_rad', 'yaw_rate_meas_rads'])
        segs.append((df['t_s'].values, df['v_mps'].values,
                     df['delta_road_rad'].values, df['yaw_rate_meas_rads'].values))
    return segs


def fit(segs, L):
    best = None
    for K in np.linspace(0.0, 0.012, 49):
        for tau in [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15]:
            feats, targets = [], []
            for t, v, d, yr in segs:
                d_f = lowpass(d, t, tau)
                feat = v * d_f / (L + K * v * v)
                m = v > 2.0
                feats.append(feat[m]); targets.append(yr[m])
            f = np.concatenate(feats); y = np.concatenate(targets)
            A = np.vstack([f, np.ones_like(f)]).T
            sol, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
            s, b0 = sol
            pred = s*f + b0
            rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
            if best is None or rmse < best[0]:
                best = (rmse, K, tau, s, b0)
    return best


out = {}
for plat, L in WB.items():
    segs = load_segments(plat)
    rmse, K, tau, s, b0 = fit(segs, L)
    print(f'{plat}: K={K:.5f} tau={tau:.3f} s={s:.6f} b0={b0:.6e} rmse={rmse:.6f}')
    out[plat] = dict(L=L, K=float(K), tau=float(tau), s=float(s), b0=float(b0))

dest = ROOT / 'final-model/coeffs.json'
dest.parent.mkdir(exist_ok=True)
with open(dest, 'w') as fh:
    json.dump(out, fh, indent=2)
print('Wrote', dest)
