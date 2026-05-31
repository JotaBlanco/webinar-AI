"""Score V2 model (poly-g) vs V1 vs V0 on dev + full FORD."""
import sys, json, math
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, '_shared')

from score import score
from split import split

with open('/tmp/params_v2.json') as f:
    P2 = json.load(f)


def _lag(yr_ss, t, tau):
    if tau <= 0 or len(yr_ss) < 2: return yr_ss.copy()
    out = np.empty_like(yr_ss); out[0] = yr_ss[0]
    dt = np.diff(t)
    for k in range(len(yr_ss)-1):
        a = dt[k] / (tau + dt[k])
        out[k+1] = out[k] + a * (yr_ss[k+1] - out[k])
    return out


def predict_v2(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    if platform not in P2:
        out['yaw_rate_pred_rads'] = sim_df.get('yaw_rate_pred_rads', pd.Series(0.0, index=sim_df.index)).astype(float).values
        return out
    p = P2[platform]
    t = sim_df['t_s'].to_numpy(float)
    v = sim_df['v_mps'].to_numpy(float)
    d = sim_df['delta_road_rad'].to_numpy(float)
    de = d - p['delta0']
    g = p['g0'] + p['g2'] * de*de
    yr_ss = v * g * de / (p['L_eff'] + p['K_us'] * v*v)
    yr = _lag(yr_ss, t, p['tau'])
    bad = ~np.isfinite(yr)
    if bad.any():
        yr = np.where(bad, sim_df.get('yaw_rate_pred_rads', 0.0).astype(float), yr)
    out['yaw_rate_pred_rads'] = yr
    return out


train, dev = split(dev_fraction=0.25, seed=42)

print('V2 — DEV:')
r = score(predict_v2, segment_paths=dev)
print(f'  yaw={r["yaw_rate_rmse"]:.6f}  CTE={r["cte_rmse"]:.3f}')
for k,v in r['per_platform'].items():
    print(f'    {k}: yaw={v["yaw_rate_rmse"]:.6f}  CTE={v["cte_rmse"]:.3f}')
for k,v in r['per_regime'].items():
    print(f'    [{k}]: yaw={v["yaw_rate_rmse"]:.6f}  n={v["n_samples"]}')

print('\nV2 — ALL FORD:')
r = score(predict_v2)
print(f'  yaw={r["yaw_rate_rmse"]:.6f}  CTE={r["cte_rmse"]:.3f}')
for k,v in r['per_platform'].items():
    print(f'    {k}: yaw={v["yaw_rate_rmse"]:.6f}  CTE={v["cte_rmse"]:.3f}')
