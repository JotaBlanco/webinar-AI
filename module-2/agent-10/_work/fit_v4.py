"""Fit a richer linear-in-features model:
psi_dot_pred = c1*feat + c2*feat*v + c3*feat*v^2 + c4*feat^3 + b0
where feat = v * delta_f / L  (just kinematic)
Grid-search tau.

Then evaluate on dev with full score (yaw+CTE).
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


def build_features(segs, L, tau):
    fs, vs, ys = [], [], []
    for t, v, d, yr in segs:
        d_f = lowpass(d, t, tau)
        feat = v * d_f / L
        m = v > 2.0
        fs.append(feat[m]); vs.append(v[m]); ys.append(yr[m])
    return np.concatenate(fs), np.concatenate(vs), np.concatenate(ys)


def fit_rich(segs, L):
    """Try several feature sets, pick best."""
    best = None
    for tau in [0.0, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15]:
        f, v, y = build_features(segs, L, tau)
        # Features: [f, f*v^2, f^3, 1]
        A = np.vstack([f, f * v * v, f**3, np.ones_like(f)]).T
        sol, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
        pred = A @ sol
        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        if best is None or rmse < best[0]:
            best = (rmse, tau, tuple(sol))
    return best


coeffs = {}
for plat, L in WB.items():
    print(f'\n== {plat} ==')
    train_segs = load_segments(train, plat)
    rmse, tau, sol = fit_rich(train_segs, L)
    c1, c2, c3, b0 = sol
    print(f'  rich: tau={tau:.3f} c1={c1:.5f} c2={c2:.5e} c3={c3:.5e} b0={b0:.5e}  train_rmse={rmse:.6f}')
    coeffs[plat] = dict(L=L, tau=tau, c1=float(c1), c2=float(c2), c3=float(c3), b0=float(b0))

with open(ROOT / '_work/coeffs_v4.json', 'w') as fh:
    json.dump(coeffs, fh, indent=2)


def make_predict(coeffs_dict):
    def predict(sim_df, platform):
        if platform not in coeffs_dict:
            yr = sim_df['yaw_rate_pred_rads'].values
            return pd.DataFrame({'yaw_rate_pred_rads': yr}, index=sim_df.index)
        c = coeffs_dict[platform]
        L, tau = c['L'], c['tau']
        c1, c2, c3, b0 = c['c1'], c['c2'], c['c3'], c['b0']
        t = sim_df['t_s'].values; v = sim_df['v_mps'].values; d = sim_df['delta_road_rad'].values
        d_f = lowpass(d, t, tau)
        feat = v * d_f / L
        pred = c1*feat + c2*feat*v*v + c3*feat**3 + b0
        return pd.DataFrame({'yaw_rate_pred_rads': pred}, index=sim_df.index)
    return predict


pf = make_predict(coeffs)


def predict_v0(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)


print('\n--- DEV ---')
print('V0 dev:', json.dumps(score(predict_v0, segment_paths=dev), indent=2, default=str))
print('V4 dev:', json.dumps(score(pf, segment_paths=dev), indent=2, default=str))
print('\n--- ALL ---')
print('V0 all:', json.dumps(score(predict_v0), indent=2, default=str))
print('V4 all:', json.dumps(score(pf), indent=2, default=str))
