"""Refit Mach-E without lag (tau=0): pure understeer+bias steady-state."""
import os, glob, json, numpy as np, pandas as pd
ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
os.chdir(ROOT)

L = 2.984
paths = sorted(glob.glob('data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv', recursive=True))
train = paths[::2]; dev = paths[1::2]

# Pool training samples
V=[]; D=[]; Y=[]
for p in train:
    df = pd.read_csv(p)
    v = df['v_mps'].to_numpy(); d = df['delta_road_rad'].to_numpy(); y = df['yaw_rate_meas_rads'].to_numpy()
    m = v > 3.0
    V.append(v[m]); D.append(d[m]); Y.append(y[m])
v = np.concatenate(V); d = np.concatenate(D); y = np.concatenate(Y)

# Linear OLS: v*d - y*L = K_us*(y*v^2) + delta0*v
rhs = v*d - y*L
A = np.column_stack([y*v*v, v])
coef,*_ = np.linalg.lstsq(A, rhs, rcond=None)
K_us, delta0 = coef
print('Fitted Mach-E (no-lag): K_us=', K_us, 'delta0=', delta0)

# Evaluate on dev
sse=0.0; n=0
sse_v0=0.0
for p in dev:
    df = pd.read_csv(p)
    v = df['v_mps'].to_numpy(); d = df['delta_road_rad'].to_numpy(); y = df['yaw_rate_meas_rads'].to_numpy()
    ypred = v*(d-delta0)/(L + K_us*v*v)
    yv0 = (v/L)*np.tan(d)
    m = v > 2.0
    sse += float(np.sum((ypred[m]-y[m])**2)); n += int(m.sum())
    sse_v0 += float(np.sum((yv0[m]-y[m])**2))
print('Dev RMSE no-lag V1:', np.sqrt(sse/n), '  vs V0:', np.sqrt(sse_v0/n))

# Try also fully pooled on all data — fair since we're choosing simple model
V=[]; D=[]; Y=[]
for p in paths:
    df = pd.read_csv(p)
    v = df['v_mps'].to_numpy(); d = df['delta_road_rad'].to_numpy(); y = df['yaw_rate_meas_rads'].to_numpy()
    m = v > 3.0
    V.append(v[m]); D.append(d[m]); Y.append(y[m])
v = np.concatenate(V); d = np.concatenate(D); y = np.concatenate(Y)
rhs = v*d - y*L
A = np.column_stack([y*v*v, v])
coef,*_ = np.linalg.lstsq(A, rhs, rcond=None)
K_us_all, delta0_all = coef
print('All-data fit: K_us=', K_us_all, 'delta0=', delta0_all)
