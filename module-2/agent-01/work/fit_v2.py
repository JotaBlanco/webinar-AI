"""V2: understeer + steering offset + first-order lag on yaw rate.

  y_ss[k] = v[k] * (delta[k] - delta0) / (L + K_us * v[k]^2)
  y[k+1]  = y[k] + (dt/tau) * (y_ss[k] - y[k])

Fit (K_us, delta0, tau) per platform on train split by minimising pooled SSE.
Use scipy.optimize. Then evaluate on dev split.
"""
import os, glob, json, sys
import numpy as np, pandas as pd
from scipy.optimize import minimize

ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
os.chdir(ROOT)

L_BY_PLAT = {
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
}


def load_seg(p):
    df = pd.read_csv(p)
    t = df['t_s'].to_numpy()
    v = df['v_mps'].to_numpy()
    d = df['delta_road_rad'].to_numpy()
    y = df['yaw_rate_meas_rads'].to_numpy()
    return t,v,d,y


def predict_v2(t, v, d, L, K_us, delta0, tau, y0=None):
    n = len(t)
    y_ss = v * (d - delta0) / (L + K_us * v * v)
    y = np.empty(n)
    y[0] = y_ss[0] if y0 is None else y0
    if tau <= 0:
        return y_ss
    for k in range(n-1):
        dt = t[k+1] - t[k]
        alpha = dt / (tau + dt)  # implicit-Euler-ish blend for stability with large dt/tau
        y[k+1] = y[k] + alpha * (y_ss[k+1] - y[k])
    return y


def sse_for_seg(t,v,d,y, params, L):
    K_us, delta0, tau = params
    y_pred = predict_v2(t, v, d, L, K_us, delta0, tau, y0=y[0])
    m = v > 3.0
    r = y_pred[m] - y[m]
    return float(np.sum(r*r)), int(m.sum())


def fit(plat, L, train_paths):
    segs = []
    for p in train_paths:
        try:
            t,v,d,y = load_seg(p)
            if (v > 3).sum() < 50: continue
            segs.append((t,v,d,y))
        except Exception:
            continue
    print(f'{plat} loaded {len(segs)} train segments')
    def obj(params):
        K_us, delta0, tau = params
        if tau < 0: return 1e9
        total_ss = 0.0; total_n = 0
        for t,v,d,y in segs:
            ss, n = sse_for_seg(t,v,d,y,(K_us,delta0,tau),L)
            total_ss += ss; total_n += n
        return total_ss / max(total_n, 1)
    # initial guess: from V1 fit
    x0 = [0.001, 0.0, 0.05]
    res = minimize(obj, x0, method='Nelder-Mead',
                   options={'xatol':1e-6,'fatol':1e-10,'maxiter':600})
    print(' result:', res.x, 'mse:', res.fun)
    return res.x


def split_paths(paths):
    paths = sorted(paths)
    train = [p for i,p in enumerate(paths) if i % 2 == 0]
    dev   = [p for i,p in enumerate(paths) if i % 2 == 1]
    return train, dev


def eval_on(plat, L, paths, params):
    K_us, delta0, tau = params
    sse_v0 = 0.0; sse_v2 = 0.0; n_tot = 0
    for p in paths:
        try:
            t,v,d,y = load_seg(p)
        except: continue
        m = v > 3.0
        if m.sum() < 20: continue
        y_v0 = (v/L)*np.tan(d)
        y_v2 = predict_v2(t,v,d,L,K_us,delta0,tau,y0=y[0])
        sse_v0 += float(np.sum((y_v0[m]-y[m])**2))
        sse_v2 += float(np.sum((y_v2[m]-y[m])**2))
        n_tot += int(m.sum())
    return np.sqrt(sse_v0/n_tot), np.sqrt(sse_v2/n_tot), n_tot


out = {}
for plat, L in L_BY_PLAT.items():
    paths = sorted(glob.glob(f'data/sim/segments/{plat}/**/sim.csv', recursive=True))
    train, dev = split_paths(paths)
    params = fit(plat, L, train)
    rmse_v0_tr, rmse_v2_tr, n_tr = eval_on(plat, L, train, params)
    rmse_v0_dv, rmse_v2_dv, n_dv = eval_on(plat, L, dev, params)
    print(f'  TRAIN: V0={rmse_v0_tr:.5f}  V2={rmse_v2_tr:.5f}  n={n_tr}')
    print(f'  DEV  : V0={rmse_v0_dv:.5f}  V2={rmse_v2_dv:.5f}  n={n_dv}')
    K_us, delta0, tau = params
    out[plat] = {'L': L, 'K_us': float(K_us), 'delta0': float(delta0), 'tau': float(tau)}

# Tesla fallback (no truth -> use Mach-E-ish defaults but with Tesla L)
out['TESLA_MODEL_3'] = {'L': 2.875, 'K_us': 0.0007, 'delta0': 0.0, 'tau': 0.08}

with open(os.path.join(ROOT, 'work/coeffs_v2.json'), 'w') as f:
    json.dump(out, f, indent=2)
print(json.dumps(out, indent=2))
