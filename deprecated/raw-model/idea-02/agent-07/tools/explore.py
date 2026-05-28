"""Quick exploration of the Ford CSVs to scope the longitudinal model."""
import glob, os
import numpy as np
import pandas as pd

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"

# Collect a sample of Ford segments (they have a_long_mps2 from IMU, accel_pedal_pct, brake_pressed).
ford_csvs = sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv", recursive=True))
tesla_csvs = sorted(glob.glob(f"{BASE}/TESLA_MODEL_3/**/sim.csv", recursive=True))
print(f"Ford segments: {len(ford_csvs)}; Tesla segments: {len(tesla_csvs)}")

# Inspect one Ford segment in detail
df = pd.read_csv(ford_csvs[0])
print("Ford columns:", list(df.columns))
print(df[["t_s","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed"]].describe())

# dt
dt = np.median(np.diff(df["t_s"].values))
print(f"dt = {dt:.5f} s  ({1/dt:.1f} Hz)")

# Check Tesla
dft = pd.read_csv(tesla_csvs[0])
print("Tesla columns:", list(dft.columns))
print(dft[["t_s","v_mps","a_long_mps2","accel_pedal_pct","brake_pedal_state"]].describe())
