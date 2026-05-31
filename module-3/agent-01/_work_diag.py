"""Diagnose Mach-E CTE residual structure."""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, 'code')
from split import split
import pandas as pd
import numpy as np
import parameters as P

tr, dv = split(dev_fraction=0.25, seed=42)
PLAT = 'FORD_MUSTANG_MACH_E_MK1'
L = P.MACH_E.L

# Use V1 fit
g = 1.1758194286274308
K_us = 0.0025190900693713852
d0 = -3.6482033317411595e-05


def platform_from_path(p):
    return Path(p).resolve().parents[3].name


# Look at residual vs a_lat, vs |delta|, vs v
deltas, vs, yrs, a_lats, dh = [], [], [], [], []
for p in dv:
    if platform_from_path(p) != PLAT:
        continue
    df = pd.read_csv(p)
    if 'yaw_rate_meas_rads' not in df.columns:
        continue
    m = (df['v_mps'] > 5).values
    delta = df['delta_road_rad'].values[m]
    v = df['v_mps'].values[m]
    yr = df['yaw_rate_meas_rads'].values[m]
    a_lat = df['a_lat_meas_mps2'].values[m] if 'a_lat_meas_mps2' in df.columns else np.zeros(m.sum())
    pred = v * g * (delta - d0) / (L + K_us * v**2)
    deltas.append(delta); vs.append(v); yrs.append(yr); a_lats.append(a_lat)
    dh.append(yr - pred)

delta = np.concatenate(deltas); v = np.concatenate(vs); yr = np.concatenate(yrs)
a_lat = np.concatenate(a_lats); resid = np.concatenate(dh)

print(f"Mach-E dev: {len(delta)} samples")
print(f"Mean residual (yr_meas - yr_pred): {np.mean(resid):.6f} (should be ~0)")
print(f"Std residual: {np.std(resid):.6f}")

# Bin by |delta|
print("\nResidual by |delta| bins:")
for lo, hi in [(0, 0.01), (0.01, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.5)]:
    m = (np.abs(delta) >= lo) & (np.abs(delta) < hi)
    if m.sum() > 100:
        print(f"  |delta| in [{lo},{hi}): n={m.sum()}, mean_resid={np.mean(resid[m]):.6f}, std={np.std(resid[m]):.6f}")

# a_lat_meas vs yr*v relationship
yr_from_alat = a_lat / np.maximum(v, 0.1)
diff_alat = yr_from_alat - yr
print(f"\nResidual a_lat/v - yr_meas: mean={np.mean(diff_alat):.6f}, std={np.std(diff_alat):.6f}")
# Try: predict yr as a weighted blend of a_lat/v with model
# residual model: yr_meas = yr_model_pred + k*(a_lat/v - yr_model_pred)
# = (1-k)*yr_model + k*a_lat/v
# Fit k via least-squares on dev (we'll do this on train below; here we just diagnose)

# Bin by sign(delta) to check left/right asymmetry
m_left = delta > 0.01
m_right = delta < -0.01
print(f"\nLeft turns (delta>0.01): mean_resid={np.mean(resid[m_left]):.6f}")
print(f"Right turns (delta<-0.01): mean_resid={np.mean(resid[m_right]):.6f}")
