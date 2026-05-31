"""Diagnose Mach-E: maybe yaw_rate has noise floor, or steering scale is off."""
import os, glob, numpy as np, pandas as pd
ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
os.chdir(ROOT)

paths = sorted(glob.glob('data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv', recursive=True))
# Pool
v_all=[]; d_all=[]; y_all=[]
for p in paths[::4]:  # subsample
    df = pd.read_csv(p)
    v_all.append(df['v_mps'].to_numpy())
    d_all.append(df['delta_road_rad'].to_numpy())
    y_all.append(df['yaw_rate_meas_rads'].to_numpy())
v = np.concatenate(v_all); d = np.concatenate(d_all); y = np.concatenate(y_all)
print('Total samples:', len(v))

# Distribution of yaw_rate when steering ~0
m_straight = (np.abs(d) < 0.005) & (v > 5)
print(f'Straight-driving subset (n={m_straight.sum()}): y mean={y[m_straight].mean():.5f}, std={y[m_straight].std():.5f}')
# This is the noise floor / residual yaw rate at zero steering.

# Linear fit: y = a*v*d on |d|>0.01
m = (v>10) & (np.abs(d)>0.01)
slope = np.sum(v[m]*d[m]*y[m]) / np.sum((v[m]*d[m])**2)
print(f'Best fit y ≈ a * v*d: a={slope:.4f}; expected 1/L=1/2.984={1/2.984:.4f}')

# Try y = a*v*d + b*v^2*y  ... already covered
# Or steering offset across segments
# Look at residual at high speed steady
L = 2.984
m_steady = (v>15) & (np.abs(d)>0.005)
y_pred = (v/L)*np.tan(d)
print('At v>15, |d|>0.005:')
print('  pred mean=', y_pred[m_steady].mean(), 'meas mean=', y[m_steady].mean(), 'resid std=', (y_pred[m_steady]-y[m_steady]).std())

# Check correlation with a_lat
df = pd.read_csv(paths[0])
print('\nFirst seg columns containing acc / yaw:')
print([c for c in df.columns if 'acc' in c or 'yaw' in c or 'lat' in c])

# Look at psi_rad and delta_state_rad (vs delta_road_rad) - maybe predict already shows scale issue
print(df[['delta_road_rad','delta_state_rad','yaw_rate_meas_rads','yaw_rate_pred_rads']].describe())
