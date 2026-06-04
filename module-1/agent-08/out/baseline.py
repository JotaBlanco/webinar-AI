"""Compute V0 baseline yaw-rate RMSE per platform."""
import pandas as pd
import numpy as np
import glob

platforms_with_truth = ['HYUNDAI_IONIQ_5', 'FORD_MUSTANG_MACH_E_MK1', 'FORD_F_150_LIGHTNING_MK1']

for plat in platforms_with_truth:
    files = glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim/segments/{plat}/*/*/*/sim.csv')
    sq_sum = 0.0
    n = 0
    for f in files:
        df = pd.read_csv(f, usecols=['yaw_rate_meas_rads', 'yaw_rate_pred_rads'])
        r = df.yaw_rate_meas_rads - df.yaw_rate_pred_rads
        sq_sum += float((r ** 2).sum())
        n += len(r)
    rmse = np.sqrt(sq_sum / n)
    print(f'{plat}: V0 yaw-rate RMSE = {rmse:.5f} rad/s   (N={n} samples, {len(files)} segs)')

# Tesla — no truth in sim, but check sim-only baseline structure
print()
print('Tesla — no yaw_rate_meas_rads in sim/, must rely on prior')
