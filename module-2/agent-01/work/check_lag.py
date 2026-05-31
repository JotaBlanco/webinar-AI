"""Check if there is a time-shift / phase lag between predicted (KS) yaw and measured."""
import os, glob, numpy as np, pandas as pd
ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
os.chdir(ROOT)

for plat, L in [('FORD_F_150_LIGHTNING_MK1', 3.70), ('FORD_MUSTANG_MACH_E_MK1', 2.984)]:
    paths = sorted(glob.glob(f'data/sim/segments/{plat}/**/sim.csv', recursive=True))
    # Pool train portion
    train = paths[::2]
    # Sample first 30
    train = train[:60]
    # Compute average cross-correlation lag in samples
    # Use detrended segments
    lags = []
    for p in train:
        df = pd.read_csv(p)
        v = df['v_mps'].to_numpy()
        d = df['delta_road_rad'].to_numpy()
        y = df['yaw_rate_meas_rads'].to_numpy()
        if (v > 5).sum() < 200: continue
        m = (v > 5)
        if m.sum() < 200: continue
        d_f = d[m]; y_f = y[m]
        # detrend
        d_f = d_f - d_f.mean(); y_f = y_f - y_f.mean()
        if d_f.std() < 1e-4 or y_f.std() < 1e-4: continue
        # full xcorr restricted to +-25 samples (0.5 s @ 50 Hz)
        N = len(d_f)
        best_lag = 0; best_corr = -1
        for k in range(-25, 26):
            if k >= 0:
                a = d_f[:N-k]; b = y_f[k:]
            else:
                a = d_f[-k:]; b = y_f[:N+k]
            if len(a) < 50: continue
            c = np.corrcoef(a,b)[0,1]
            if c > best_corr:
                best_corr = c; best_lag = k
        if best_corr > 0.5:
            lags.append(best_lag)
    if lags:
        print(plat, 'mean lag samples (~20ms each):', np.mean(lags), 'median:', np.median(lags), 'N=', len(lags))
    else:
        print(plat, 'no signal')
