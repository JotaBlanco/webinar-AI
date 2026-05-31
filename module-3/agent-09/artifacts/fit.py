"""Fit per-platform understeer + steering offset/scale + first-order lag.

Model:
    yr_ss(t)  = v(t) * (g * (delta(t) - delta0)) / (L_eff + K_us * v(t)^2)
    yr_pred   = first-order lag of yr_ss with time constant tau

Fitted per platform on train only. Evaluated on dev.

Optionally with a residual correction on a_lat:
    yr_pred += alpha * (a_lat_meas / v - yr_pred)   # complementary blend (DISABLED by default)
"""
import json, glob, sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score  # noqa
from traj_metrics import cte_rmse_segment  # noqa


def load_segments(paths):
    return [(p, pd.read_csv(p)) for p in paths]


def yr_model(params, v, delta, dt):
    """Compute yr_pred for arrays v, delta with given params.
    params: [g, delta0, L_eff, K_us, tau]
    """
    g, delta0, L_eff, K_us, tau = params
    yr_ss = v * (g * (delta - delta0)) / (L_eff + K_us * v * v)
    if tau <= 0:
        return yr_ss
    # First-order lag: y[k+1] = y[k] + dt/tau * (yr_ss[k] - y[k])
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for k in range(len(yr_ss) - 1):
        alpha = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + alpha * (yr_ss[k+1] - yr[k])
    return yr


def loss_yaw(params, segs, v_min=2.0):
    """Pooled MSE of yaw rate on segments."""
    total_sq, total_n = 0.0, 0
    for _, df in segs:
        v = df['v_mps'].to_numpy(float)
        delta = df['delta_road_rad'].to_numpy(float)
        yr_true = df['yaw_rate_meas_rads'].to_numpy(float)
        t = df['t_s'].to_numpy(float)
        if len(t) < 2:
            continue
        dt = np.diff(t)
        dt = np.append(dt, dt[-1])
        yr_pred = yr_model(params, v, delta, dt)
        mask = v > v_min
        if not mask.any():
            continue
        r = yr_pred[mask] - yr_true[mask]
        total_sq += float(np.sum(r * r))
        total_n += int(mask.sum())
    return total_sq / max(total_n, 1)


def fit_platform(segs, p_init, p_bounds):
    res = minimize(
        loss_yaw, p_init, args=(segs,),
        method='Nelder-Mead', options={'xatol': 1e-5, 'fatol': 1e-9, 'maxiter': 2000}
    )
    return res


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

    # Initial guesses from openpilot priors and approach-menu hints.
    # Lightning: L=3.70, K_us higher than Mach-E.
    # Mach-E:    L=2.984, lighter, lower K_us.
    init = {
        'FORD_F_150_LIGHTNING_MK1':   [1.0, 0.0, 3.70, 0.003, 0.06],
        'FORD_MUSTANG_MACH_E_MK1':    [1.0, 0.0, 2.984, 0.002, 0.06],
    }

    coeffs = {}
    for plat, paths in by_plat_train.items():
        print(f'== Fitting {plat} on {len(paths)} train segments ==')
        segs = load_segments(paths)
        res = fit_platform(segs, init[plat], None)
        g, d0, L_eff, K_us, tau = res.x
        print(f'  g={g:.5f}  d0={d0:.6f}  L_eff={L_eff:.4f}  K_us={K_us:.5f}  tau={tau:.4f}')
        print(f'  train MSE = {res.fun:.7f}  (RMSE = {np.sqrt(res.fun):.5f})')
        coeffs[plat] = {'g': g, 'delta0': d0, 'L_eff': L_eff, 'K_us': K_us, 'tau': tau}

    with open('artifacts/coeffs.json', 'w') as f:
        json.dump(coeffs, f, indent=2)
    print('Wrote artifacts/coeffs.json')

    # Build a predict callable from these coeffs for evaluation.
    def predict_fn(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in coeffs:
            # Tesla and any unknown: fall back to V0
            out['yaw_rate_pred_rads'] = sim_df.get('yaw_rate_pred_rads', 0.0)
            return out
        c = coeffs[platform]
        params = [c['g'], c['delta0'], c['L_eff'], c['K_us'], c['tau']]
        v = sim_df['v_mps'].to_numpy(float)
        delta = sim_df['delta_road_rad'].to_numpy(float)
        t = sim_df['t_s'].to_numpy(float)
        dt = np.diff(t)
        dt = np.append(dt, dt[-1] if len(dt) > 0 else 0.02)
        out['yaw_rate_pred_rads'] = yr_model(params, v, delta, dt)
        return out

    # Score on dev
    print('\n== DEV (route-level holdout) ==')
    r_dev = score(predict_fn, segment_paths=dev)
    print('overall: yaw=', r_dev['yaw_rate_rmse'], 'cte=', r_dev['cte_rmse'])
    for plat, v in r_dev['per_platform'].items():
        print(' ', plat, v)
    for k, v in r_dev['per_regime'].items():
        print(' ', k, v)

    # V0 dev for ref
    def v0_predict(sim_df, platform):
        return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)
    print('\n== V0 dev ==')
    r0 = score(v0_predict, segment_paths=dev)
    print('overall: yaw=', r0['yaw_rate_rmse'], 'cte=', r0['cte_rmse'])
    for plat, v in r0['per_platform'].items():
        print(' ', plat, v)

    # All-data scoring
    print('\n== ALL Ford segments ==')
    r_all = score(predict_fn)
    print('overall: yaw=', r_all['yaw_rate_rmse'], 'cte=', r_all['cte_rmse'])
    for plat, v in r_all['per_platform'].items():
        print(' ', plat, v)


if __name__ == '__main__':
    main()
