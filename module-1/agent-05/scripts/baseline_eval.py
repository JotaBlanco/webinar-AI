"""Evaluate baseline V0 (yaw_rate_pred_rads in the file) against truth (yaw_rate_meas_rads).

We compute per-segment yaw-rate RMSE and overall pooled RMSE.
We also try a few quick improvements:
  - simple bicycle linear gain correction (scaling)
  - steering bias removal
  - low-pass filter mismatch
"""
import os, glob
import numpy as np
import pandas as pd

BASE = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/data/sim/segments'

NEW_SCHEMA_COLS = {'yaw_rate_meas_rads', 'yaw_rate_pred_rads'}


def iter_new_schema_files(platform=None):
    pattern = os.path.join(BASE, platform if platform else '*', '*', '*', '*', 'sim.csv')
    for p in glob.glob(pattern):
        with open(p) as fp:
            hdr = fp.readline().strip().split(',')
        if NEW_SCHEMA_COLS.issubset(set(hdr)):
            yield p


def per_platform_baseline():
    summary = {}
    for plat in ['FORD_F_150_LIGHTNING_MK1', 'HYUNDAI_IONIQ_5', 'FORD_MUSTANG_MACH_E_MK1', 'TESLA_MODEL_3']:
        sse, n = 0.0, 0
        n_seg = 0
        for p in iter_new_schema_files(plat):
            df = pd.read_csv(p)
            r = df['yaw_rate_pred_rads'].values - df['yaw_rate_meas_rads'].values
            sse += np.sum(r**2)
            n += len(r)
            n_seg += 1
        if n:
            summary[plat] = (np.sqrt(sse/n), n_seg, n)
            print(f"{plat}: baseline yaw RMSE = {np.sqrt(sse/n):.5f} rad/s ({n_seg} segments, {n} samples)")
    return summary


if __name__ == "__main__":
    per_platform_baseline()
