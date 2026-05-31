"""V2: V1 steady-state bicycle + first-order yaw-rate lag.
Also tries a small per-platform tau search."""
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
    train_paths.extend(sh[:cut])
    dev_paths.extend(sh[cut:])

with open('final-model/coeffs.json') as fh:
    fits = json.load(fh)
print('Loaded fits:', fits)

def predict_with_lag(sim_df, platform, tau):
    out = pd.DataFrame(index=sim_df.index)
    if platform not in fits:
        out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
        return out
    f = fits[platform]
    t = sim_df['t_s'].to_numpy(float)
    v = sim_df['v_mps'].to_numpy(float)
    delta = sim_df['delta_road_rad'].to_numpy(float)
    de = delta - f['delta_offset_rad']
    L = f['L_eff_m']; K = f['K_us']
    yr_ss = v * de / (L + K * v * v)
    if tau <= 1e-6:
        out['yaw_rate_pred_rads'] = yr_ss
        return out
    # First-order lag: y[i+1] = y[i] + dt/tau * (yr_ss[i] - y[i])
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    for i in range(len(yr_ss) - 1):
        alpha = dt[i] / tau
        if alpha > 1.0: alpha = 1.0
        y[i+1] = y[i] + alpha * (yr_ss[i] - y[i])
    out['yaw_rate_pred_rads'] = y
    return out

# Tau search per platform on train split
best_taus = {}
for plat in fits.keys():
    train_p = [p for p in train_paths if plat in p]
    best_tau, best_rmse = 0.0, float('inf')
    for tau in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
        fn = lambda df, pl, t=tau: predict_with_lag(df, pl, t)
        r = score(fn, segment_paths=train_p, platform_filter=plat)
        rmse = r['yaw_rate_rmse']
        if rmse < best_rmse:
            best_rmse = rmse; best_tau = tau
        print(f'  {plat} tau={tau:.2f}: yr_rmse={rmse:.5f}')
    best_taus[plat] = best_tau
    print(f'  ==> best tau for {plat}: {best_tau} (train yr_rmse={best_rmse:.5f})')

# Update coeffs
for plat in fits:
    fits[plat]['tau_s'] = best_taus[plat]
with open('final-model/coeffs.json', 'w') as fh:
    json.dump(fits, fh, indent=2)
print('Updated coeffs:', fits)

# Evaluate V2 on dev split
def predict_v2(sim_df, platform):
    tau = fits.get(platform, {}).get('tau_s', 0.0)
    return predict_with_lag(sim_df, platform, tau)

def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out

r0 = score(v0, segment_paths=dev_paths)
r2 = score(predict_v2, segment_paths=dev_paths)
print('\\n=== DEV SPLIT ===')
print(f'V0: yaw_rmse={r0["yaw_rate_rmse"]:.5f}  cte_rmse={r0["cte_rmse"]:.3f}')
print(f'V2: yaw_rmse={r2["yaw_rate_rmse"]:.5f}  cte_rmse={r2["cte_rmse"]:.3f}')
for plat in r0['per_platform']:
    a = r0['per_platform'][plat]; b = r2['per_platform'][plat]
    print(f'  {plat}: V0 yr={a["yaw_rate_rmse"]:.5f} cte={a["cte_rmse"]:.2f}'
          f'  →  V2 yr={b["yaw_rate_rmse"]:.5f} cte={b["cte_rmse"]:.2f}')
print('per_regime V2:', r2['per_regime'])
