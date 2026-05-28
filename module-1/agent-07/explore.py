"""Explore Ford sim CSVs to baseline V0 and design a fitted model.

Outputs to stdout — does not write artefacts.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments")
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "TESLA_MODEL_3"]

def list_csvs(platform: str) -> list[Path]:
    return sorted((DATA / platform).rglob("sim.csv"))

def rmse(a: np.ndarray) -> float:
    return float(np.sqrt(np.mean(a**2)))

def main():
    for plat in PLATFORMS:
        files = list_csvs(plat)
        print(f"\n=== {plat}  ({len(files)} segments) ===")
        if not files: continue
        # sample first file
        df = pd.read_csv(files[0])
        print(f" cols: {list(df.columns)}")
        print(f" rows: {len(df)},  dt~{df['t_s'].diff().median():.4f}s")

        # Aggregate V0 yaw_rate RMSE across the platform (Ford only)
        if "yaw_rate_meas_rads" in df.columns:
            total_sq = 0.0; total_n = 0
            v_range = []
            for f in files:
                d = pd.read_csv(f, usecols=["yaw_rate_meas_rads","yaw_rate_pred_rads","v_mps","delta_road_rad"])
                r = d["yaw_rate_meas_rads"].values - d["yaw_rate_pred_rads"].values
                total_sq += float(np.sum(r**2))
                total_n  += len(r)
                v_range.append((d["v_mps"].min(), d["v_mps"].max()))
            print(f" V0 yaw RMSE = {np.sqrt(total_sq/total_n):.5f} rad/s "
                  f"({np.degrees(np.sqrt(total_sq/total_n)):.3f} deg/s) over {total_n} samples")
        else:
            print(" (no truth: tesla)")

if __name__ == "__main__":
    main()
