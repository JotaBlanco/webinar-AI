"""Compare KS naive vs V0-predicted on Mach-E to understand."""
import os, glob, numpy as np, pandas as pd
ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
os.chdir(ROOT)
L = 2.984
paths = sorted(glob.glob('data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv', recursive=True))
sse_v0 = sse_ks = 0.0; n = 0
for p in paths:
    df = pd.read_csv(p)
    v = df['v_mps'].to_numpy(); d = df['delta_road_rad'].to_numpy()
    y = df['yaw_rate_meas_rads'].to_numpy(); ypred = df['yaw_rate_pred_rads'].to_numpy()
    yks = (v/L)*np.tan(d)
    m = v > 2.0
    sse_v0 += float(np.sum((ypred[m]-y[m])**2))
    sse_ks += float(np.sum((yks[m]-y[m])**2))
    n += int(m.sum())
print('Mach-E pooled (v>2):')
print(' V0   RMSE:', np.sqrt(sse_v0/n))
print(' KSnaive RMSE:', np.sqrt(sse_ks/n))
print(' n=', n)
