"""Check whether x_m,y_m in sim/ is the integrated KS path or truth path."""
import pandas as pd, numpy as np
import glob
files = sorted(glob.glob('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim/segments/HYUNDAI_IONIQ_5/*/*/*/sim.csv'))
df = pd.read_csv(files[0])
t = df['t_s'].values
v = df['v_mps'].values
L = 3.0
# KS yaw rate
yr_ks = (df['v_mps'].values/L)*np.tan(df['delta_road_rad'].values)
N = len(t)
def integrate(yr):
    psi = np.zeros(N); x=np.zeros(N); y=np.zeros(N)
    for k in range(N-1):
        dt = t[k+1]-t[k]
        yr_mid = 0.5*(yr[k]+yr[k+1])
        psi[k+1] = psi[k] + yr_mid*dt
        psi_mid = 0.5*(psi[k]+psi[k+1])
        v_mid = 0.5*(v[k]+v[k+1])
        x[k+1] = x[k] + v_mid*np.cos(psi_mid)*dt
        y[k+1] = y[k] + v_mid*np.sin(psi_mid)*dt
    return x,y,psi

x_ks,y_ks,psi_ks = integrate(yr_ks)
print('KS-recompute final:', x_ks[-1], y_ks[-1], 'psi', psi_ks[-1])
print('sim recorded final:', df['x_m'].iloc[-1], df['y_m'].iloc[-1], 'psi', df['psi_rad'].iloc[-1])
x_t,y_t,psi_t = integrate(df['yaw_rate_meas_rads'].values)
print('Truth-integrate final:', x_t[-1], y_t[-1], 'psi', psi_t[-1])
