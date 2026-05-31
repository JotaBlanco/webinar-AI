"""V3: V1 physics model + complementary filter blend with a_lat_meas/v.

Model:
    yr_phys = lagged single-track-with-understeer-and-offset (V1 form)
    yr_alat = a_lat_meas / v       (only where v > v_min, else 0)
    yr_pred = (1-w(v)) * yr_phys + w(v) * yr_alat
where w(v) is a speed-gated blend (we don't want noisy a_lat at low speed).

We jointly fit [g, delta0, L_eff, K_us, tau, w_high] on train, where w_high is
the asymptotic blend weight at high v. w(v) = w_high * sigmoid((v - 5)/2).

This stays inference-time legal (all inputs are sim_df channels).
"""
import json, sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score  # noqa


def yr_phys(params_phys, v, delta, dt):
    g, delta0, L_eff, K_us, tau = params_phys
    yr_ss = v * (g * (delta - delta0)) / (L_eff + K_us * v * v)
    if tau <= 0:
        return yr_ss
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for k in range(len(yr_ss) - 1):
        a = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + a * (yr_ss[k+1] - yr[k])
    return yr


def yr_v3(params, v, delta, a_lat, dt):
    g, delta0, L_eff, K_us, tau, w_high = params
    yp = yr_phys((g, delta0, L_eff, K_us, tau), v, delta, dt)
    v_safe = np.where(v > 2.0, v, np.nan)
    yr_a = np.where(v > 2.0, a_lat / v_safe, yp)
    w = w_high / (1.0 + np.exp(-(v - 5.0) / 2.0))
    w = np.where(v > 2.0, w, 0.0)
    return (1.0 - w) * yp + w * yr_a


def loss(params, segs, v_min=2.0):
    total_sq, total_n = 0.0, 0
    for _, df in segs:
        v = df['v_mps'].to_numpy(float)
        delta = df['delta_road_rad'].to_numpy(float)
        a_lat = df['a_lat_meas_mps2'].to_numpy(float)
        yr_true = df['yaw_rate_meas_rads'].to_numpy(float)
        t = df['t_s'].to_numpy(float)
        if len(t) < 2:
            continue
        dt = np.diff(t); dt = np.append(dt, dt[-1])
        yrp = yr_v3(params, v, delta, a_lat, dt)
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

    # Initial from V1 fit
    init = {
        'FORD_F_150_LIGHTNING_MK1':   [0.86338, 0.001334, 3.2623, 0.00350, 0.0595, 0.3],
        'FORD_MUSTANG_MACH_E_MK1':    [0.87939, -0.000101, 2.1799, 0.00219, 0.0695, 0.3],
    }
    coeffs = {}
    for plat, paths in by_plat_train.items():
        print(f'== Fitting v3 {plat} ==')
        segs = [(p, pd.read_csv(p)) for p in paths]
        res = minimize(loss, init[plat], args=(segs,),
                       method='Nelder-Mead',
                       options={'xatol': 1e-5, 'fatol': 1e-9, 'maxiter': 3000})
        g, d0, L_eff, K_us, tau, w_high = res.x
        print(f'  g={g:.5f}  d0={d0:.6f}  L_eff={L_eff:.4f}  K_us={K_us:.5f}  tau={tau:.4f}  w_high={w_high:.3f}')
        print(f'  train RMSE = {np.sqrt(res.fun):.5f}')
        coeffs[plat] = {'g': g, 'delta0': d0, 'L_eff': L_eff, 'K_us': K_us, 'tau': tau, 'w_high': w_high}

    with open('artifacts/coeffs_v3.json', 'w') as f:
        json.dump(coeffs, f, indent=2)

    def predict_fn(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in coeffs:
            out['yaw_rate_pred_rads'] = sim_df.get('yaw_rate_pred_rads', 0.0)
            return out
        c = coeffs[platform]
        v = sim_df['v_mps'].to_numpy(float)
        delta = sim_df['delta_road_rad'].to_numpy(float)
        a_lat = sim_df['a_lat_meas_mps2'].to_numpy(float)
        t = sim_df['t_s'].to_numpy(float)
        dt = np.diff(t); dt = np.append(dt, dt[-1] if len(dt)>0 else 0.02)
        params = [c['g'], c['delta0'], c['L_eff'], c['K_us'], c['tau'], c['w_high']]
        out['yaw_rate_pred_rads'] = yr_v3(params, v, delta, a_lat, dt)
        return out

    print('\n== V3 DEV ==')
    r = score(predict_fn, segment_paths=dev)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)
    for k, v in r['per_regime'].items():
        print(' ', k, v)

    print('\n== V3 ALL ==')
    r = score(predict_fn)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)


if __name__ == '__main__':
    main()
