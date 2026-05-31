"""V3: polynomial steering scale g(delta)= g0 + g2*delta^2 on Mach-E.
Refit (g0, g2, K_us, delta_0)."""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'code')
from split import split
from score import score
import pandas as pd
import numpy as np
import parameters as P
from scipy.optimize import least_squares

tr, dv = split(dev_fraction=0.25, seed=42)
L_MAP = {'FORD_F_150_LIGHTNING_MK1': P.F150_LIGHTNING.L,
         'FORD_MUSTANG_MACH_E_MK1': P.MACH_E.L}


def platform_from_path(p):
    return Path(p).resolve().parents[3].name


def load_concat(paths, plat):
    deltas, vs, yrs = [], [], []
    for p in paths:
        if platform_from_path(p) != plat:
            continue
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        m = (df['v_mps'] > 5).values
        deltas.append(df['delta_road_rad'].values[m])
        vs.append(df['v_mps'].values[m])
        yrs.append(df['yaw_rate_meas_rads'].values[m])
    return np.concatenate(deltas), np.concatenate(vs), np.concatenate(yrs)


# Fit polynomial steering for both
poly_results = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    L = L_MAP[plat]
    delta, v, yr = load_concat(tr, plat)

    # Model: yr = v * (g0 + g2 * (delta-d0)^2) * (delta-d0) / (L + K_us*v^2)
    def resid(params, delta, v, yr, L):
        g0, g2, kus, d0 = params
        de = delta - d0
        pred = v * (g0 + g2 * de**2) * de / (L + kus * v**2)
        return pred - yr

    x0 = [1.0, 0.0, 0.003, 0.0]
    res = least_squares(
        resid, x0, args=(delta, v, yr, L),
        bounds=([0.5, -50.0, -0.005, -0.05], [2.0, 50.0, 0.030, 0.05]),
        max_nfev=500,
    )
    g0, g2, kus, d0 = res.x
    pred = v * (g0 + g2 * (delta - d0)**2) * (delta - d0) / (L + kus * v**2)
    rmse = float(np.sqrt(np.mean((pred - yr)**2)))
    print(f"{plat}: g0={g0:.4f} g2={g2:.4f} K_us={kus:.5f} d0={d0:.6f}  rmse={rmse:.5f}")
    poly_results[plat] = {'g0': float(g0), 'g2': float(g2), 'K_us': float(kus),
                          'delta_0': float(d0), 'L': L}

# Build predict and evaluate
def steady_state_poly(delta, v, c):
    de = delta - c['delta_0']
    g = c['g0'] + c['g2'] * de**2
    return v * g * de / (c['L'] + c['K_us'] * v**2)


def apply_lag(yr_ss, t, tau):
    if tau <= 0:
        return yr_ss
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    for i in range(1, len(yr_ss)):
        dt = t[i] - t[i-1]
        alpha = dt / (tau + dt)
        y[i] = y[i-1] + alpha * (yr_ss[i] - y[i-1])
    return y


def make_predict(coeffs, tau=0.08):
    def predict(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in coeffs:
            out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
            return out
        c = coeffs[platform]
        delta = sim_df['delta_road_rad'].values.astype(float)
        v = sim_df['v_mps'].values.astype(float)
        t = sim_df['t_s'].values.astype(float)
        yr_ss = steady_state_poly(delta, v, c)
        yr = apply_lag(yr_ss, t, tau)
        out['yaw_rate_pred_rads'] = yr
        return out
    return predict


for tau in [0.0, 0.05, 0.08, 0.10]:
    p = make_predict(poly_results, tau=tau)
    r = score(p, segment_paths=dv)
    print(f"V3 poly tau={tau}: yaw={r['yaw_rate_rmse']:.5f} CTE={r['cte_rmse']:.3f}")
    for k, vv in r['per_platform'].items():
        print(f"   {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")
