"""Baseline metric across all Ford simdata CSVs.

The KS lateral prediction is psi_dot_pred = (v / L) tan(delta_road).
Compute RMS / bias of yaw-rate and a_y residuals platform-wide.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-04/data/sim/segments")
PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

def load_all(platform: str) -> pd.DataFrame:
    csvs = sorted(ROOT.joinpath(platform).rglob("sim.csv"))
    frames = []
    for c in csvs:
        try:
            df = pd.read_csv(c)
            df["platform"] = platform
            df["seg"] = str(c.relative_to(ROOT / platform).parent)
            frames.append(df)
        except Exception as e:
            print("skip", c, e)
    return pd.concat(frames, ignore_index=True)

def rms(x):
    x = np.asarray(x); x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2)))

if __name__ == "__main__":
    for plat in PLATFORMS:
        df = load_all(plat)
        n = len(df)
        yaw_resid = df["yaw_rate_meas_rads"] - df["yaw_rate_pred_rads"]
        ay_resid = df["a_lat_meas_mps2"] - df["a_y_pred_mps2"]
        print(f"\n=== {plat} ===  rows={n}  segs={df['seg'].nunique()}")
        print(f"  yaw_rate (rad/s)  RMS={rms(yaw_resid):.5f}  bias={yaw_resid.mean():.5f}  std={yaw_resid.std():.5f}")
        print(f"  a_y (m/s^2)       RMS={rms(ay_resid):.4f}  bias={ay_resid.mean():.4f}  std={ay_resid.std():.4f}")
        print(f"  in deg/s         RMS={np.degrees(rms(yaw_resid)):.3f}")
