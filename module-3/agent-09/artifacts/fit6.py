"""V6 (hybrid): per-platform choice of model.

Lightning: V1 (global delta0).
Mach-E:    V4 (per-segment delta0 from low-a_lat rows; global fallback).

Both use a first-order yaw-rate lag.
"""
import json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score  # noqa


with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/artifacts/coeffs.json') as f:
    V1 = json.load(f)
with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/artifacts/coeffs_v4.json') as f:
    V4 = json.load(f)


def yr_v1(c, v, delta, dt):
    g, d0, Le, K, tau = c['g'], c['delta0'], c['L_eff'], c['K_us'], c['tau']
    yr_ss = v * (g * (delta - d0)) / (Le + K * v * v)
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for k in range(len(yr_ss)-1):
        a = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + a * (yr_ss[k+1] - yr[k])
    return yr


def estimate_delta0_seg(sim_df, fallback):
    a_lat = sim_df['a_lat_meas_mps2'].to_numpy(float)
    delta = sim_df['delta_road_rad'].to_numpy(float)
    v = sim_df['v_mps'].to_numpy(float)
    mask = (np.abs(a_lat) < 0.3) & (v > 5.0)
    if mask.sum() < 50:
        return fallback
    return float(np.median(delta[mask]))


def yr_v4(c, sim_df):
    d0 = estimate_delta0_seg(sim_df, c['delta0_fallback'])
    delta_eff = sim_df['delta_road_rad'].to_numpy(float) - d0
    v = sim_df['v_mps'].to_numpy(float)
    t = sim_df['t_s'].to_numpy(float)
    dt = np.diff(t); dt = np.append(dt, dt[-1] if len(dt)>0 else 0.02)
    g, Le, K, tau = c['g'], c['L_eff'], c['K_us'], c['tau']
    yr_ss = v * (g * delta_eff) / (Le + K * v * v)
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for k in range(len(yr_ss)-1):
        a = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + a * (yr_ss[k+1] - yr[k])
    return yr


def predict_fn(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    if platform == 'FORD_F_150_LIGHTNING_MK1':
        c = V1[platform]
        v = sim_df['v_mps'].to_numpy(float)
        delta = sim_df['delta_road_rad'].to_numpy(float)
        t = sim_df['t_s'].to_numpy(float)
        dt = np.diff(t); dt = np.append(dt, dt[-1] if len(dt)>0 else 0.02)
        out['yaw_rate_pred_rads'] = yr_v1(c, v, delta, dt)
    elif platform == 'FORD_MUSTANG_MACH_E_MK1':
        c = V4[platform]
        out['yaw_rate_pred_rads'] = yr_v4(c, sim_df)
    else:
        # Tesla / unknown — V0 passthrough
        out['yaw_rate_pred_rads'] = sim_df.get('yaw_rate_pred_rads', 0.0)
    return out


def main():
    with open('artifacts/split.json') as f:
        split = json.load(f)
    dev = split['dev']

    print('\n== V6 hybrid DEV ==')
    r = score(predict_fn, segment_paths=dev)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)
    for k, v in r['per_regime'].items():
        print(' ', k, v)

    print('\n== V6 hybrid ALL ==')
    r = score(predict_fn)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)


if __name__ == '__main__':
    main()
