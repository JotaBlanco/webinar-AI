import pandas as pd, numpy as np
d = pd.read_csv('/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07/data/sim/segments/FORD_MUSTANG_MACH_E_MK1/fc883bd6fe459212/000004bf--a3e06a0517/1/sim.csv')
print('len:', len(d))
print(d[['t_s','x_m','y_m','psi_rad','v_state_mps','v_mps','yaw_rate_meas_rads','yaw_rate_pred_rads']].head())
print('---tail---')
print(d[['t_s','x_m','y_m','psi_rad']].tail())
t = d['t_s'].values; v_state = d['v_state_mps'].values; v_meas = d['v_mps'].values
yr_meas = d['yaw_rate_meas_rads'].values
yr_pred = d['yaw_rate_pred_rads'].values

def integ(yr, vv):
    n=len(t); psi=np.zeros(n); x=np.zeros(n); y=np.zeros(n)
    for k in range(1,n):
        dt=t[k]-t[k-1]
        psi[k]=psi[k-1]+0.5*(yr[k-1]+yr[k])*dt
        pm=0.5*(psi[k-1]+psi[k]); vm=0.5*(vv[k-1]+vv[k])
        x[k]=x[k-1]+vm*np.cos(pm)*dt
        y[k]=y[k-1]+vm*np.sin(pm)*dt
    return x,y

xm, ym = integ(yr_meas, v_meas)
xp, yp = integ(yr_pred, v_state)
print('meas+v_mps  end:', xm[-1], ym[-1])
print('pred+v_state end:', xp[-1], yp[-1])
print('truth end:', d['x_m'].iloc[-1], d['y_m'].iloc[-1])
print('truth psi end:', d['psi_rad'].iloc[-1])
