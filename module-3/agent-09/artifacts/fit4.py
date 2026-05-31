"""V4: V1 + per-segment delta0 estimate from low-a_lat rows.

delta0_seg = median(delta_road) over rows with |a_lat_meas| < 0.3 and v > 5.
If fewer than 50 qualifying rows, fall back to global delta0 fitted from train.

Effective delta is delta_eff = delta_road - delta0_seg.

Use V1 model parameters but re-fit (g, L_eff, K_us, tau) with delta_eff in place
of (delta - delta0_global).
"""
import json, sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score  # noqa


def estimate_delta0_seg(df, fallback):
    a_lat = df['a_lat_meas_mps2'].to_numpy(float)
    delta = df['delta_road_rad'].to_numpy(float)
    v = df['v_mps'].to_numpy(float)
    mask = (np.abs(a_lat) < 0.3) & (v > 5.0)
    if mask.sum() < 50:
        return fallback
    return float(np.median(delta[mask]))


def yr_phys(params, v, delta_eff, dt):
    g, L_eff, K_us, tau = params
    yr_ss = v * (g * delta_eff) / (L_eff + K_us * v * v)
    if tau <= 0:
        return yr_ss
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for k in range(len(yr_ss)-1):
        a = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + a * (yr_ss[k+1] - yr[k])
    return yr


def loss(params, segs, v_min=2.0):
    total_sq, total_n = 0.0, 0
    for delta_eff_arr, v, yr_true, t in segs:
        if len(t) < 2:
            continue
        dt = np.diff(t); dt = np.append(dt, dt[-1])
        yrp = yr_phys(params, v, delta_eff_arr, dt)
        mask = v > v_min
        r = yrp[mask] - yr_true[mask]
        total_sq += float(np.sum(r * r))
        total_n += int(mask.sum())
    return total_sq / max(total_n, 1)


def main():
    with open('artifacts/split.json') as f:
        split = json.load(f)
    train, dev = split['train'], split['dev']

    by_plat_train = {}
    for p in train:
        plat = p.split('/')[-5]
        by_plat_train.setdefault(plat, []).append(p)

    # Fallback delta0 from V1
    with open('artifacts/coeffs.json') as f:
        v1 = json.load(f)
    fallback = {plat: v1[plat]['delta0'] for plat in v1}

    init = {
        'FORD_F_150_LIGHTNING_MK1':   [0.86, 3.26, 0.0035, 0.06],
        'FORD_MUSTANG_MACH_E_MK1':    [0.88, 2.18, 0.0022, 0.07],
    }
    coeffs = {}
    for plat, paths in by_plat_train.items():
        print(f'== Fitting v4 {plat} ==')
        fb = fallback[plat]
        segs = []
        for p in paths:
            df = pd.read_csv(p)
            d0 = estimate_delta0_seg(df, fb)
            delta_eff = df['delta_road_rad'].to_numpy(float) - d0
            v = df['v_mps'].to_numpy(float)
            yr_t = df['yaw_rate_meas_rads'].to_numpy(float)
            t = df['t_s'].to_numpy(float)
            segs.append((delta_eff, v, yr_t, t))
        res = minimize(loss, init[plat], args=(segs,),
                       method='Nelder-Mead',
                       options={'xatol': 1e-5, 'fatol': 1e-9, 'maxiter': 3000})
        g, L_eff, K_us, tau = res.x
        print(f'  g={g:.5f}  L_eff={L_eff:.4f}  K_us={K_us:.5f}  tau={tau:.4f}')
        print(f'  train RMSE = {np.sqrt(res.fun):.5f}')
        coeffs[plat] = {'g': g, 'L_eff': L_eff, 'K_us': K_us, 'tau': tau,
                        'delta0_fallback': fb}

    with open('artifacts/coeffs_v4.json', 'w') as f:
        json.dump(coeffs, f, indent=2)

    def predict_fn(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in coeffs:
            out['yaw_rate_pred_rads'] = sim_df.get('yaw_rate_pred_rads', 0.0)
            return out
        c = coeffs[platform]
        d0 = estimate_delta0_seg(sim_df, c['delta0_fallback'])
        delta_eff = sim_df['delta_road_rad'].to_numpy(float) - d0
        v = sim_df['v_mps'].to_numpy(float)
        t = sim_df['t_s'].to_numpy(float)
        dt = np.diff(t); dt = np.append(dt, dt[-1] if len(dt)>0 else 0.02)
        params = [c['g'], c['L_eff'], c['K_us'], c['tau']]
        out['yaw_rate_pred_rads'] = yr_phys(params, v, delta_eff, dt)
        return out

    print('\n== V4 DEV ==')
    r = score(predict_fn, segment_paths=dev)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)
    for k, v in r['per_regime'].items():
        print(' ', k, v)

    print('\n== V4 ALL ==')
    r = score(predict_fn)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)


if __name__ == '__main__':
    main()
