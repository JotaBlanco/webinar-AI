"""Maybe truth x_m/y_m is integrated from yaw_rate_meas_rads (the real truth)."""
import pandas as pd, numpy as np, glob

for plat in ['FORD_F_150_LIGHTNING_MK1','HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1']:
    files = sorted(glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim/segments/{plat}/*/*/*/sim.csv'))[:3]
    for f in files:
        df = pd.read_csv(f)
        if 'yaw_rate_meas_rads' not in df.columns: continue
        truth_yaw = df['yaw_rate_meas_rads'].values
        v = df['v_mps'].values
        t = df['t_s'].values
        n = len(t)
        psi = np.zeros(n)
        if n>1:
            dt = np.diff(t)
            psi[1:] = np.cumsum(0.5*(truth_yaw[:-1]+truth_yaw[1:])*dt)
        vx = v*np.cos(psi); vy = v*np.sin(psi)
        x = np.zeros(n); y = np.zeros(n)
        if n>1:
            dt = np.diff(t)
            x[1:] = np.cumsum(0.5*(vx[:-1]+vx[1:])*dt)
            y[1:] = np.cumsum(0.5*(vy[:-1]+vy[1:])*dt)
        diff_x = (x - df['x_m']).abs().max()
        diff_y = (y - df['y_m']).abs().max()
        # Also check pred-based
        pred_yaw = df['yaw_rate_pred_rads'].values
        psi_p = np.zeros(n)
        if n>1:
            psi_p[1:] = np.cumsum(0.5*(pred_yaw[:-1]+pred_yaw[1:])*dt)
        vxp = v*np.cos(psi_p); vyp = v*np.sin(psi_p)
        xp = np.zeros(n); yp = np.zeros(n)
        if n>1:
            xp[1:] = np.cumsum(0.5*(vxp[:-1]+vxp[1:])*dt)
            yp[1:] = np.cumsum(0.5*(vyp[:-1]+vyp[1:])*dt)
        diff_xp = (xp - df['x_m']).abs().max()
        diff_yp = (yp - df['y_m']).abs().max()
        print(f"{plat} {f.split('/')[-3]}: from-truth x/y diff={diff_x:.3f}/{diff_y:.3f}  from-pred x/y diff={diff_xp:.3f}/{diff_yp:.3f}")
        break  # first segment per plat
