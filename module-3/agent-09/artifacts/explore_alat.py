"""Check whether a_lat_meas/v is a useful yaw-rate estimator."""
import json, sys, glob
import numpy as np
import pandas as pd

with open('artifacts/split.json') as f:
    split = json.load(f)
train = split['train']

# Sample 30 segments randomly
import random
rng = random.Random(0)
rng.shuffle(train)
sample = train[:30]

errs_alat, errs_v0 = [], []
for p in sample:
    df = pd.read_csv(p)
    v = df['v_mps'].to_numpy(float)
    yr_t = df['yaw_rate_meas_rads'].to_numpy(float)
    yr_v0 = df['yaw_rate_pred_rads'].to_numpy(float)
    a_lat = df['a_lat_meas_mps2'].to_numpy(float)
    yr_alat = a_lat / np.where(v > 2.0, v, np.nan)
    mask = v > 2.0
    # bias/RMSE on full segment
    e1 = yr_alat[mask] - yr_t[mask]
    e2 = yr_v0[mask] - yr_t[mask]
    errs_alat.append(np.sqrt(np.nanmean(e1**2)))
    errs_v0.append(np.sqrt(np.nanmean(e2**2)))
print('mean RMSE a_lat/v:', np.mean(errs_alat))
print('mean RMSE V0:     ', np.mean(errs_v0))
print('correlation alat/v with yr_meas (one sample):')
df = pd.read_csv(sample[0])
v = df['v_mps'].to_numpy(float)
yr_t = df['yaw_rate_meas_rads'].to_numpy(float)
a_lat = df['a_lat_meas_mps2'].to_numpy(float)
m = v > 5
yr_alat = a_lat[m] / v[m]
yr_tm = yr_t[m]
print('  r=', np.corrcoef(yr_alat, yr_tm)[0,1])
print('  bias alat/v:', np.mean(yr_alat - yr_tm))
print('  bias V0:    ', np.mean(df['yaw_rate_pred_rads'].to_numpy(float)[m] - yr_tm))
