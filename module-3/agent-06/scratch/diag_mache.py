"""Diagnose Mach-E residual structure."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
from split import split

import os
os.chdir(str(ROOT))

# How many train segments are missing truth?
all_paths = sorted((ROOT / "data" / "sim" / "segments").glob("FORD_*/**/sim.csv"))
train, dev = split(all_paths, dev_fraction=0.25, seed=42)

mache_paths = [p for p in train if "FORD_MUSTANG_MACH_E_MK1" in str(p)]
print(f"Mach-E train segments: {len(mache_paths)}")

missing = 0
for p in mache_paths:
    cols = pd.read_csv(p, nrows=1).columns
    if "yaw_rate_meas_rads" not in cols:
        missing += 1
print(f"  missing yaw_rate_meas_rads: {missing}")

# Look at residual structure on Mach-E train segments
import json
coeffs = json.load(open(ROOT / "scratch" / "coeffs.json"))
p = coeffs["FORD_MUSTANG_MACH_E_MK1"]


def yr_steady(delta, v, g, delta0, K_us, L):
    return v * (g * delta + delta0) / (L + K_us * v * v)


def apply_lag(yr_ss, t, tau):
    n = len(yr_ss)
    y = np.empty(n); y[0] = yr_ss[0]
    dt = np.diff(t); alpha = np.clip(dt / tau, 0, 1)
    for k in range(n - 1):
        y[k + 1] = y[k] + alpha[k] * (yr_ss[k] - y[k])
    return y


# Aggregate residuals vs delta, vs v, vs a_lat for Mach-E
all_d, all_v, all_alat, all_resid, all_yr = [], [], [], [], []
for path in mache_paths[:30]:
    df = pd.read_csv(path)
    if "yaw_rate_meas_rads" not in df.columns:
        continue
    t = df["t_s"].to_numpy(float)
    v = df["v_mps"].to_numpy(float)
    d = df["delta_road_rad"].to_numpy(float)
    yr = df["yaw_rate_meas_rads"].to_numpy(float)
    alat = df["a_lat_meas_mps2"].to_numpy(float) if "a_lat_meas_mps2" in df.columns else np.zeros_like(v)
    yr_ss = yr_steady(d, v, p["g"], p["delta0"], p["K_us"], p["L"])
    yr_pred = apply_lag(yr_ss, t, p["tau"])
    mask = v > 2.0
    all_d.append(d[mask]); all_v.append(v[mask]); all_alat.append(alat[mask])
    all_resid.append((yr_pred - yr)[mask]); all_yr.append(yr[mask])

all_d = np.concatenate(all_d); all_v = np.concatenate(all_v); all_alat = np.concatenate(all_alat)
all_resid = np.concatenate(all_resid); all_yr = np.concatenate(all_yr)

print(f"n samples: {len(all_d)}")
print(f"residual mean={all_resid.mean():.5f}, std={all_resid.std():.5f}")

# Bin by |delta|
import numpy as np
abs_d = np.abs(all_d)
for lo, hi in [(0, 0.005), (0.005, 0.02), (0.02, 0.05), (0.05, 0.1), (0.1, 0.5)]:
    m = (abs_d >= lo) & (abs_d < hi)
    if m.sum() > 100:
        print(f"  |d|=[{lo},{hi}): n={m.sum()}, resid mean={all_resid[m].mean():.5f}, std={all_resid[m].std():.5f}")

# Bin by sign(delta)
m_pos = all_d > 0.01; m_neg = all_d < -0.01
print(f"  d>0.01: mean resid={all_resid[m_pos].mean():.5f}")
print(f"  d<-0.01: mean resid={all_resid[m_neg].mean():.5f}")

# a_lat correlation
print(f"  corr(resid, a_lat)={np.corrcoef(all_resid, all_alat)[0,1]:.3f}")
print(f"  corr(resid, v*delta)={np.corrcoef(all_resid, all_v*all_d)[0,1]:.3f}")
print(f"  corr(resid, delta^2*sign)={np.corrcoef(all_resid, all_d**2*np.sign(all_d))[0,1]:.3f}")
print(f"  corr(resid, |delta|*delta)={np.corrcoef(all_resid, all_d*np.abs(all_d))[0,1]:.3f}")
print(f"  corr(resid, v^2*delta)={np.corrcoef(all_resid, all_v**2*all_d)[0,1]:.3f}")
