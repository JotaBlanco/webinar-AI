"""Load Ford segments into a flat dataframe for longitudinal modelling.

We use Ford only because it gives us a clean IMU `a_long_mps2` channel and
explicit `accel_pedal_pct` + `brake_pressed` — perfect commanded inputs.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-02/data/sim/segments")


def find_csvs(platforms=("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1")) -> list[Path]:
    out = []
    for p in platforms:
        out.extend(sorted((ROOT / p).rglob("sim.csv")))
    return out


def load_segment(csv: Path) -> pd.DataFrame:
    df = pd.read_csv(csv)
    # Annotate with provenance
    parts = csv.parts
    # .../segments/<PLATFORM>/<device>/<seg>/<sub>/sim.csv
    df["platform"] = parts[-5]
    df["device"]   = parts[-4]
    df["segment"]  = parts[-3]
    df["sub"]      = parts[-2]
    return df


def stack_all(limit_segments: int | None = None) -> pd.DataFrame:
    csvs = find_csvs()
    if limit_segments:
        csvs = csvs[:limit_segments]
    frames = []
    for c in csvs:
        try:
            d = load_segment(c)
            if len(d) > 50:
                frames.append(d)
        except Exception as e:
            print(f"skip {c}: {e}")
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    df = stack_all(limit_segments=20)
    print(df.shape)
    print(df.columns.tolist())
    print(df.head(3))
