import sys, os, glob
import pandas as pd, numpy as np
ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
os.chdir(ROOT)

# Sample one segment from each platform
for plat, L in [('FORD_F_150_LIGHTNING_MK1', 3.70), ('FORD_MUSTANG_MACH_E_MK1', 2.984)]:
    paths = sorted(glob.glob(f'data/sim/segments/{plat}/**/sim.csv', recursive=True))
    p = paths[0]
    df = pd.read_csv(p)
    print('\n==', plat, p, 'len=', len(df))
    print(df[['t_s','delta_wheel_deg','delta_road_rad','v_mps','yaw_rate_meas_rads','yaw_rate_pred_rads']].head(5))
    # Compare delta_road to KS yaw rate at typical speeds
    v = df['v_mps'].values
    d = df['delta_road_rad'].values
    yr_m = df['yaw_rate_meas_rads'].values
    yr_p = df['yaw_rate_pred_rads'].values
    yr_ks = (v / L) * np.tan(d)
    print('  V0 RMSE this seg:', np.sqrt(np.mean((yr_p - yr_m)**2)))
    print('  KS  RMSE this seg:', np.sqrt(np.mean((yr_ks - yr_m)**2)))
    # Slope of meas/ks at speed > 10
    m = (v > 10) & (np.abs(d) > 0.005)
    if m.sum() > 50:
        ratio = (yr_m[m] / yr_ks[m])
        print(f'  ratio meas/KS at v>10 |d|>0.005: median={np.median(ratio):.3f} mean={np.mean(ratio):.3f} n={m.sum()}')
