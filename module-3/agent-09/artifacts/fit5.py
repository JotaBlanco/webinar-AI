"""V5: V1 physics + per-segment additive yaw bias correction.

Idea: a_lat_meas/v is an essentially unbiased estimate of yaw rate at moderate
to high speed (independent of our model error). On near-straight rows, the
mean of (yr_v1 - a_lat/v) over the segment estimates a coherent per-segment
yaw bias we want to subtract from yr_v1.

We are inference-time legal: we use only sim_df channels.

Specifically:
    bias_seg = median over rows {v>5, |delta_road|<0.02} of (yr_v1 - a_lat/v)
If fewer than 100 qualifying rows, bias_seg = 0 (no correction).
Final yr_pred = yr_v1 - bias_seg.

Per-platform parameters from V1 — no need to re-fit since the bias correction
is segment-by-segment and zero-mean across the training set.
"""
import json, sys
import numpy as np
import pandas as pd

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score  # noqa


with open('/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/artifacts/coeffs.json') as f:
    V1 = json.load(f)


def yr_phys_v1(c, v, delta, dt):
    g, d0, Le, K, tau = c['g'], c['delta0'], c['L_eff'], c['K_us'], c['tau']
    yr_ss = v * (g * (delta - d0)) / (Le + K * v * v)
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for k in range(len(yr_ss)-1):
        a = dt[k] / (tau + dt[k])
        yr[k+1] = yr[k] + a * (yr_ss[k+1] - yr[k])
    return yr


def per_seg_bias(yr_v1, v, delta, a_lat,
                  v_min=5.0, delta_max=0.02, min_n=100):
    mask = (v > v_min) & (np.abs(delta) < delta_max)
    if mask.sum() < min_n:
        return 0.0
    yr_alat = a_lat[mask] / v[mask]
    return float(np.median(yr_v1[mask] - yr_alat))


def predict_fn(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    if platform not in V1:
        out['yaw_rate_pred_rads'] = sim_df.get('yaw_rate_pred_rads', 0.0)
        return out
    c = V1[platform]
    v = sim_df['v_mps'].to_numpy(float)
    delta = sim_df['delta_road_rad'].to_numpy(float)
    a_lat = sim_df['a_lat_meas_mps2'].to_numpy(float)
    t = sim_df['t_s'].to_numpy(float)
    dt = np.diff(t); dt = np.append(dt, dt[-1] if len(dt)>0 else 0.02)
    yr1 = yr_phys_v1(c, v, delta, dt)
    bias = per_seg_bias(yr1, v, delta, a_lat)
    out['yaw_rate_pred_rads'] = yr1 - bias
    return out


def main():
    with open('artifacts/split.json') as f:
        split = json.load(f)
    dev = split['dev']

    print('\n== V5 DEV ==')
    r = score(predict_fn, segment_paths=dev)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)
    for k, v in r['per_regime'].items():
        print(' ', k, v)

    print('\n== V5 ALL ==')
    r = score(predict_fn)
    print('overall: yaw=', r['yaw_rate_rmse'], 'cte=', r['cte_rmse'])
    for plat, v in r['per_platform'].items():
        print(' ', plat, v)


if __name__ == '__main__':
    main()
