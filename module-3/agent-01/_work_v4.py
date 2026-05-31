"""V4: complementary fusion with a_lat/v. Fit blend coefficient k per platform."""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'code')
from split import split
from score import score
import pandas as pd
import numpy as np
from scipy.optimize import least_squares
import parameters as P

tr, dv = split(dev_fraction=0.25, seed=42)
L_MAP = {'FORD_F_150_LIGHTNING_MK1': P.F150_LIGHTNING.L,
         'FORD_MUSTANG_MACH_E_MK1': P.MACH_E.L}

V1_COEFFS = {
    'FORD_F_150_LIGHTNING_MK1': {'g': 0.9637434201304231, 'K_us': 0.0035947144818903242,
                                  'delta_0': 0.0012339825423108163, 'L': 3.7},
    'FORD_MUSTANG_MACH_E_MK1':  {'g': 1.1758194286274308, 'K_us': 0.0025190900693713852,
                                  'delta_0': -3.6482033317411595e-05, 'L': 2.984},
}


def platform_from_path(p):
    return Path(p).resolve().parents[3].name


def steady_state(delta, v, c):
    return v * c['g'] * (delta - c['delta_0']) / (c['L'] + c['K_us'] * v**2)


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


# Fit k on training: yr_meas ≈ (1-k)*yr_model + k*(a_lat/v)
print("Fitting blend coefficient k per platform on training set...")
fit_k = {}
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    c = V1_COEFFS[plat]
    yr_models, alat_vs, yr_meass = [], [], []
    for p in tr:
        if platform_from_path(p) != plat:
            continue
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns or 'a_lat_meas_mps2' not in df.columns:
            continue
        m = (df['v_mps'] > 5).values
        delta = df['delta_road_rad'].values[m]
        v = df['v_mps'].values[m]
        yr = df['yaw_rate_meas_rads'].values[m]
        a_lat = df['a_lat_meas_mps2'].values[m]
        yr_models.append(steady_state(delta, v, c))
        alat_vs.append(a_lat / np.maximum(v, 0.1))
        yr_meass.append(yr)
    ym = np.concatenate(yr_models)
    av = np.concatenate(alat_vs)
    yt = np.concatenate(yr_meass)
    # Fit y = a*ym + b*av + c0 in pure LS
    A = np.column_stack([ym, av, np.ones_like(ym)])
    sol, *_ = np.linalg.lstsq(A, yt, rcond=None)
    print(f"  {plat}: a={sol[0]:.4f} b={sol[1]:.4f} c={sol[2]:.6f}")
    fit_k[plat] = {'a': float(sol[0]), 'b': float(sol[1]), 'c': float(sol[2])}


def make_predict(coeffs, blend, tau=0.05):
    def predict(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in coeffs:
            out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
            return out
        c = coeffs[platform]
        bl = blend.get(platform, {'a': 1.0, 'b': 0.0, 'c': 0.0})
        delta = sim_df['delta_road_rad'].values.astype(float)
        v = sim_df['v_mps'].values.astype(float)
        t = sim_df['t_s'].values.astype(float)
        yr_ss = steady_state(delta, v, c)
        yr_lag = apply_lag(yr_ss, t, tau)
        if 'a_lat_meas_mps2' in sim_df.columns:
            a_lat = sim_df['a_lat_meas_mps2'].values.astype(float)
            av = a_lat / np.maximum(v, 0.1)
            yr_out = bl['a'] * yr_lag + bl['b'] * av + bl['c']
        else:
            yr_out = yr_lag
        out['yaw_rate_pred_rads'] = yr_out
        return out
    return predict


for tau in [0.0, 0.05, 0.08]:
    p = make_predict(V1_COEFFS, fit_k, tau=tau)
    r = score(p, segment_paths=dv)
    print(f"\nV4 fuse tau={tau}: yaw={r['yaw_rate_rmse']:.5f} CTE={r['cte_rmse']:.3f}")
    for k, vv in r['per_platform'].items():
        print(f"   {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")
