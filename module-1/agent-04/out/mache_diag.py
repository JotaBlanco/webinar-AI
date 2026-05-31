"""Why is Mach-E so noisy?"""
import pandas as pd, numpy as np, glob

DATA = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim/segments/FORD_MUSTANG_MACH_E_MK1'
files = sorted(glob.glob(f'{DATA}/*/*/*/sim.csv'))
print(f"Mach-E segments: {len(files)}")

# Look at per-segment baseline RMSE - is the issue large segment-level variance?
rmses = []
for f in files[:50]:
    d = pd.read_csv(f)
    rmse = np.sqrt(((d['yaw_rate_meas_rads']-d['yaw_rate_pred_rads'])**2).mean())
    rmses.append((rmse, f, d['v_mps'].mean(), d['yaw_rate_meas_rads'].abs().max()))
rmses.sort(reverse=True)
for r, f, vbar, ymax in rmses[:5]:
    print(f"  worst: rmse={r:.4f} v_mean={vbar:.1f} ymax={ymax:.3f}  {f.split('/')[-3:]}")
for r, f, vbar, ymax in rmses[-5:]:
    print(f"  best:  rmse={r:.4f} v_mean={vbar:.1f} ymax={ymax:.3f}  {f.split('/')[-3:]}")

# Check sample timesteps + perhaps a delay
d = pd.read_csv(files[0])
print(f"\nSample dt: {(d['t_s'].diff().dropna().median()):.4f}")
print(f"Truth-pred corr (zero-lag): {np.corrcoef(d['yaw_rate_meas_rads'], d['yaw_rate_pred_rads'])[0,1]:.4f}")
# Try various lags
truth = d['yaw_rate_meas_rads'].values
pred = d['yaw_rate_pred_rads'].values
for lag in [-5,-3,-1,0,1,3,5,10]:
    if lag>=0:
        c = np.corrcoef(truth[lag:], pred[:len(pred)-lag])[0,1] if len(truth)>lag else 0
    else:
        c = np.corrcoef(truth[:lag], pred[-lag:])[0,1]
    print(f"  lag={lag} samples: corr={c:.4f}")

# Look at scale: truth/pred
mask = np.abs(pred) > 0.02
scale = truth[mask]/pred[mask]
print(f"\ntruth/pred ratio (where |pred|>0.02): median={np.median(scale):.3f}, mean={np.mean(scale):.3f}, std={np.std(scale):.3f}")
