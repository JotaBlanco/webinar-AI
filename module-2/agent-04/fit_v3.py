"""V3: Refit with tighter sample selection and verify with full-data evaluation."""
import sys, glob, json, random
import numpy as np, pandas as pd

random.seed(7)
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score

paths_by_plat = {}
for p in sorted(glob.glob('data/sim/segments/FORD_*/**/sim.csv', recursive=True)):
    plat = p.split('/segments/')[1].split('/')[0]
    paths_by_plat.setdefault(plat, []).append(p)

train_paths, dev_paths = [], []
for plat, ps in paths_by_plat.items():
    sh = ps[:]; random.Random(7).shuffle(sh)
    cut = int(len(sh) * 0.7)
    train_paths.extend(sh[:cut]); dev_paths.extend(sh[cut:])

fits = {}
for plat, ps in paths_by_plat.items():
    ps_train = [p for p in ps if p in set(train_paths)]
    dfs = [pd.read_csv(p) for p in ps_train]
    d = pd.concat(dfs, ignore_index=True)
    d = d[d['v_mps'] > 5].reset_index(drop=True)
    yr_t = d['yaw_rate_meas_rads'].values
    v = d['v_mps'].values
    delta = d['delta_road_rad'].values

    # offset from near-zero yaw samples
    m_yr_small = (np.abs(yr_t) < 0.003) & (np.abs(delta) < 0.02)
    d0 = float(np.median(delta[m_yr_small])) if m_yr_small.sum() > 100 else 0.0

    # Use only cornering samples for L/K fit
    m = (np.abs(yr_t) > 0.02) & (np.abs(delta - d0) > 0.005)
    lhs = v[m] * (delta[m] - d0) / yr_t[m]
    rhs_v2 = v[m] ** 2
    # remove obvious outliers (signs flipped, etc.)
    keep = (lhs > 0.5) & (lhs < 30)
    lhs = lhs[keep]; rhs_v2 = rhs_v2[keep]
    A = np.vstack([np.ones_like(rhs_v2), rhs_v2]).T
    # Huber IRLS
    coef, *_ = np.linalg.lstsq(A, lhs, rcond=None)
    for _ in range(5):
        r = lhs - A @ coef
        scale = max(1e-3, 1.4826 * np.median(np.abs(r - np.median(r))))
        w = 1.0 / np.maximum(1.0, np.abs(r) / (2 * scale))
        Aw = A * w[:, None]
        coef, *_ = np.linalg.lstsq(Aw, lhs * w, rcond=None)
    L_eff, K_us = float(coef[0]), float(coef[1])
    fits[plat] = {"delta_offset_rad": d0, "L_eff_m": L_eff, "K_us": K_us, "tau_s": 0.05}
    print(f'{plat}: d0={d0:.5f}  L_eff={L_eff:.4f}  K_us={K_us:.6f}  n_train_samp={keep.sum()}')

with open('final-model/coeffs.json', 'w') as fh:
    json.dump(fits, fh, indent=2)
print(json.dumps(fits, indent=2))

def predict_lag(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    if platform not in fits:
        out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
        return out
    f = fits[platform]
    t = sim_df['t_s'].to_numpy(float)
    v = sim_df['v_mps'].to_numpy(float)
    delta = sim_df['delta_road_rad'].to_numpy(float)
    de = delta - f['delta_offset_rad']
    L = f['L_eff_m']; K = f['K_us']; tau = f.get('tau_s', 0.0)
    yr_ss = v * de / (L + K * v * v)
    if tau <= 1e-6:
        out['yaw_rate_pred_rads'] = yr_ss
        return out
    y = np.empty_like(yr_ss); y[0] = yr_ss[0]
    dt = np.diff(t)
    for i in range(len(yr_ss) - 1):
        alpha = dt[i] / tau
        if alpha > 1.0: alpha = 1.0
        y[i+1] = y[i] + alpha * (yr_ss[i] - y[i])
    out['yaw_rate_pred_rads'] = y
    return out

def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out

print('\\n=== DEV SPLIT ===')
r0 = score(v0, segment_paths=dev_paths)
r3 = score(predict_lag, segment_paths=dev_paths)
print(f'V0: yaw_rmse={r0["yaw_rate_rmse"]:.5f}  cte_rmse={r0["cte_rmse"]:.3f}')
print(f'V3: yaw_rmse={r3["yaw_rate_rmse"]:.5f}  cte_rmse={r3["cte_rmse"]:.3f}')
for plat in r0['per_platform']:
    a = r0['per_platform'][plat]; b = r3['per_platform'][plat]
    print(f'  {plat}: V0 yr={a["yaw_rate_rmse"]:.5f} cte={a["cte_rmse"]:.2f}'
          f'  →  V3 yr={b["yaw_rate_rmse"]:.5f} cte={b["cte_rmse"]:.2f}')

print('\\n=== FULL DATA (train + dev) ===')
all_paths = train_paths + dev_paths
r0a = score(v0, segment_paths=all_paths)
r3a = score(predict_lag, segment_paths=all_paths)
print(f'V0: yaw_rmse={r0a["yaw_rate_rmse"]:.5f}  cte_rmse={r0a["cte_rmse"]:.3f}')
print(f'V3: yaw_rmse={r3a["yaw_rate_rmse"]:.5f}  cte_rmse={r3a["cte_rmse"]:.3f}')
for plat in r0a['per_platform']:
    a = r0a['per_platform'][plat]; b = r3a['per_platform'][plat]
    print(f'  {plat}: V0 yr={a["yaw_rate_rmse"]:.5f} cte={a["cte_rmse"]:.2f}'
          f'  →  V3 yr={b["yaw_rate_rmse"]:.5f} cte={b["cte_rmse"]:.2f}')
print('per_regime V3:', r3a['per_regime'])
