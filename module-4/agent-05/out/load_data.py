"""Load segments and compute V0/V1 baseline scores quickly."""
from __future__ import annotations
import os, sys, glob, math, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-05")
SIM = ROOT / "data" / "sim" / "segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def list_segments(platform: str) -> list[Path]:
    """Return all sim.csv paths under the platform tree."""
    pdir = SIM / platform
    return sorted(pdir.rglob("sim.csv"))


def load_segment(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p)
    return df


def sim_only_df(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2",
            "accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]
    return df[cols].copy()


if __name__ == "__main__":
    for plat in PLATFORMS:
        segs = list_segments(plat)
        print(f"{plat}: {len(segs)} segments")
