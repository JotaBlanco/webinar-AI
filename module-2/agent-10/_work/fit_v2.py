"""Try adding (a) tire saturation: psi_dot = s*feat + s3*feat^3 + b0
(b) speed-dependent steering scale: s + s1*v
"""
import sys, os, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'skills' / 'make-train-dev-split'))
sys.path.insert(0, str(ROOT / 'skills' / 'score-model'))
sys.path.insert(0, str(ROOT / '_shared'))
from split import split
from score import score

WB = {'FORD_MUSTANG_MACH_E_MK1': 2.984, 'FORD_F_150_LIGHTNING_MK1': 3.70}
train, dev = split(dev_fraction=0.25, seed=42)


def lowpass(delta, t, tau):
    if tau <= 1e-6: return delta.copy()
    out = np.empty_like(delta); out[0] = delta[0]
    dt = np.diff(t); a = dt / (tau + dt)
    for k in range(1, len(delta)):
        out[k] = (1 - a[k-1]) * out[k-1] + a[k-1] * delta[k]
    return out


def load_segments(paths, platform):
    segs = []
    for p in paths:
        if Path(p).resolve().parents[3].name != platform: continue
        df = pd.read_csv(p, usecols=['t_s', 'v_mps', 'delta_road_rad', 'yaw_rate_meas_rads'])
        segs.append((df['t_s'].values, df['v_mps'].values,
                     df['delta_road_rad'].values, df['yaw_rate_meas_rads'].values))
    return segs


def fit_v2(segs, L):
    """psi = s1*feat + s3*feat^3 + b0 (4 params)"""
    best = None
    for K in np.linspace(0.0, 0.012, 13):
        for tau in [0.0, 0.04, 0.06, 0.08, 0.10, 0.15]:
            feats, targets = [], []
            for t, v, d, yr in segs:
                d_f = lowpass(d, t, tau)
                feat = v * d_f / (L + K * v * v)
                m = v > 2.0
                feats.append(feat[m]); targets.append(yr[m])
            f = np.concatenate(feats); y = np.concatenate(targets)
            A = np.vstack([f, f**3, np.ones_like(f)]).T
            sol, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
            s1, s3, b0 = sol
            pred = s1*f + s3*f**3 + b0
            rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
            if best is None or rmse < best[0]:
                best = (rmse, K, tau, s1, s3, b0)
    return best


def fit_v3(segs, L):
    """psi = (s + sv*v) * feat + b0 — speed-dependent scale"""
    best = None
    for K in np.linspace(0.0, 0.012, 13):
        for tau in [0.0, 0.04, 0.06, 0.08, 0.10, 0.15]:
            feats, feats_v, targets = [], [], []
            for t, v, d, yr in segs:
                d_f = lowpass(d, t, tau)
                feat = v * d_f / (L + K * v * v)
                m = v > 2.0
                feats.append(feat[m]); feats_v.append((feat * v)[m]); targets.append(yr[m])
            f = np.concatenate(feats); fv = np.concatenate(feats_v); y = np.concatenate(targets)
            A = np.vstack([f, fv, np.ones_like(f)]).T
            sol, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
            s, sv, b0 = sol
            pred = s*f + sv*fv + b0
            rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
            if best is None or rmse < best[0]:
                best = (rmse, K, tau, s, sv, b0)
    return best


for plat, L in WB.items():
    train_segs = load_segments(train, plat)
    print(f'\n== {plat} ==')
    r2 = fit_v2(train_segs, L); print(f'  V2 cubic:  rmse={r2[0]:.6f} K={r2[1]} tau={r2[2]} s1={r2[3]:.4f} s3={r2[4]:.4e} b0={r2[5]:.4e}')
    r3 = fit_v3(train_segs, L); print(f'  V3 svspd:  rmse={r3[0]:.6f} K={r3[1]} tau={r3[2]} s={r3[3]:.4f} sv={r3[4]:.4e} b0={r3[5]:.4e}')
