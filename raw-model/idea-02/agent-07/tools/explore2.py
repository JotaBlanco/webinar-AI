"""Aggregate stats over many segments to scope the model."""
import glob
import numpy as np
import pandas as pd

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"

# Ford aggregated
ford_csvs = sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv", recursive=True))
print(f"Sampling {min(50, len(ford_csvs))} Ford segments for stats...")
rows = []
brake_var = 0
for f in ford_csvs[:50]:
    d = pd.read_csv(f)
    rows.append(d[["v_mps","a_long_mps2","accel_pedal_pct","brake_pressed"]])
    if d["brake_pressed"].nunique() > 1:
        brake_var += 1
all_ford = pd.concat(rows)
print(all_ford.describe())
print(f"Segments with variable brake_pressed: {brake_var}/50")
print(f"brake_pressed values seen: {sorted(all_ford['brake_pressed'].unique())}")

# Tesla
tesla_csvs = sorted(glob.glob(f"{BASE}/TESLA_MODEL_3/**/sim.csv", recursive=True))
print(f"\nSampling {min(50, len(tesla_csvs))} Tesla segments...")
rows = []
for f in tesla_csvs[:50]:
    d = pd.read_csv(f)
    rows.append(d[["v_mps","a_long_mps2","accel_pedal_pct","brake_pedal_state","di_torque_actual_nm"]])
all_t = pd.concat(rows)
print(all_t.describe())
print(f"brake_pedal_state vals: {sorted(all_t['brake_pedal_state'].unique())}")
