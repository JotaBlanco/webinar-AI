"""Tau sweep with V3 coefficients."""
import sys, glob, json, random
import numpy as np, pandas as pd

random.seed(7)
sys.path.insert(0, 'skills/score-model')
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

with open('final-model/coeffs.json') as fh:
    fits = json.load(fh)

def predict_lag(sim_df, platform, tau_map):
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
    tau = tau_map.get(platform, 0.0)
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

best_taus = {}
for plat in fits.keys():
    train_p = [p for p in train_paths if plat in p]
    print(f'\\n{plat} tau sweep:')
    best_tau, best_rmse, best_cte = 0.0, float('inf'), float('inf')
    for tau in [0.0, 0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]:
        tm = {plat: tau}
        fn = lambda df, pl, tm=tm: predict_lag(df, pl, tm)
        r = score(fn, segment_paths=train_p, platform_filter=plat)
        rmse = r['yaw_rate_rmse']; cte = r['cte_rmse']
        print(f'  tau={tau:.2f}: yr={rmse:.5f} cte={cte:.2f}')
        if rmse < best_rmse:
            best_rmse = rmse; best_tau = tau; best_cte = cte
    best_taus[plat] = best_tau
    print(f'  best tau={best_tau} (yr={best_rmse:.5f} cte={best_cte:.2f})')

for plat, tau in best_taus.items():
    fits[plat]['tau_s'] = tau

with open('final-model/coeffs.json', 'w') as fh:
    json.dump(fits, fh, indent=2)
print('\\nFinal coeffs:', fits)

def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out

def predict_final(sim_df, platform):
    return predict_lag(sim_df, platform, best_taus)

print('\\n=== DEV SPLIT (final) ===')
r0 = score(v0, segment_paths=dev_paths)
rf = score(predict_final, segment_paths=dev_paths)
print(f'V0: yaw_rmse={r0["yaw_rate_rmse"]:.5f}  cte_rmse={r0["cte_rmse"]:.3f}')
print(f'V_final: yaw_rmse={rf["yaw_rate_rmse"]:.5f}  cte_rmse={rf["cte_rmse"]:.3f}')
for plat in r0['per_platform']:
    a = r0['per_platform'][plat]; b = rf['per_platform'][plat]
    print(f'  {plat}: V0 yr={a["yaw_rate_rmse"]:.5f} cte={a["cte_rmse"]:.2f}'
          f'  →  Vf yr={b["yaw_rate_rmse"]:.5f} cte={b["cte_rmse"]:.2f}')

print('\\n=== FULL DATA ===')
all_paths = train_paths + dev_paths
r0a = score(v0, segment_paths=all_paths)
rfa = score(predict_final, segment_paths=all_paths)
print(f'V0: yaw_rmse={r0a["yaw_rate_rmse"]:.5f}  cte_rmse={r0a["cte_rmse"]:.3f}')
print(f'V_final: yaw_rmse={rfa["yaw_rate_rmse"]:.5f}  cte_rmse={rfa["cte_rmse"]:.3f}')
for plat in r0a['per_platform']:
    a = r0a['per_platform'][plat]; b = rfa['per_platform'][plat]
    print(f'  {plat}: V0 yr={a["yaw_rate_rmse"]:.5f} cte={a["cte_rmse"]:.2f}'
          f'  →  Vf yr={b["yaw_rate_rmse"]:.5f} cte={b["cte_rmse"]:.2f}')
print('per_regime:', rfa['per_regime'])
