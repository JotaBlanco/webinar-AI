#!/usr/bin/env python3
"""step2_segment_by_regime.py — add `regime` column to a loaded DataFrame."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd

DELTA_THR = 0.01    # rad
DDELTA_THR = 0.05   # rad/s
DEFAULT_DT = 0.02


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    df = pd.read_parquet(args.inp)
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, DEFAULT_DT)
    delta = df["delta_road_rad"].to_numpy()
    ddelta = np.gradient(delta) / dt

    reg = np.full(len(df), "transient", dtype=object)
    reg[np.abs(delta) < DELTA_THR] = "straight"
    steady = (np.abs(delta) >= DELTA_THR) & (np.abs(ddelta) < DDELTA_THR)
    reg[steady] = "steady"
    df["regime"] = reg
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out)

    counts = {r: int((reg == r).sum()) for r in ("straight", "steady", "transient")}
    print(f"regime counts: {counts} → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
