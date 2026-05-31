"""V2 — try polynomial steering scale for Mach-E.
yr_ss = v * g(delta_eff) * delta_eff / (L + K_us * v^2)
where delta_eff = delta - delta0
and g(d) = g0 + g2 * d^2 (even-symmetric — no sign-dependent bias).
"""
import sys, math, json
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

sys.path.insert(0, 'skills/make-train-dev-split')
from split import split

train, dev = split(dev_fraction=0.25, seed=42)

def load_arr(p):
    df = pd.read_csv(p)[['t_s','v_mps','delta_road_rad','yaw_rate_meas_rads']].astype(float).dropna()
    return df

# pool train rows per platform
by_plat = {}
for p in train:
    plat = p.parts[-5]
    by_plat.setdefault(plat, []).append(p)

L_priors = {'FORD_MUSTANG_MACH_E_MK1': 2.984, 'FORD_F_150_LIGHTNING_MK1': 3.70}
params = {}

for plat, paths in by_plat.items():
    segs = [load_arr(p) for p in paths]
    vs, ds, yrs = [], [], []
    for df in segs:
        m = df['v_mps'] > 3.0
        vs.append(df.loc[m,'v_mps'].to_numpy())
        ds.append(df.loc[m,'delta_road_rad'].to_numpy())
        yrs.append(df.loc[m,'yaw_rate_meas_rads'].to_numpy())
    v = np.concatenate(vs); d = np.concatenate(ds); yr = np.concatenate(yrs)
    print(f'{plat}: {len(v)} rows')

    def resid(theta):
        g0, g2, L_eff, K_us, d0 = theta
        de = d - d0
        g = g0 + g2 * de * de
        pred = v * g * de / (L_eff + K_us * v*v)
        return pred - yr
    x0 = [1.0, 0.0, L_priors[plat], 0.002, 0.0]
    res = least_squares(resid, x0,
        bounds=([0.3, -5.0, 1.0, -0.01, -0.05],
                [2.0,  5.0, 6.0,  0.03,  0.05]))
    g0, g2, L_eff, K_us, d0 = res.x
    print(f'  V2-static: g0={g0:.5f} g2={g2:.5f} L_eff={L_eff:.4f} K_us={K_us:.6f} d0={d0:.6f}  cost={res.cost:.4f}')
    params[plat] = dict(g0=float(g0), g2=float(g2), L_eff=float(L_eff),
                        K_us=float(K_us), delta0=float(d0))

    # fit tau by grid search per segment
    def lag_apply(yr_ss, t, tau):
        if tau <= 0: return yr_ss
        out = np.empty_like(yr_ss); out[0] = yr_ss[0]
        for k in range(len(yr_ss)-1):
            dt = t[k+1] - t[k]; a = dt / (tau + dt)
            out[k+1] = out[k] + a * (yr_ss[k+1] - out[k])
        return out

    best_tau, best_ss, best_n = 0.0, math.inf, 1
    for tau in np.linspace(0.0, 0.15, 16):
        ss = 0.0; n = 0
        for df in segs:
            vv = df['v_mps'].to_numpy()
            dd = df['delta_road_rad'].to_numpy()
            yy = df['yaw_rate_meas_rads'].to_numpy()
            tt = df['t_s'].to_numpy()
            de = dd - d0
            g = g0 + g2 * de * de
            yr_ss = vv * g * de / (L_eff + K_us * vv*vv)
            yr_p = lag_apply(yr_ss, tt, tau)
            m = vv > 2.0
            ss += float(np.sum((yr_p[m]-yy[m])**2)); n += int(m.sum())
        if ss < best_ss:
            best_ss = ss; best_tau = tau; best_n = n
    print(f'  V2-tau best = {best_tau:.3f}  train rmse = {math.sqrt(best_ss/best_n):.6f}')
    params[plat]['tau'] = float(best_tau)

print('\nV2 PARAMS:')
print(json.dumps(params, indent=2))
with open('/tmp/params_v2.json', 'w') as f:
    json.dump(params, f, indent=2)
