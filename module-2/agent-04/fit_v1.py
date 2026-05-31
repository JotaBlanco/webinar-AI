"""Fit per-platform bicycle steady-state coefficients (L_eff, K_us) and a
delta offset. Evaluates V1 on a held-out 30% of segments per platform."""
import sys, glob, json, random
import numpy as np, pandas as pd

random.seed(7)
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, '_shared')
from score import score
from traj_metrics import cte_rmse_segment

paths_by_plat = {}
for p in sorted(glob.glob('data/sim/segments/FORD_*/**/sim.csv', recursive=True)):
    plat = p.split('/segments/')[1].split('/')[0]
    paths_by_plat.setdefault(plat, []).append(p)

train_paths, dev_paths = [], []
for plat, ps in paths_by_plat.items():
    shuffled = ps[:]
    random.Random(7).shuffle(shuffled)
    cut = int(len(shuffled) * 0.7)
    train_paths.extend(shuffled[:cut])
    dev_paths.extend(shuffled[cut:])
print(f'train: {len(train_paths)} segs   dev: {len(dev_paths)} segs')

# Fit per platform on the train split
fits = {}
for plat, ps in paths_by_plat.items():
    ps_train = [p for p in ps if p in set(train_paths)]
    dfs = []
    for p in ps_train:
        try:
            dfs.append(pd.read_csv(p))
        except Exception:
            pass
    d = pd.concat(dfs, ignore_index=True)
    d = d[d['v_mps'] > 5].reset_index(drop=True)
    yr_t = d['yaw_rate_meas_rads'].values
    v = d['v_mps'].values
    delta = d['delta_road_rad'].values

    # Step 1: estimate steering offset d0 from straight-running (|delta|<0.005)
    # using mean residual: when delta small and v_mps moderate, yaw_truth should be ~0
    m_str = (np.abs(delta) < 0.005)
    # d0 from: yr_t * L / v = delta - d0  → only meaningful at higher delta. Use:
    # Compute d0 such that median residual at small delta is zero
    d0 = np.median(delta[m_str] - yr_t[m_str] * 3.7 / np.where(v[m_str] > 1, v[m_str], 1))
    # That used L=3.7 generically; better: estimate d0 from where yr_t≈0 and v>5
    m_yr_small = np.abs(yr_t) < 0.005
    d0 = float(np.median(delta[m_yr_small]))

    # Step 2: fit L_eff, K_us via linear regression v*(delta-d0)/yr_t = L_eff + K_us * v^2
    m = (np.abs(yr_t) > 0.01)
    lhs = v[m] * (delta[m] - d0) / yr_t[m]
    rhs_v2 = v[m] ** 2
    A = np.vstack([np.ones_like(rhs_v2), rhs_v2]).T
    # Robust fit via Huber-like reweighting: do a couple of IRLS iterations
    coef, *_ = np.linalg.lstsq(A, lhs, rcond=None)
    for _ in range(3):
        resid = lhs - A @ coef
        scale = max(1e-3, 1.4826 * np.median(np.abs(resid - np.median(resid))))
        w = 1.0 / np.maximum(1.0, np.abs(resid) / (3 * scale))
        Aw = A * w[:, None]
        coef, *_ = np.linalg.lstsq(Aw, lhs * w, rcond=None)
    L_eff, K_us = float(coef[0]), float(coef[1])
    fits[plat] = {"delta_offset_rad": d0, "L_eff_m": L_eff, "K_us": K_us}
    print(f'{plat}: d0={d0:.5f} rad, L_eff={L_eff:.4f}, K_us={K_us:.6f}')

# Save coefs
with open('final-model/coeffs.json', 'w') as fh:
    json.dump(fits, fh, indent=2)
print('\\nSaved coeffs to final-model/coeffs.json')

# Define V1 predictor
def predict_v1(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    if platform not in fits:
        out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
        return out
    f = fits[platform]
    v = sim_df['v_mps'].to_numpy(float)
    delta = sim_df['delta_road_rad'].to_numpy(float)
    de = delta - f['delta_offset_rad']
    L = f['L_eff_m']; K = f['K_us']
    yr = v * de / (L + K * v * v)
    out['yaw_rate_pred_rads'] = yr
    return out

# Score V0 and V1 on the dev split
def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out

r0 = score(v0, segment_paths=dev_paths)
r1 = score(predict_v1, segment_paths=dev_paths)
print('\\n=== DEV SPLIT ===')
print(f'V0: yaw_rmse={r0["yaw_rate_rmse"]:.5f}  cte_rmse={r0["cte_rmse"]:.3f}')
print(f'V1: yaw_rmse={r1["yaw_rate_rmse"]:.5f}  cte_rmse={r1["cte_rmse"]:.3f}')
for plat in r0['per_platform']:
    a = r0['per_platform'][plat]; b = r1['per_platform'][plat]
    print(f'  {plat}: V0 yr={a["yaw_rate_rmse"]:.5f} cte={a["cte_rmse"]:.2f}'
          f'  →  V1 yr={b["yaw_rate_rmse"]:.5f} cte={b["cte_rmse"]:.2f}')
print('per_regime V0:', r0['per_regime'])
print('per_regime V1:', r1['per_regime'])
