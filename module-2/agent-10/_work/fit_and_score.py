"""Fit on train, score (yaw + CTE) on dev — honest evaluation."""
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

WB = {
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'FORD_F_150_LIGHTNING_MK1': 3.70,
}

train, dev = split(dev_fraction=0.25, seed=42)
print(f'train={len(train)} dev={len(dev)}')


def lowpass(delta, t, tau):
    if tau <= 1e-6:
        return delta.copy()
    out = np.empty_like(delta)
    out[0] = delta[0]
    dt = np.diff(t)
    a = dt / (tau + dt)
    for k in range(1, len(delta)):
        out[k] = (1 - a[k-1]) * out[k-1] + a[k-1] * delta[k]
    return out


def load_segments(paths, platform):
    segs = []
    for p in paths:
        if Path(p).resolve().parents[3].name != platform:
            continue
        df = pd.read_csv(p, usecols=['t_s', 'v_mps', 'delta_road_rad', 'yaw_rate_meas_rads'])
        segs.append((df['t_s'].values, df['v_mps'].values,
                     df['delta_road_rad'].values, df['yaw_rate_meas_rads'].values))
    return segs


def fit(segs, L):
    best = None
    for K in np.linspace(0.0, 0.012, 25):
        for tau in [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]:
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
            pred = s * f + b0
            rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
            if best is None or rmse < best[0]:
                best = (rmse, K, tau, s, b0)
    return best


coeffs = {}
for plat, L in WB.items():
    train_segs = load_segments(train, plat)
    rmse, K, tau, s, b0 = fit(train_segs, L)
    print(f'{plat}: K={K:.5f} tau={tau:.3f} s={s:.5f} b0={b0:.6e} train_rmse={rmse:.6f}')
    coeffs[plat] = dict(L=L, K=K, tau=tau, s=s, b0=b0)

# Save coeffs
(ROOT / '_work').mkdir(exist_ok=True)
with open(ROOT / '_work/coeffs.json', 'w') as fh:
    json.dump(coeffs, fh, indent=2)


# Now define predict and score on dev.
def make_predict(coeffs_dict):
    def predict(sim_df, platform):
        if platform not in coeffs_dict:
            # fallback: V0
            yr = sim_df['yaw_rate_pred_rads'].values
            return pd.DataFrame({'yaw_rate_pred_rads': yr}, index=sim_df.index)
        c = coeffs_dict[platform]
        L, K, tau, s, b0 = c['L'], c['K'], c['tau'], c['s'], c['b0']
        t = sim_df['t_s'].values
        v = sim_df['v_mps'].values
        d = sim_df['delta_road_rad'].values
        d_f = lowpass(d, t, tau)
        feat = v * d_f / (L + K * v * v)
        pred = s * feat + b0
        return pd.DataFrame({'yaw_rate_pred_rads': pred}, index=sim_df.index)
    return predict


predict_fn = make_predict(coeffs)


def predict_v0(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)


print('\n--- Dev set scores ---')
print('V0:'); print(json.dumps(score(predict_v0, segment_paths=dev), indent=2, default=str))
print('V1:'); print(json.dumps(score(predict_fn, segment_paths=dev), indent=2, default=str))
print('\n--- ALL segments ---')
print('V0:'); print(json.dumps(score(predict_v0), indent=2, default=str))
print('V1:'); print(json.dumps(score(predict_fn), indent=2, default=str))
