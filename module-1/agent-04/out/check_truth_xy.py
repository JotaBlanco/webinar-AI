"""Is the truth (x_m, y_m) the integrated KS trajectory or actual measurement?"""
import pandas as pd, numpy as np, glob

for plat in ['FORD_F_150_LIGHTNING_MK1','HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','TESLA_MODEL_3']:
    files = sorted(glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim/segments/{plat}/*/*/*/sim.csv'))[:1]
    if not files: continue
    df = pd.read_csv(files[0])
    print(f"\n{plat}:")
    print(f"  cols with x/y/psi: {[c for c in df.columns if any(k in c for k in ['x_','y_','psi'])]}")
    if 'yaw_rate_pred_rads' in df.columns:
        pred_yaw = df['yaw_rate_pred_rads'].values
        v = df['v_mps'].values
        t = df['t_s'].values
        n = len(t)
        psi = np.zeros(n)
        if n>1:
            dt = np.diff(t)
            psi[1:] = np.cumsum(0.5*(pred_yaw[:-1]+pred_yaw[1:])*dt)
        # Now compare psi to df['psi_rad']
        print(f"  psi (integrated from pred_yaw) vs df['psi_rad']: max abs diff = {(psi-df['psi_rad']).abs().max():.4f}")
        # integrate x,y
        vx = v*np.cos(psi); vy = v*np.sin(psi)
        x = np.zeros(n); y = np.zeros(n)
        if n>1:
            dt = np.diff(t)
            x[1:] = np.cumsum(0.5*(vx[:-1]+vx[1:])*dt)
            y[1:] = np.cumsum(0.5*(vy[:-1]+vy[1:])*dt)
        print(f"  x integrated vs df['x_m']: max abs diff = {(x-df['x_m']).abs().max():.4f}")
        print(f"  y integrated vs df['y_m']: max abs diff = {(y-df['y_m']).abs().max():.4f}")
    elif 'psi_dot_rads' in df.columns:
        pred_yaw = df['psi_dot_rads'].values
        v = df['v_mps'].values
        t = df['t_s'].values
        n = len(t)
        psi = np.zeros(n)
        if n>1:
            dt = np.diff(t)
            psi[1:] = np.cumsum(0.5*(pred_yaw[:-1]+pred_yaw[1:])*dt)
        print(f"  psi integrated vs df['psi_rad']: max abs diff = {(psi-df['psi_rad']).abs().max():.4f}")
