"""V2: per-platform fit, polynomial steering scale + per-segment delta offset
inferred from yaw_rate_meas==0 condition (using a_lat? no truth at inference).

The "δ₀ inferred from input alone" idea: when the car drives straight,
yr_meas≈0 and delta_road≈0 by symmetry — we can't use yr_meas at inference.
Instead we use measured a_lat ≈ 0 OR robust median of delta_road over a window.

Approach: estimate per-segment delta0 from the median delta_road in samples where
|a_lat_meas_mps2| < 0.5 m/s^2 (a proxy for straight driving). This DOES use a sim
input channel, not truth, so it is inference-time legal.

Model:
    delta_eff = delta_road - delta0_seg
    yr_ss = v * (g0 + g2 * delta_eff^2 * sign-preserving) * delta_eff / (L + K_us v^2)
       i.e. g(delta) = g0 + g2 * delta_eff^2

Then first-order lag with tau.
"""
import json, sys, os
import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score  # noqa


def estimate_delta0_seg(df):
    """Estimate per-segment steering offset from quasi-straight rows."""
    a_lat = df.get('a_lat_meas_mps2')
    delta = df['delta_road_rad'].to_numpy(float)
    if a_lat is None:
        return float(np.median(delta))
    a_lat = a_lat.to_numpy(float)
    mask = np.abs(a_lat) < 0.5
    if mask.sum() < 50:
        # Fall back to overall median
        return float(np.median(delta))
    return float(np.median(delta[mask]))


def yr_model_v2(params, v, delta_eff, dt):
    """params: [g0, g2, L_eff, K_us, tau]"""
    g0, g2, L_eff, K_us, tau = params
    gain = g0 + g2 * (delta_eff ** 2)
    yr_ss = v * (gain * delta_eff) / (L_eff + K_us * v * v)
    if tau <= 0:
        return yr_ss
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for k in range(len(yr_ss) - 1):
        alpha = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + alpha * (yr_ss[k+1] - yr[k])
    return yr


def loss(params, segs, v_min=2.0):
    total_sq, total_n = 0.0, 0
    for _, df, delta_eff_arr in segs:
        v = df['v_mps'].to_numpy(float)
        yr_true = df['yaw_rate_meas_rads'].to_numpy(float)
        t = df['t_s'].to_numpy(float)
        if len(t) < 2:
            continue
        dt = np.diff(t)
        dt = np.append(dt, dt[-1])
        yr_pred = yr_model_v2(params, v, delta_eff_arr, dt)
        mask = v > v_min
        if not mask.any():
            continue
        r = yr_pred[mask] - yr_true[mask]
        total_sq += float(np.sum(r * r))
        total_n += int(mask.sum())
    return total_sq / max(total_n, 1)


def main():
    with open('artifacts/split.json') as f:
        split = json.load(f)
    train, dev = split['train'], split['dev']

    by_plat_train, by_plat_dev = {}, {}
    for p in train:
        plat = p.split('/')[-5]
        by_plat_train.setdefault(plat, []).append(p)
    for p in dev:
        plat = p.split('/')[-5]
        by_plat_dev.setdefault(plat, []).append(p)

    # Precompute per-segment delta_eff arrays for the train set.
    def load(paths):
        out = []
        for p in paths:
            df = pd.read_csv(p)
            d0 = estimate_delta0_seg(df)
            delta_eff = df['delta_road_rad'].to_numpy(float) - d0
            out.append((p, df, delta_eff))
        return out

    init = {
        'FORD_F_150_LIGHTNING_MK1':   [0.87, 0.0, 3.30, 0.0035, 0.06],
        'FORD_MUSTANG_MACH_E_MK1':    [0.88, 0.0, 2.20, 0.0022, 0.07],
    }
    coeffs = {}
    for plat, paths in by_plat_train.items():
        print(f'== Fitting v2 {plat} on {len(paths)} train segments ==')
        segs = load(paths)
        res = minimize(loss, init[plat], args=(segs,),
                       method='Nelder-Mead',
                       options={'xatol': 1e-5, 'fatol': 1e-9, 'maxiter': 3000})
        g0, g2, L_eff, K_us, tau = res.x
        print(f'  g0={g0:.5f}  g2={g2:.4f}  L_eff={L_eff:.4f}  K_us={K_us:.5f}  tau={tau:.4f}')
        print(f'  train RMSE = {np.sqrt(res.fun):.5f}')
        coeffs[plat] = {'g0': g0, 'g2': g2, 'L_eff': L_eff, 'K_us': K_us, 'tau': tau}

    with open('artifacts/coeffs_v2.json', 'w') as f:
        json.dump(coeffs, f, indent=2)

    def predict_fn(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in coeffs:
            out['yaw_rate_pred_rads'] = sim_df.get('yaw_rate_pred_rads', 0.0)
            return out
        c = coeffs[platform]
        d0 = estimate_delta0_seg(sim_df)
        delta_eff = sim_df['delta_road_rad'].to_numpy(float) - d0
        v = sim_df['v_mps'].to_numpy(float)
        t = sim_df['t_s'].to_numpy(float)
        dt = np.diff(t)
        dt = np.append(dt, dt[-1] if len(dt) > 0 else 0.02)
        params = [c['g0'], c['g2'], c['L_eff'], c['K_us'], c['tau']]
        out['yaw_rate_pred_rads'] = yr_model_v2(params, v, delta_eff, dt)
        return out

    print('\n== V2 DEV ==')
    r_dev = score(predict_fn, segment_paths=dev)
    print('overall: yaw=', r_dev['yaw_rate_rmse'], 'cte=', r_dev['cte_rmse'])
    for plat, v in r_dev['per_platform'].items():
        print(' ', plat, v)
    for k, v in r_dev['per_regime'].items():
        print(' ', k, v)

    print('\n== V2 ALL ==')
    r_all = score(predict_fn)
    print('overall: yaw=', r_all['yaw_rate_rmse'], 'cte=', r_all['cte_rmse'])
    for plat, v in r_all['per_platform'].items():
        print(' ', plat, v)


if __name__ == '__main__':
    main()
