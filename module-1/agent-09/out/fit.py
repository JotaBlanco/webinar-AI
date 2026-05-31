"""Fit per-platform yaw model: steady-state + first-order lag + bias.

Model: yaw_pred(t) = LP[ v(t) * delta(t) / (L + K * v(t)^2) ; tau ] + bias

Fast version: sub-sample segments, use Nelder-Mead with one restart.
"""
import pandas as pd, numpy as np, glob, json, time, sys
from scipy.optimize import minimize

SIM_ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-09/data/sim/segments'

def lowpass_vec(x, tau, dt):
    if tau <= 1e-6:
        return x.copy()
    alpha = dt / (tau + dt)
    n = len(x)
    y = np.empty(n)
    y[0] = x[0]
    one_minus = 1.0 - alpha
    for i in range(1, n):
        y[i] = one_minus * y[i-1] + alpha * x[i]
    return y

def load_platform(platform, max_files=None, stride=1):
    files = sorted(glob.glob(f'{SIM_ROOT}/{platform}/*/*/*/sim.csv'))
    if max_files:
        files = files[:max_files]
    out = []
    for f in files:
        d = pd.read_csv(f, usecols=['t_s','v_mps','delta_road_rad',
                                     'yaw_rate_meas_rads','yaw_rate_pred_rads'])
        if stride > 1:
            d = d.iloc[::stride].reset_index(drop=True)
        t = d['t_s'].values
        if len(t) < 2: continue
        out.append({
            'v': d['v_mps'].values.astype(np.float64),
            'delta': d['delta_road_rad'].values.astype(np.float64),
            'truth': d['yaw_rate_meas_rads'].values.astype(np.float64),
            'pred_v0': d['yaw_rate_pred_rads'].values.astype(np.float64),
            't': t.astype(np.float64),
            'dt': float(np.median(np.diff(t))),
        })
    return out

def evaluate(params, segs):
    L, K, tau, bias = params
    if L <= 0.5 or K < -0.05 or tau < 0:
        return 1e9
    sse = 0.0; n = 0
    for s in segs:
        ss = s['v'] * s['delta'] / (L + K * s['v'] * s['v'])
        pred = lowpass_vec(ss, tau, s['dt']) + bias
        err = s['truth'] - pred
        sse += float(np.sum(err * err))
        n += len(err)
    return np.sqrt(sse / n) if n else float('inf')

def evaluate_v0(segs):
    sse = 0.0; n = 0
    for s in segs:
        err = s['truth'] - s['pred_v0']
        sse += float(np.sum(err*err)); n += len(err)
    return np.sqrt(sse / n) if n else float('inf')

def fit_platform(platform, max_files=80, stride=4):
    t0 = time.time()
    segs = load_platform(platform, max_files, stride)
    print(f'\n=== {platform}: {len(segs)} segments (stride={stride}) loaded in {time.time()-t0:.1f}s ===', flush=True)
    print(f'  V0 RMSE on train subset: {evaluate_v0(segs):.5f}', flush=True)

    t0 = time.time()
    # Two-start NM
    best = None
    for x0 in [[3.0, 0.005, 0.05, 0.0], [3.0, 0.01, 0.15, 0.0]]:
        res = minimize(evaluate, x0, args=(segs,),
                       method='Nelder-Mead',
                       options={'xatol':1e-5,'fatol':1e-7,'maxiter':400})
        if best is None or res.fun < best.fun:
            best = res
    L, K, tau, bias = best.x
    print(f'  fit done in {time.time()-t0:.1f}s', flush=True)
    print(f'  L={L:.4f}  K={K:.5f}  tau={tau:.4f}  bias={bias:.5f}', flush=True)
    print(f'  Fitted RMSE on train subset: {best.fun:.5f}', flush=True)
    return {'L': float(L), 'K': float(K), 'tau': float(tau), 'bias': float(bias),
            'rmse_train_subset': float(best.fun),
            'rmse_v0_train_subset': float(evaluate_v0(segs)),
            'n_train_segments': len(segs),
            'stride': stride}

if __name__ == '__main__':
    out = {}
    for p in ['HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1']:
        out[p] = fit_platform(p, max_files=80, stride=4)
    out['TESLA_MODEL_3'] = {
        'L': 2.875, 'K': 0.0, 'tau': 0.0, 'bias': 0.0,
        'use_v0': True,
        'note': 'No yaw_rate_meas channel in Tesla sim CSV — falls back to V0 KS (yaw_rate_pred_rads from sim_df).'
    }
    out_path = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-09/out/coeffs.json'
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2)
    # Also copy into final-model/ so predict.py can find it
    final_path = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-09/final-model/coeffs.json'
    with open(final_path, 'w') as f:
        json.dump(out, f, indent=2)
    print(f'\nWrote {out_path} and {final_path}', flush=True)
    print(json.dumps(out, indent=2), flush=True)
