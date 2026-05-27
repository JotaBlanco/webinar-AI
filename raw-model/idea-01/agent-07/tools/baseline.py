"""Compute baseline lateral-prediction RMSE across all Ford sim CSVs.

Headline metric: RMS of yaw_rate residual (in deg/s) aggregated across all
samples in all Ford CSVs (both Mach-E and F-150). a_y residual reported too.
"""
from __future__ import annotations
import glob, sys, os
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-07/data/sim/segments"

def load_all(platform):
    csvs = sorted(glob.glob(os.path.join(ROOT, platform, "*", "*", "*", "sim.csv")))
    frames = []
    for c in csvs:
        try:
            df = pd.read_csv(c)
            df["__src"] = c
            df["__platform"] = platform
            frames.append(df)
        except Exception as e:
            print("skip", c, e)
    return frames

def rms(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x**2))) if len(x) else float("nan")

def summarise(label, df_all):
    yaw_resid = df_all["yaw_rate_meas_rads"].values - df_all["yaw_rate_pred_rads"].values
    ay_resid  = df_all["a_lat_meas_mps2"].values   - df_all["a_y_pred_mps2"].values
    print(f"--- {label} ---")
    print(f"  N samples            : {len(df_all):,}")
    print(f"  RMS yaw-rate resid   : {np.degrees(rms(yaw_resid)):.4f} deg/s   ({rms(yaw_resid):.5f} rad/s)")
    print(f"  RMS a_y resid        : {rms(ay_resid):.4f} m/s^2")
    print(f"  RMS yaw_meas         : {np.degrees(rms(df_all['yaw_rate_meas_rads'])):.3f} deg/s")
    print(f"  RMS a_y_meas         : {rms(df_all['a_lat_meas_mps2']):.3f} m/s^2")
    return {
        "label": label,
        "n": len(df_all),
        "yaw_rms_degs": np.degrees(rms(yaw_resid)),
        "yaw_rms_rads": rms(yaw_resid),
        "ay_rms": rms(ay_resid),
        "yaw_meas_rms_degs": np.degrees(rms(df_all["yaw_rate_meas_rads"])),
    }

if __name__ == "__main__":
    machE_frames = load_all("FORD_MUSTANG_MACH_E_MK1")
    f150_frames  = load_all("FORD_F_150_LIGHTNING_MK1")
    print(f"Loaded {len(machE_frames)} Mach-E CSVs, {len(f150_frames)} F-150 CSVs")

    machE = pd.concat(machE_frames, ignore_index=True) if machE_frames else pd.DataFrame()
    f150  = pd.concat(f150_frames,  ignore_index=True) if f150_frames  else pd.DataFrame()
    both  = pd.concat([machE, f150], ignore_index=True)

    summarise("Mach-E (baseline)", machE)
    summarise("F-150  (baseline)", f150)
    summarise("Combined (baseline)", both)
